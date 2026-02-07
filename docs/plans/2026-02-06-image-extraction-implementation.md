# Image Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract images from Docling output, save to disk, link to chunks, serve via API, and display in frontend.

**Architecture:** Images are decoded from Docling's base64 `pictures` array, saved as JPEG to `data/uploads/images/{doc_id}/`, and linked to chunks via `<!-- image -->` placeholder positions in the markdown. A new authenticated endpoint serves images, and the KB browse page displays thumbnails with a lightbox.

**Tech Stack:** Python (FastAPI, Pillow), TypeScript (Next.js/React), Qdrant

---

### Task 1: `_extract_and_save_images()` helper

**Files:**
- Modify: `services/admin_endpoints.py` (add helper after line 1238, after `_hierarchical_chunk`)
- Test: `tests/test_image_extraction.py` (create)

**Step 1: Write the failing test**

Create `tests/test_image_extraction.py`:

```python
"""Tests for image extraction from Docling results."""

import base64
import io
from pathlib import Path
from unittest.mock import patch

import pytest

# Create a minimal 1x1 red PNG for testing
def _make_test_png_b64() -> str:
    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (1, 1), (255, 0, 0))
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_extract_and_save_images_decodes_and_saves(tmp_path):
    """Should decode base64 images from Docling result and save as JPEG."""
    from services.admin_endpoints import _extract_and_save_images

    b64 = _make_test_png_b64()
    docling_result = {
        "pictures": [
            {"image": {"uri": f"data:image/png;base64,{b64}"}, "prov": [{"page_no": 1}]},
            {"image": {"uri": f"data:image/png;base64,{b64}"}, "prov": [{"page_no": 2}]},
        ]
    }

    images = _extract_and_save_images(docling_result, doc_id="test123", base_dir=tmp_path)

    assert len(images) == 2
    assert images[0]["image_id"] == "test123_page1_img0"
    assert images[1]["image_id"] == "test123_page2_img1"
    # Files should exist on disk
    assert Path(images[0]["path"]).exists()
    assert Path(images[1]["path"]).exists()
    # Should be JPEG
    assert images[0]["path"].endswith(".jpg")


def test_extract_and_save_images_empty_pictures():
    """Should return empty list when no pictures in Docling result."""
    from services.admin_endpoints import _extract_and_save_images

    images = _extract_and_save_images({}, doc_id="test456")
    assert images == []


def test_extract_and_save_images_skips_bad_base64(tmp_path):
    """Should skip images with invalid base64 and continue."""
    from services.admin_endpoints import _extract_and_save_images

    b64 = _make_test_png_b64()
    docling_result = {
        "pictures": [
            {"image": {"uri": "data:image/png;base64,INVALID!!!"}, "prov": [{"page_no": 1}]},
            {"image": {"uri": f"data:image/png;base64,{b64}"}, "prov": [{"page_no": 1}]},
        ]
    }

    images = _extract_and_save_images(docling_result, doc_id="test789", base_dir=tmp_path)

    # Should have 1 image (skipped the bad one)
    assert len(images) == 1
    assert images[0]["image_id"] == "test789_page1_img1"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_image_extraction.py -v`
Expected: FAIL with `ImportError` (function doesn't exist yet)

**Step 3: Write the implementation**

Add to `services/admin_endpoints.py` after the `_hierarchical_chunk` function (after line 1238):

```python
# Image storage directory
IMAGE_DIR = UPLOAD_DIR / "images"


def _extract_and_save_images(
    docling_result: Dict[str, Any],
    doc_id: str,
    base_dir: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """
    Extract embedded images from Docling result, save as JPEG to disk.

    Returns list of dicts: {"image_id": ..., "path": ..., "page": ...}
    """
    pictures = docling_result.get("pictures", [])
    if not pictures:
        return []

    save_dir = (base_dir or IMAGE_DIR) / doc_id
    save_dir.mkdir(parents=True, exist_ok=True)

    images: List[Dict[str, str]] = []
    for idx, pic in enumerate(pictures):
        try:
            uri = pic.get("image", {}).get("uri", "")
            if not uri or "base64," not in uri:
                continue

            b64_data = uri.split("base64,", 1)[1]
            raw_bytes = base64.b64decode(b64_data)

            # Get page number from provenance
            prov = pic.get("prov", [{}])
            page_no = prov[0].get("page_no", 0) if prov else 0

            image_id = f"{doc_id}_page{page_no}_img{idx}"
            filename = f"page{page_no}_img{idx}.jpg"
            filepath = save_dir / filename

            # Convert to JPEG via Pillow
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(raw_bytes))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(filepath, "JPEG", quality=90)
            except Exception:
                # Fallback: save raw bytes
                filepath = save_dir / f"page{page_no}_img{idx}.bin"
                filepath.write_bytes(raw_bytes)

            images.append({
                "image_id": image_id,
                "path": str(filepath),
                "page": str(page_no),
            })

        except Exception as e:
            logger.warning(f"Skipping image {idx} in doc {doc_id}: {e}")
            continue

    return images
```

Also add `import base64` and `import io` to the imports at the top of the file (they are not yet imported).

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_image_extraction.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add tests/test_image_extraction.py services/admin_endpoints.py
git commit -m "feat: add _extract_and_save_images helper for Docling image extraction"
```

---

### Task 2: Update `_hierarchical_chunk()` to link images to chunks

**Files:**
- Modify: `services/admin_endpoints.py:1181-1238` (`_hierarchical_chunk` function)
- Test: `tests/test_image_extraction.py` (add tests)

**Step 1: Write the failing test**

Add to `tests/test_image_extraction.py`:

```python
def test_hierarchical_chunk_links_images_to_chunks():
    """Images should be linked to chunks based on placeholder positions."""
    from services.admin_endpoints import _hierarchical_chunk

    # Markdown with image placeholders at known positions
    md_text = "First section text here.\n\n<!-- image -->\n\nSecond section after image."
    docling_result = {"md": md_text}

    images = [
        {"image_id": "doc1_page1_img0", "path": "/tmp/img0.jpg", "page": "1"},
    ]

    chunks = _hierarchical_chunk(
        docling_result,
        source_file="test.pdf",
        domain="mold",
        uploaded_by="test",
        images=images,
    )

    assert len(chunks) > 0
    # At least one chunk should have the image linked
    linked = [c for c in chunks if c["metadata"].get("has_images")]
    assert len(linked) >= 1
    assert "doc1_page1_img0" in linked[0]["metadata"]["image_ids"]
    assert linked[0]["metadata"]["image_count"] == 1


def test_hierarchical_chunk_no_images_keeps_has_images_false():
    """Without images, has_images should remain False."""
    from services.admin_endpoints import _hierarchical_chunk

    chunks = _hierarchical_chunk(
        {"md": "Some text content."},
        source_file="test.pdf",
        domain="mold",
        uploaded_by="test",
    )

    assert len(chunks) > 0
    for c in chunks:
        assert c["metadata"]["has_images"] is False
        assert c["metadata"].get("image_ids", []) == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_image_extraction.py::test_hierarchical_chunk_links_images_to_chunks -v`
Expected: FAIL (function doesn't accept `images` parameter yet)

**Step 3: Modify `_hierarchical_chunk`**

Update the function signature and body to accept and link images:

```python
def _hierarchical_chunk(
    docling_result: Dict[str, Any],
    source_file: str,
    domain: str,
    uploaded_by: str,
    max_chunk_size: int = 1000,
    overlap: int = 200,
    images: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """
    Generic hierarchical chunking for non-Excel documents.
    Uses Docling's structured output to respect section boundaries.
    """
    doc = docling_result.get("document", docling_result)
    doc_id = str(uuid.uuid4())

    # Try markdown first
    text = docling_result.get("md", "")
    if not text:
        parts = []
        for item in doc.get("content", []):
            t = item.get("text", "")
            if t:
                parts.append(t)
        text = "\n\n".join(parts)

    if not text:
        return []

    # Map image placeholder positions to images
    image_placeholder = "<!-- image -->"
    placeholder_positions: List[int] = []
    search_start = 0
    while True:
        pos = text.find(image_placeholder, search_start)
        if pos == -1:
            break
        placeholder_positions.append(pos)
        search_start = pos + len(image_placeholder)

    # Build image-to-position mapping
    image_positions: List[tuple] = []  # (char_offset, image_dict)
    if images and placeholder_positions:
        if len(placeholder_positions) == len(images):
            # 1:1 mapping
            for pos, img in zip(placeholder_positions, images):
                image_positions.append((pos, img))
        else:
            # Fallback: all images attached to first chunk
            image_positions = [(0, img) for img in images]
    elif images and not placeholder_positions:
        # No placeholders: all images to first chunk
        image_positions = [(0, img) for img in images]

    # Simple sliding-window chunking
    chunks = []
    start = 0
    chunk_idx = 0
    while start < len(text):
        end = min(start + max_chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            # Find images whose placeholder falls within [start, end)
            chunk_images = [
                img for pos, img in image_positions
                if start <= pos < end
            ]
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "doc_id": doc_id,
                    "source_file": source_file,
                    "file_type": Path(source_file).suffix.lstrip("."),
                    "domain": domain,
                    "chunk_index": chunk_idx,
                    "uploaded_by": uploaded_by,
                    "upload_date": datetime.now(timezone.utc).isoformat(),
                    "processing_method": "docling",
                    "has_images": len(chunk_images) > 0,
                    "image_ids": [img["image_id"] for img in chunk_images],
                    "image_count": len(chunk_images),
                },
            })
            chunk_idx += 1
        start = end - overlap if end < len(text) else end

    # Set total_chunks on all chunks
    for c in chunks:
        c["metadata"]["total_chunks"] = len(chunks)

    return chunks
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_image_extraction.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add services/admin_endpoints.py tests/test_image_extraction.py
git commit -m "feat: link extracted images to chunks via placeholder positions"
```

---

### Task 3: Wire image extraction into upload and URL job pipelines

**Files:**
- Modify: `services/admin_endpoints.py:311-406` (`admin_upload_document` function)
- Modify: `services/admin_endpoints.py:1521-1616` (`_process_url_job` function)

**Step 1: Update `admin_upload_document`**

In the `admin_upload_document` function, after `docling_result = await client.convert_file(...)` and before the chunking step, add image extraction. Then pass the images to `_hierarchical_chunk`.

In the generic chunking branch (the `else` block around line 360):

```python
# Extract images from Docling result
images = _extract_and_save_images(docling_result, doc_id=str(uuid.uuid4()))

# Generic hierarchical chunking
chunks = _hierarchical_chunk(
    docling_result,
    source_file=file.filename or saved_path.name,
    domain=domain,
    uploaded_by=user.get("username", ""),
    images=images,
)
```

Note: The doc_id used for images needs to match the one inside `_hierarchical_chunk`. Since `_hierarchical_chunk` generates its own `doc_id`, we need to generate it before and pass it in. However, to minimize changes, we'll extract images first with a temp doc_id, then after chunking, update the image_ids in chunk metadata to use the real doc_id.

**Simpler approach**: Generate the doc_id outside and pass it into `_hierarchical_chunk`. Add an optional `doc_id` parameter to `_hierarchical_chunk`.

Update `_hierarchical_chunk` signature to accept optional `doc_id`:

```python
def _hierarchical_chunk(
    docling_result: Dict[str, Any],
    source_file: str,
    domain: str,
    uploaded_by: str,
    max_chunk_size: int = 1000,
    overlap: int = 200,
    images: Optional[List[Dict[str, str]]] = None,
    doc_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
```

And change the internal line from:
```python
doc_id = str(uuid.uuid4())
```
to:
```python
doc_id = doc_id or str(uuid.uuid4())
```

Then in `admin_upload_document`:
```python
else:
    doc_id = str(uuid.uuid4())
    images = _extract_and_save_images(docling_result, doc_id=doc_id)
    chunks = _hierarchical_chunk(
        docling_result,
        source_file=file.filename or saved_path.name,
        domain=domain,
        uploaded_by=user.get("username", ""),
        images=images,
        doc_id=doc_id,
    )
```

**Step 2: Update `_process_url_job`**

In `_process_url_job`, after docling conversion and before the chunking stage, add image extraction. Same pattern:

```python
# ----- Stage 2: chunking -----
job["stage"] = "chunking"

chunks: List[Dict[str, Any]] = []
if body.domain == "mold" and ext in (".xlsx", ".xls"):
    extractor = MoldCaseExtractor()
    chunks = extractor.extract(
        docling_result,
        source_file=filename,
        uploaded_by=user.get("username", ""),
    )
else:
    doc_id = str(uuid.uuid4())
    images = _extract_and_save_images(docling_result, doc_id=doc_id)
    chunks = _hierarchical_chunk(
        docling_result,
        source_file=filename,
        domain=body.domain,
        uploaded_by=user.get("username", ""),
        images=images,
        doc_id=doc_id,
    )
```

**Step 3: Run existing tests to verify nothing broke**

Run: `pytest tests/test_image_extraction.py tests/test_url_download.py tests/test_enriched_indexing.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add services/admin_endpoints.py
git commit -m "feat: wire image extraction into upload and URL job pipelines"
```

---

### Task 4: Add `GET /admin/kb/images/{image_id}` endpoint

**Files:**
- Modify: `services/admin_endpoints.py` (add new endpoint)
- Test: `tests/test_image_extraction.py` (add endpoint test)

**Step 1: Write the failing test**

Add to `tests/test_image_extraction.py`:

```python
import io
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_image_endpoint_returns_file(tmp_path):
    """GET /admin/kb/images/{image_id} should return the image file."""
    from PIL import Image

    # Create a test image on disk
    doc_dir = tmp_path / "testdoc123"
    doc_dir.mkdir()
    img_path = doc_dir / "page1_img0.jpg"
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    img.save(img_path, "JPEG")

    from services.admin_endpoints import _resolve_image_path

    with patch("services.admin_endpoints.IMAGE_DIR", tmp_path):
        result = _resolve_image_path("testdoc123_page1_img0")
        assert result is not None
        assert result.exists()


def test_resolve_image_path_returns_none_for_missing():
    """Should return None for unknown image_id."""
    from services.admin_endpoints import _resolve_image_path

    result = _resolve_image_path("nonexistent_page99_img99")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_image_extraction.py::test_image_endpoint_returns_file -v`
Expected: FAIL (function doesn't exist)

**Step 3: Write the endpoint and resolver**

Add to `services/admin_endpoints.py`:

```python
from fastapi.responses import FileResponse


def _resolve_image_path(image_id: str) -> Optional[Path]:
    """Resolve an image_id like 'docid_page1_img0' to its file path."""
    # image_id format: {doc_id}_page{N}_img{M}
    # Find the last occurrence of _page to split doc_id from the rest
    page_match = re.search(r"^(.+)_(page\d+_img\d+)$", image_id)
    if not page_match:
        return None

    doc_id = page_match.group(1)
    filename = page_match.group(2) + ".jpg"

    filepath = IMAGE_DIR / doc_id / filename
    if filepath.exists():
        return filepath

    # Try .bin fallback
    bin_path = IMAGE_DIR / doc_id / (page_match.group(2) + ".bin")
    if bin_path.exists():
        return bin_path

    return None


@router.get("/kb/images/{image_id}")
async def admin_get_image(
    image_id: str,
    user: Dict = Depends(require_permission("view")),
):
    """Serve an extracted document image."""
    filepath = _resolve_image_path(image_id)
    if not filepath:
        raise HTTPException(status_code=404, detail="Image not found")

    media_type = "image/jpeg" if filepath.suffix == ".jpg" else "application/octet-stream"
    return FileResponse(filepath, media_type=media_type)
```

Add `FileResponse` to the imports from `fastapi.responses`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_image_extraction.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add services/admin_endpoints.py tests/test_image_extraction.py
git commit -m "feat: add GET /admin/kb/images/{image_id} authenticated endpoint"
```

---

### Task 5: Update document detail endpoint to return `image_ids`

**Files:**
- Modify: `services/admin_endpoints.py:741-835` (`admin_get_document` function)

**Step 1: Update chunk response**

In `admin_get_document`, the chunk dict construction (around line 815) already includes `has_images` and `image_paths`. Update it to also return `image_ids` and `image_count`:

Change the chunk append block to include:
```python
chunks.append({
    "chunk_index": payload.get("chunk_index", 0),
    "text": payload.get("text", ""),
    "defect_type": payload.get("defect_type", ""),
    "mold_id": payload.get("mold_id", ""),
    "severity": payload.get("severity", ""),
    "has_images": payload.get("has_images", False),
    "image_ids": payload.get("image_ids", []),
    "image_count": payload.get("image_count", 0),
    "image_paths": payload.get("image_paths", []),
    "chunk_type": payload.get("chunk_type", "original"),
    "root_cause_category": payload.get("root_cause_category", ""),
})
```

**Step 2: Run existing tests**

Run: `pytest tests/test_image_extraction.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add services/admin_endpoints.py
git commit -m "feat: return image_ids and image_count in document detail endpoint"
```

---

### Task 6: Frontend — image thumbnails and lightbox in KB browse

**Files:**
- Modify: `frontend/copilot-demo/app/admin/kb/page.tsx`

**Step 1: Add lightbox state**

Add state variables for lightbox:
```typescript
const [lightboxImage, setLightboxImage] = useState<string | null>(null);
```

**Step 2: Add image thumbnails to chunk display**

In the chunk rendering loop (inside the detail modal), after the `<p>` tag that shows `chunk.text`, add:

```tsx
{/* Image thumbnails */}
{(chunk.image_ids as string[] || []).length > 0 && (
  <div className="mt-2 flex gap-2 flex-wrap">
    {(chunk.image_ids as string[]).map((imgId: string) => (
      <button
        key={imgId}
        onClick={() => setLightboxImage(imgId)}
        className="w-20 h-20 rounded-lg overflow-hidden border border-gray-200 hover:border-blue-400 transition-colors flex-shrink-0"
      >
        <img
          src={`${API_BASE}/admin/kb/images/${imgId}`}
          alt={imgId}
          className="w-full h-full object-cover"
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
        />
      </button>
    ))}
  </div>
)}
```

Note: For auth, the image endpoint uses the same admin-token/JWT header. Since `<img>` tags can't send custom headers, use fetch + blob URL pattern instead:

Replace the simple `<img>` with an `ImageThumb` component that fetches with auth:

```tsx
function ImageThumb({ imageId, onClick }: { imageId: string; onClick: () => void }) {
  const [src, setSrc] = useState<string>("");

  useEffect(() => {
    let revoke = "";
    fetch(`${API_BASE}/admin/kb/images/${imageId}`, { headers: getAuthHeaders() })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setSrc(url);
        revoke = url;
      })
      .catch(() => {});
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [imageId]);

  if (!src) return <div className="w-20 h-20 rounded-lg bg-gray-100 animate-pulse" />;

  return (
    <button
      onClick={onClick}
      className="w-20 h-20 rounded-lg overflow-hidden border border-gray-200 hover:border-blue-400 transition-colors flex-shrink-0"
    >
      <img src={src} alt={imageId} className="w-full h-full object-cover" />
    </button>
  );
}
```

**Step 3: Add lightbox modal**

Add the lightbox modal after the detail modal closing `</div>`:

```tsx
{/* Image lightbox */}
{lightboxImage && (
  <div
    className="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center p-8"
    onClick={() => setLightboxImage(null)}
  >
    <div className="relative max-w-4xl max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => setLightboxImage(null)}
        className="absolute -top-10 right-0 text-white hover:text-gray-300"
      >
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
      <ImageFull imageId={lightboxImage} />
    </div>
  </div>
)}
```

With a matching full-size component:

```tsx
function ImageFull({ imageId }: { imageId: string }) {
  const [src, setSrc] = useState<string>("");

  useEffect(() => {
    let revoke = "";
    fetch(`${API_BASE}/admin/kb/images/${imageId}`, { headers: getAuthHeaders() })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setSrc(url);
        revoke = url;
      })
      .catch(() => {});
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [imageId]);

  if (!src) return <div className="w-64 h-64 bg-gray-800 animate-pulse rounded" />;

  return <img src={src} alt={imageId} className="max-w-full max-h-[80vh] rounded-lg shadow-2xl" />;
}
```

**Step 4: Add image count to document metadata in detail modal**

In the metadata grid (around line 400 area), add image count display. Compute it from chunks data:

After the "Source URL" section, add:
```tsx
{(() => {
  const chunks = (detailData as Record<string, unknown>).chunks as Array<Record<string, unknown>> || [];
  const totalImages = chunks.reduce((sum: number, c: Record<string, unknown>) =>
    sum + ((c.image_ids as string[] || []).length), 0);
  return totalImages > 0 ? (
    <div>
      <span className="text-gray-500">Images:</span>{" "}
      <span className="font-medium">{totalImages}</span>
    </div>
  ) : null;
})()}
```

**Step 5: Lint check**

Run: `cd frontend/copilot-demo && npx eslint app/admin/kb/page.tsx`
Expected: No errors (warnings OK)

**Step 6: Commit**

```bash
git add frontend/copilot-demo/app/admin/kb/page.tsx
git commit -m "feat: add image thumbnails and lightbox to KB browse page"
```

---

### Task 7: E2E smoke test for image endpoint

**Files:**
- Modify: `tests/test_url_ingestion_e2e.py` (add test)

**Step 1: Add image endpoint test**

Add to `tests/test_url_ingestion_e2e.py`:

```python
def test_image_endpoint_returns_404_for_missing():
    """GET /admin/kb/images/{nonexistent} should return 404."""
    resp = httpx.get(
        f"{API_BASE}/admin/kb/images/nonexistent_page0_img0",
        headers={"admin-token": "dev"},
        timeout=10,
    )
    assert resp.status_code == 404
```

**Step 2: Run E2E tests**

Run: `pytest tests/test_url_ingestion_e2e.py -v`
Expected: All PASS (including new test, if services are running)

**Step 3: Commit**

```bash
git add tests/test_url_ingestion_e2e.py
git commit -m "test: add E2E smoke test for image endpoint 404 behavior"
```
