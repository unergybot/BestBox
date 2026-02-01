#!/usr/bin/env python3
"""
Cleanup duplicate troubleshooting points in Qdrant.

Strategy:
- For `troubleshooting_issues`: group points by (case_id, issue_number).
  For each group, keep the point whose payload.images best match files on disk
  (count of image_ids that exist). If tie, keep the one with larger image_count.
- For `troubleshooting_cases`: group by case_id and keep the one with largest total_issues.

Run:
    ./scripts/cleanup_qdrant_duplicates.py
"""
import os
from pathlib import Path
from collections import defaultdict
from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT / 'data' / 'troubleshooting' / 'processed' / 'images'


def file_exists_for_image_id(image_id: str) -> bool:
    # image_id may or may not include extension
    if not image_id:
        return False
    p = Path(image_id)
    name = p.name
    # try direct
    candidate = IMAGES_DIR / name
    if candidate.exists():
        return True
    # try common extensions
    for ext in ('.jpg', '.jpeg', '.png', '.webp'):
        if (IMAGES_DIR / f"{name}{ext}").exists():
            return True
    # try glob matching
    matches = list(IMAGES_DIR.glob(f"*{name}*"))
    return len(matches) > 0


def cleanup_issues(client: QdrantClient):
    print('Scanning troubleshooting_issues...')
    scroll = client.scroll(collection_name='troubleshooting_issues', limit=10000)
    points = list(scroll[0])
    print(f'  Got {len(points)} points')

    groups = defaultdict(list)
    for p in points:
        payload = p.payload or {}
        case_id = payload.get('case_id')
        issue_number = payload.get('issue_number')
        if case_id is None or issue_number is None:
            # put in its own group
            groups[(p.id, None)].append(p)
        else:
            groups[(case_id, int(issue_number))].append(p)

    to_delete = []
    kept = 0
    for key, pts in groups.items():
        if len(pts) <= 1:
            kept += len(pts)
            continue

        # Score each point by number of image_ids that exist on disk
        scored = []
        for p in pts:
            payload = p.payload or {}
            images = payload.get('images', []) or []
            match_count = 0
            for img in images:
                img_id = None
                if isinstance(img, dict):
                    img_id = img.get('image_id') or img.get('file_path') or img.get('url')
                else:
                    img_id = str(img)
                if img_id and file_exists_for_image_id(img_id):
                    match_count += 1
            image_count = payload.get('image_count', len(images))
            scored.append((p, match_count, image_count))

        # choose keeper: highest match_count, then highest image_count
        scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
        keeper = scored[0][0]
        # others to delete
        for s in scored[1:]:
            to_delete.append(s[0].id)

        kept += 1

    print(f'Identified {len(to_delete)} duplicate issue points to delete, keeping {kept} points')
    if to_delete:
        print('Deleting issue points...')
        # delete in batches
        batch = []
        for pid in to_delete:
            batch.append(pid)
            if len(batch) >= 100:
                client.delete(collection_name='troubleshooting_issues', points_selector=batch)
                batch = []
        if batch:
            client.delete(collection_name='troubleshooting_issues', points_selector=batch)


def cleanup_cases(client: QdrantClient):
    print('Scanning troubleshooting_cases...')
    scroll = client.scroll(collection_name='troubleshooting_cases', limit=10000)
    points = list(scroll[0])
    print(f'  Got {len(points)} points')

    groups = defaultdict(list)
    for p in points:
        payload = p.payload or {}
        case_id = payload.get('case_id')
        groups[case_id].append(p)

    to_delete = []
    kept = 0
    for case_id, pts in groups.items():
        if not case_id or len(pts) <= 1:
            kept += len(pts)
            continue

        # prefer point with largest total_issues
        best = None
        best_issues = -1
        for p in pts:
            total = (p.payload or {}).get('total_issues') or 0
            try:
                total = int(total)
            except Exception:
                total = 0
            if total > best_issues:
                best = p
                best_issues = total

        for p in pts:
            if p.id != best.id:
                to_delete.append(p.id)
        kept += 1

    print(f'Identified {len(to_delete)} duplicate case points to delete')
    if to_delete:
        print('Deleting case points...')
        batch = []
        for pid in to_delete:
            batch.append(pid)
            if len(batch) >= 100:
                client.delete(collection_name='troubleshooting_cases', points_selector=batch)
                batch = []
        if batch:
            client.delete(collection_name='troubleshooting_cases', points_selector=batch)


def main():
    q = QdrantClient(host=os.getenv('QDRANT_HOST','localhost'), port=int(os.getenv('QDRANT_PORT','6333')))
    print('Connected to Qdrant')

    cleanup_issues(q)
    cleanup_cases(q)

    print('Done')


if __name__ == '__main__':
    main()
