#!/usr/bin/env python3
"""Index all processed troubleshooting cases into Qdrant.

This is the "missing step" when Qdrant collections exist but are empty
(`troubleshooting_cases` / `troubleshooting_issues` have 0 points).

It loads JSON case files from `data/troubleshooting/processed/` and indexes each
case at both levels (case + issue vectors).

Typical run (after starting Qdrant + embeddings):
    python scripts/index_troubleshooting_processed.py

Options:
    python scripts/index_troubleshooting_processed.py --limit 10
    python scripts/index_troubleshooting_processed.py --processed-dir data/troubleshooting/processed

Notes:
- Indexing requires the embeddings service to be running (default: http://localhost:8004).
- The indexer deletes by `case_id` before reindexing, so reruns are safe.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Add project root to python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.troubleshooting.indexer import TroubleshootingIndexer  # noqa: E402


def _looks_like_case(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("case_id"), str)
        and payload.get("case_id")
        and isinstance(payload.get("issues"), list)
        and "metadata" in payload
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Index processed troubleshooting JSON into Qdrant")
    parser.add_argument(
        "--processed-dir",
        type=str,
        default="data/troubleshooting/processed",
        help="Directory containing processed troubleshooting JSON files",
    )
    parser.add_argument(
        "--glob",
        type=str,
        default="*.json",
        help="Glob pattern to match JSON files within processed-dir",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of case files to index (0 = no limit)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching files and exit without indexing",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately if any case fails to index",
    )
    parser.add_argument(
        "--qdrant-host",
        type=str,
        default=os.getenv("QDRANT_HOST", "localhost"),
    )
    parser.add_argument(
        "--qdrant-port",
        type=int,
        default=int(os.getenv("QDRANT_PORT", "6333")),
    )
    parser.add_argument(
        "--embeddings-url",
        type=str,
        default=os.getenv("EMBEDDINGS_URL", os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004")),
    )

    args = parser.parse_args()

    processed_dir = (PROJECT_ROOT / args.processed_dir).resolve()
    if not processed_dir.exists():
        print(f"❌ Processed directory not found: {processed_dir}")
        return 2

    # Avoid indexing non-case JSON files (and anything under images/)
    candidates = [
        p
        for p in processed_dir.glob(args.glob)
        if p.is_file() and p.suffix.lower() == ".json" and p.parent.name != "images"
    ]

    # Prefer enriched files last (so they win if both exist)
    candidates.sort(key=lambda p: (p.name.endswith("_enriched.json"), p.name))

    if args.limit and args.limit > 0:
        candidates = candidates[: args.limit]

    if not candidates:
        print(f"⚠️  No JSON files matched: dir={processed_dir} glob={args.glob}")
        return 0

    print(f"📁 Found {len(candidates)} candidate JSON files")
    if args.dry_run:
        for p in candidates:
            print(f"- {p.relative_to(PROJECT_ROOT)}")
        return 0

    indexer = TroubleshootingIndexer(
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        embeddings_url=args.embeddings_url,
    )

    ok = 0
    skipped = 0
    failed = 0

    for idx, json_path in enumerate(candidates, start=1):
        rel = json_path.relative_to(PROJECT_ROOT)
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            if not _looks_like_case(payload):
                skipped += 1
                print(f"[{idx}/{len(candidates)}] ↷ Skipping (not a case): {rel}")
                continue

            case_id = payload.get("case_id")
            print(f"[{idx}/{len(candidates)}] 📊 Indexing case {case_id}: {rel}")
            stats = indexer.index_case(payload, force_reindex=True)
            ok += 1
            print(
                f"   ✅ case_points={stats.get('case_points')} issue_points={stats.get('issue_points')}"
            )

        except Exception as e:
            failed += 1
            print(f"[{idx}/{len(candidates)}] ❌ Failed: {rel}\n   {type(e).__name__}: {e}")
            if args.stop_on_error:
                break

    print("\n📊 Indexing summary")
    print(f"- ok: {ok}")
    print(f"- skipped: {skipped}")
    print(f"- failed: {failed}")

    stats = indexer.get_collection_stats()
    print("\n📈 Qdrant collection stats")
    for name, info in stats.items():
        if "error" in info:
            print(f"- {name}: error={info['error']}")
        else:
            print(f"- {name}: points_count={info.get('points_count')} status={info.get('status')}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
