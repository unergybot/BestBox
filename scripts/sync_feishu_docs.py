#!/usr/bin/env python3
"""Sync Feishu docs into BestBox Qdrant knowledge base with incremental cursor."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from qdrant_client.models import Distance, PointStruct, SparseVector
import hashlib

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.rag_pipeline.chunker import TextChunker
from services.rag_pipeline.vector_store import VectorStore


FEISHU_HOST = os.getenv("FEISHU_HOST", "https://open.feishu.cn")
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
COLLECTION = os.getenv("KB_COLLECTION", "bestbox_knowledge")
STATE_DIR = project_root / "data" / ".seed_state"
STATE_FILE = STATE_DIR / "feishu_cursor.json"


def _load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {"updated_at": 0}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _save_state(state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _tenant_token() -> str:
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET")

    response = requests.post(
        f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant token: {payload}")
    return payload["tenant_access_token"]


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _list_docs(token: str, updated_after: int) -> List[Dict[str, Any]]:
    """List docs from Feishu Drive API (supports incremental filter by update time)."""
    docs: List[Dict[str, Any]] = []
    page_token: Optional[str] = None

    while True:
        params: Dict[str, Any] = {
            "page_size": 50,
            "order_by": "EditedTime",
            "direction": "DESC",
        }
        if page_token:
            params["page_token"] = page_token

        response = requests.get(
            f"{FEISHU_HOST}/open-apis/drive/explorer/v2/root_folder/meta",
            headers=_headers(token),
            params=params,
            timeout=15,
        )

        # Some tenants disable this endpoint; fail gracefully.
        if response.status_code >= 400:
            break

        payload = response.json()
        if payload.get("code") != 0:
            break

        items = payload.get("data", {}).get("items", []) or []
        for item in items:
            edited = int(item.get("edit_time", 0) or 0)
            if edited and edited < updated_after:
                continue
            docs.append(
                {
                    "doc_id": item.get("token") or item.get("obj_token"),
                    "title": item.get("name") or "Untitled",
                    "updated_at": edited,
                }
            )

        if not payload.get("data", {}).get("has_more"):
            break
        page_token = payload.get("data", {}).get("page_token")
        if not page_token:
            break

    return docs


def _fetch_raw_content(token: str, doc_id: str) -> Optional[str]:
    if not doc_id:
        return None

    response = requests.get(
        f"{FEISHU_HOST}/open-apis/docx/v1/documents/{doc_id}/raw_content",
        headers=_headers(token),
        timeout=15,
    )
    if response.status_code >= 400:
        return None

    payload = response.json()
    if payload.get("code") != 0:
        return None

    data = payload.get("data", {})
    if isinstance(data, dict):
        return data.get("content") or data.get("raw_content")
    return None


def _embed(texts: List[str]) -> List[List[float]]:
    response = requests.post(
        os.getenv("EMBEDDINGS_URL", "http://localhost:8081/embed"),
        json={"inputs": texts, "normalize": True},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["embeddings"]


def _content_hash(text: str) -> str:
    """Compute SHA-256 hash of document content for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_doc_indexed(vector_store: VectorStore, doc_id: str, content_hash: str) -> bool:
    """
    Check if a document with the same content hash is already indexed.

    Args:
        vector_store: VectorStore instance
        doc_id: Feishu document ID
        content_hash: SHA-256 hash of content

    Returns:
        True if document with same hash exists, False otherwise
    """
    try:
        result = vector_store.client.scroll(
            collection_name=COLLECTION,
            scroll_filter={
                "must": [
                    {"key": "doc_id", "match": {"value": doc_id}},
                    {"key": "content_hash", "match": {"value": content_hash}}
                ]
            },
            limit=1,
            with_payload=True,
        )
        points = result[0]
        return len(points) > 0
    except Exception:
        return False


def _sparse_vector(text: str, size: int = 65536) -> SparseVector:
    term_counts: Dict[int, int] = {}
    for token in re.findall(r"[A-Za-z0-9_]+", text.lower()):
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % size
        term_counts[idx] = term_counts.get(idx, 0) + 1

    indices = list(term_counts.keys())
    values = [float(term_counts[idx]) for idx in indices]
    return SparseVector(indices=indices, values=values)


def _ensure_collection(vector_store: VectorStore) -> None:
    try:
        vector_store.client.get_collection(COLLECTION)
    except Exception:
        vector_store.create_collection(
            collection_name=COLLECTION,
            vector_size=1024,
            distance=Distance.COSINE,
            enable_bm25=True,
        )


def sync_feishu_docs() -> None:
    token = _tenant_token()
    state = _load_state()
    updated_after = int(state.get("updated_at", 0))

    docs = _list_docs(token, updated_after)
    if not docs:
        print("No Feishu docs found or list endpoint unavailable.")
        return

    vector_store = VectorStore()
    _ensure_collection(vector_store)
    chunker = TextChunker(chunk_size=512, overlap_percentage=0.2)

    newest_ts = updated_after
    indexed_docs = 0
    indexed_chunks = 0
    skipped_docs = 0

    for doc in docs:
        doc_id = str(doc.get("doc_id") or "")
        content = _fetch_raw_content(token, doc_id)
        if not content:
            continue

        # Check content hash for deduplication
        content_hash = _content_hash(content)
        if _check_doc_indexed(vector_store, doc_id, content_hash):
            print(f"Skipping {doc.get('title')}: unchanged (hash: {content_hash[:16]}...)")
            skipped_docs += 1
            continue

        chunks = chunker.chunk_text(content)
        if not chunks:
            continue

        embeddings = _embed([chunk["text"] for chunk in chunks])
        points: List[PointStruct] = []

        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector={"": embedding, "text": _sparse_vector(chunk["text"])},
                    payload={
                        "chunk_id": f"feishu_{doc_id}_{index}",
                        "text": chunk["text"],
                        "domain": "oa",
                        "source": "feishu",
                        "doc_id": doc_id,
                        "content_hash": content_hash,  # Store hash for deduplication
                        "title": doc.get("title"),
                        "updated_at": int(doc.get("updated_at") or 0),
                        "token_count": chunk["token_count"],
                        "synced_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            )

        vector_store.client.upsert(collection_name=COLLECTION, points=points)

        indexed_docs += 1
        indexed_chunks += len(points)
        newest_ts = max(newest_ts, int(doc.get("updated_at") or 0))

    _save_state({"updated_at": newest_ts, "last_sync": datetime.now(timezone.utc).isoformat()})

    print(f"Indexed Feishu docs: {indexed_docs}")
    print(f"Skipped docs (unchanged): {skipped_docs}")
    print(f"Indexed chunks: {indexed_chunks}")
    print(f"Cursor updated_at: {newest_ts}")
    print(f"Deduplication: Content hashes tracked to skip unchanged documents")


if __name__ == "__main__":
    try:
        sync_feishu_docs()
    except Exception as exc:
        print(f"Feishu sync failed: {exc}")
        sys.exit(1)
