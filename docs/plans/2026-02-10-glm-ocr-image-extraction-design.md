# GLM-OCR Image Extraction & Preview Design

**Date:** 2026-02-10
**Author:** Claude Sonnet 4.5
**Status:** Approved for Implementation

## Executive Summary

Extend the GLM-OCR pipeline to extract image regions from PDFs during upload and render them in the Knowledge Base viewer. Currently, GLM-OCR identifies image locations with bounding boxes (`![](page=N,bbox=[...])`) but doesn't extract the actual pixels. This design adds automatic image extraction, storage, and preview capabilities.

**Key Benefits:**
- ✅ Rich document preview with actual images, not just placeholders
- ✅ Better knowledge base browsing experience
- ✅ Leverages existing GLM-SDK JSON output
- ✅ Minimal architectural changes

## 1. Architecture Overview

### Current State

**Upload Flow:**
```
PDF Upload → GLM-SDK → markdown + JSON → Chunking → Qdrant
                         (bbox coords)    (placeholders)
```

GLM-SDK returns:
- `markdown_result`: Text with `![](page=N,bbox=[x1,y1,x2,y2])` placeholders
- `json_result`: Structured layout data with bbox coordinates and labels

**Problem:** Images are identified but not extracted. KB viewer shows raw markdown placeholders.

### Proposed Architecture

**Enhanced Upload Flow:**
```
PDF Upload → GLM-SDK → markdown + JSON → Extract Images → Replace Placeholders → Chunking → Qdrant
                         ↓                     ↓                                      ↓
                    Store JSON          Crop from PDF                           Image IDs in chunks
                                       Save as PNG files
```

**New Components:**
1. **Image Extractor** - Crops bbox regions from PDF using PyMuPDF
2. **Image Storage** - Filesystem-based organized by collection/doc
3. **Image Server** - API endpoint to serve extracted images
4. **Markdown Processor** - Replaces bbox placeholders with image IDs
5. **Frontend Renderer** - Displays images in KB viewer

### Design Decisions

| Decision | Chosen Approach | Rationale |
|----------|----------------|-----------|
| **When to extract** | During upload (sync) | Immediate complete results, acceptable 2-5s overhead |
| **Where to store** | Filesystem (`data/uploads/images/`) | Simple, consistent with current architecture |
| **Placeholder format** | `<!-- image:pN_imgX -->` | Matches existing KB page pattern (line 95) |
| **Image format** | PNG | Lossless quality for diagrams, tables, charts |
| **Storage organization** | `{collection}/{doc_id}/pN_imgX.png` | Hierarchical, easy cleanup, namespaced |

## 2. Image Extraction Logic

### Core Algorithm

```python
async def _extract_images_from_pdf(
    pdf_path: Path,
    json_result: List[List[Dict]],
    doc_id: str,
    collection: str
) -> Dict[str, Dict]:
    """
    Extract image regions from PDF using bbox coordinates.

    Args:
        pdf_path: Path to source PDF
        json_result: GLM-SDK JSON output with layout data
        doc_id: Document identifier
        collection: Collection name

    Returns:
        Image manifest: {"p0_img0": {"page": 0, "bbox": [...], "file": "p0_img0.png"}, ...}
    """
    import fitz  # PyMuPDF

    # Create output directory
    image_dir = Path("data/uploads/images") / collection / doc_id
    image_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    pdf_doc = fitz.open(pdf_path)

    try:
        for page_elements in json_result:
            for element in page_elements:
                # Only process image elements
                if element.get("label") != "image":
                    continue

                page_num = element.get("page", 0)  # Default to 0 if not specified
                bbox = element["bbox_2d"]  # [x1, y1, x2, y2]

                # Generate image ID
                img_count = len([k for k in manifest if k.startswith(f"p{page_num}_")])
                image_id = f"p{page_num}_img{img_count}"

                # Crop region from PDF
                page = pdf_doc[page_num]

                # fitz uses (x0, y0, x1, y1) format - same as bbox_2d
                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])

                # Render region to pixmap (200 DPI for quality)
                pix = page.get_pixmap(clip=rect, dpi=200)

                # Save as PNG
                output_path = image_dir / f"{image_id}.png"
                pix.save(str(output_path))

                # Add to manifest
                manifest[image_id] = {
                    "page": page_num,
                    "bbox": bbox,
                    "file": f"{image_id}.png",
                    "width": pix.width,
                    "height": pix.height
                }

                logger.info(f"Extracted {image_id}: {pix.width}x{pix.height}px from page {page_num}")

    finally:
        pdf_doc.close()

    return manifest
```

### Markdown Placeholder Replacement

```python
def _replace_image_placeholders(markdown: str, manifest: Dict[str, Dict]) -> str:
    """
    Replace bbox placeholders with image IDs.

    Before: ![](page=0,bbox=[45, 107, 272, 468])
    After:  <!-- image:p0_img0 -->
    """
    import re

    # Pattern: ![](page=N,bbox=[x1, y1, x2, y2])
    pattern = r'!\[\]\(page=(\d+),bbox=\[([^\]]+)\]\)'

    # Track which images we've used
    image_index_per_page = {}

    def replace_match(match):
        page = int(match.group(1))
        bbox_str = match.group(2)

        # Find corresponding image ID
        if page not in image_index_per_page:
            image_index_per_page[page] = 0

        img_idx = image_index_per_page[page]
        image_id = f"p{page}_img{img_idx}"
        image_index_per_page[page] += 1

        # Verify image exists in manifest
        if image_id in manifest:
            return f"<!-- image:{image_id} -->"
        else:
            # Fallback if extraction failed
            logger.warning(f"Image {image_id} not in manifest, keeping placeholder")
            return match.group(0)

    return re.sub(pattern, replace_match, markdown)
```

### Integration into Upload Pipeline

**Modify `_process_with_glm_ocr()` in `services/admin_endpoints.py`:**

```python
async def _process_with_glm_ocr(pdf_path: Path, domain: str) -> tuple[Dict[str, Any], Dict[str, int], float]:
    # ... existing GLM-SDK call ...

    result = response.json()
    markdown = result.get("markdown_result", "")
    json_result = result.get("json_result", [])  # NEW: capture JSON

    # NEW: Extract images
    doc_id = pdf_path.stem  # Use filename as doc_id for now
    image_manifest = await _extract_images_from_pdf(
        pdf_path=pdf_path,
        json_result=json_result,
        doc_id=doc_id,
        collection=domain
    )

    # NEW: Replace placeholders
    markdown = _replace_image_placeholders(markdown, image_manifest)

    layout_stats = _extract_layout_stats(markdown)
    processing_time = time.monotonic() - start_time

    # Enhanced result
    docling_result = {
        "md": markdown,
        "document": {"content": [{"text": markdown}]},
        "pictures": [],  # Keep empty for compatibility
        "metadata": {
            "domain": domain,
            "source": str(pdf_path),
            "json_result": json_result,        # NEW: store full JSON
            "image_manifest": image_manifest   # NEW: store image mapping
        },
    }

    return docling_result, layout_stats, processing_time
```

## 3. Storage & File Organization

### Filesystem Structure

```
data/uploads/
├── pdfs/
│   └── {collection}/
│       └── {doc_id}.pdf
├── images/                              ← NEW
│   └── {collection}/                    ← NEW
│       └── {doc_id}/                    ← NEW
│           ├── p0_img0.png              ← NEW: page 0, image 0
│           ├── p0_img1.png              ← NEW: page 0, image 1
│           ├── p4_img0.png              ← NEW: page 4, image 0
│           └── metadata.json            ← NEW: image manifest
└── metadata/                            ← NEW (optional)
    └── {collection}/                    ← NEW
        └── {doc_id}.json                ← NEW: full GLM-SDK JSON result
```

### Image Naming Convention

**Format:** `p{page}_img{index}.png`

- `page`: Zero-indexed page number
- `index`: Sequential index of images on that page (order from JSON)
- Extension: Always `.png` for consistency

**Examples:**
- `p0_img0.png` - First image on page 0
- `p0_img1.png` - Second image on page 0
- `p4_img0.png` - First image on page 4

### Metadata Storage

**Option 1: Sidecar JSON file (Recommended)**

Store `data/uploads/images/{collection}/{doc_id}/metadata.json`:

```json
{
  "doc_id": "ppd407",
  "collection": "mold_reference_kb",
  "source_pdf": "ppd407.pdf",
  "extracted_at": "2026-02-10T17:30:00Z",
  "total_images": 25,
  "images": {
    "p0_img0": {
      "page": 0,
      "bbox": [45, 107, 272, 468],
      "file": "p0_img0.png",
      "width": 454,
      "height": 722,
      "format": "PNG"
    },
    "p0_img1": {
      "page": 0,
      "bbox": [42, 555, 272, 877],
      "file": "p0_img1.png",
      "width": 460,
      "height": 644,
      "format": "PNG"
    }
  }
}
```

**Option 2: PostgreSQL table**

For production scale, store in database:

```sql
CREATE TABLE IF NOT EXISTS document_images (
    id SERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL,
    collection TEXT NOT NULL,
    image_id TEXT NOT NULL,  -- p0_img0
    page_num INTEGER NOT NULL,
    bbox_x1 INTEGER NOT NULL,
    bbox_y1 INTEGER NOT NULL,
    bbox_x2 INTEGER NOT NULL,
    bbox_y2 INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    extracted_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(doc_id, image_id)
);

CREATE INDEX idx_document_images_doc ON document_images(doc_id, collection);
```

**Recommendation:** Start with Option 1 (sidecar JSON) for simplicity. Migrate to Option 2 if scale demands it.

## 4. Database Schema & Metadata

### Chunk Metadata Enhancement

When storing chunks in Qdrant, include image references:

```python
# Current chunk payload
{
    "text": "chunk text with <!-- image:p0_img0 --> placeholder",
    "doc_id": "ppd407",
    "chunk_index": 0,
    "source_file": "ppd407.pdf",
    "domain": "mold"
}

# Enhanced chunk payload
{
    "text": "chunk text with <!-- image:p0_img0 --> placeholder",
    "doc_id": "ppd407",
    "chunk_index": 0,
    "source_file": "ppd407.pdf",
    "domain": "mold",
    "collection": "mold_reference_kb",       # NEW
    "image_ids": ["p0_img0"],                # NEW: list of image IDs in this chunk
    "has_images": true                        # NEW: quick filter flag
}
```

### Document Metadata Table

Optionally extend the existing `documents` table (if using PostgreSQL for doc tracking):

```sql
ALTER TABLE documents ADD COLUMN image_count INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN image_manifest JSONB;  -- Store manifest directly
ALTER TABLE documents ADD COLUMN glm_json_result JSONB;  -- Store full GLM output
```

Or keep it simple with filesystem-only storage initially.

## 5. API Endpoints

### New Endpoint: Serve Images

**Endpoint:** `GET /admin/kb/images/{collection}/{doc_id}/{image_id}`

**Purpose:** Serve extracted image files with proper caching

**Implementation:**

```python
from fastapi import HTTPException
from fastapi.responses import FileResponse
import os

@app.get("/admin/kb/images/{collection}/{doc_id}/{image_id}")
async def get_document_image(collection: str, doc_id: str, image_id: str):
    """
    Serve extracted document image.

    Example: GET /admin/kb/images/mold_reference_kb/ppd407/p0_img0
    Returns: PNG image file
    """
    # Validate image_id format (security)
    import re
    if not re.match(r'^p\d+_img\d+$', image_id):
        raise HTTPException(400, "Invalid image_id format")

    # Construct file path
    image_path = (
        Path("data/uploads/images") / collection / doc_id / f"{image_id}.png"
    )

    # Check existence
    if not image_path.exists():
        raise HTTPException(404, f"Image not found: {image_id}")

    # Serve with caching headers
    return FileResponse(
        path=image_path,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",  # 24 hour cache
            "ETag": f'"{image_id}"'
        }
    )
```

**Security Considerations:**
- ✅ Validate `image_id` format with regex (prevent path traversal)
- ✅ Check `collection` and `doc_id` against allowed values
- ✅ Add authentication check (reuse existing admin auth)
- ✅ Rate limiting if needed

### Enhanced Endpoint: Document Detail

**Endpoint:** `GET /admin/kb/documents/{doc_id}`

**Enhancement:** Include image manifest in response

```python
@app.get("/admin/kb/documents/{doc_id}")
async def get_document_detail(doc_id: str, collection: str):
    # ... existing logic ...

    # NEW: Load image manifest if exists
    manifest_path = Path("data/uploads/images") / collection / doc_id / "metadata.json"
    image_manifest = {}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest_data = json.load(f)
            image_manifest = manifest_data.get("images", {})

    return {
        "doc_id": doc_id,
        "source_file": source_file,
        # ... other fields ...
        "chunks": chunks,
        "image_manifest": image_manifest,  # NEW
        "total_images": len(image_manifest)  # NEW
    }
```

## 6. Frontend Integration

### KB Page Enhancement

**File:** `frontend/copilot-demo/app/[locale]/admin/kb/page.tsx`

The KB page already has infrastructure for images (lines 44-112):
- `ImageThumb` component
- `ImageFull` component
- `InlineImage` component
- `ChunkContent` component with `<!-- image -->` placeholder handling

**Required Changes:**

1. **Update image fetching logic** (lines 48, 66, 80):

```typescript
// BEFORE: Fetches from non-existent endpoint
fetch(`${API_BASE}/admin/kb/images/${imageId}`, ...)

// AFTER: Use new endpoint with collection and doc_id
fetch(`${API_BASE}/admin/kb/images/${collection}/${docId}/${imageId}`, ...)
```

2. **Parse image IDs from chunks:**

```typescript
// In openDetail function, parse chunks for image IDs
const chunks = detailData.chunks.map(chunk => {
  const imageIds: string[] = [];
  const text = chunk.text as string;

  // Extract image IDs: <!-- image:p0_img0 -->
  const matches = text.matchAll(/<!-- image:([^ ]+) -->/g);
  for (const match of matches) {
    imageIds.push(match[1]);
  }

  return {
    ...chunk,
    image_ids: imageIds
  };
});
```

3. **Update ChunkContent component** (line 94):

```typescript
function ChunkContent({
  text,
  collection,  // NEW
  docId,       // NEW
  onImageClick
}: {
  text: string;
  collection: string;  // NEW
  docId: string;       // NEW
  onImageClick: (id: string) => void
}) {
  const placeholder = "<!-- image:";

  // Split by image placeholders
  const parts = text.split(/<!-- image:([^ ]+) -->/);

  if (parts.length === 1) {
    return <p className="text-gray-800 whitespace-pre-wrap">{text}</p>;
  }

  return (
    <div className="text-gray-800">
      {parts.map((part, index) => {
        // Even indices are text, odd indices are image IDs
        if (index % 2 === 0) {
          return <span key={index} className="whitespace-pre-wrap">{part}</span>;
        } else {
          const imageId = part;
          return (
            <InlineImage
              key={index}
              collection={collection}  // NEW
              docId={docId}            // NEW
              imageId={imageId}
              onClick={() => onImageClick(imageId)}
            />
          );
        }
      })}
    </div>
  );
}
```

4. **Update image components to accept collection and docId:**

```typescript
function InlineImage({
  collection,
  docId,
  imageId,
  onClick
}: {
  collection: string;
  docId: string;
  imageId: string;
  onClick: () => void
}) {
  const [src, setSrc] = useState<string>("");

  useEffect(() => {
    let revoke = "";
    // NEW: Include collection and docId in URL
    fetch(
      `${API_BASE}/admin/kb/images/${collection}/${docId}/${imageId}`,
      { headers: getAuthHeaders() }
    )
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setSrc(url);
        revoke = url;
      })
      .catch(() => {});
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [collection, docId, imageId]);

  // ... rest unchanged ...
}
```

### Table Rendering

GLM-OCR returns tables as HTML (`<table border="1">...</table>`). To render them safely:

**Recommended: Use react-markdown with rehype-raw**

```bash
npm install react-markdown rehype-raw rehype-sanitize
```

```typescript
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';

function ChunkContent({ text, ... }) {
  return (
    <ReactMarkdown
      rehypePlugins={[rehypeRaw, rehypeSanitize]}
      className="prose prose-sm max-w-none"
    >
      {text}
    </ReactMarkdown>
  );
}
```

**Security Note:** Always use `rehype-sanitize` to prevent XSS attacks. Never use `dangerouslySetInnerHTML` with untrusted content from GLM-OCR, as it could contain malicious HTML. The `rehype-sanitize` plugin automatically strips dangerous tags and attributes while preserving safe HTML like tables.

## 7. Error Handling & Edge Cases

### Image Extraction Failures

**Scenario:** PyMuPDF fails to crop a bbox region

**Handling:**
```python
try:
    pix = page.get_pixmap(clip=rect, dpi=200)
    pix.save(str(output_path))
    manifest[image_id] = {...}
except Exception as e:
    logger.warning(f"Failed to extract {image_id}: {e}")
    # Continue processing other images
    continue
```

**Result:** Partial extraction - some images succeed, failed ones keep placeholders

### Missing Images in Viewer

**Scenario:** Image file deleted but metadata references it

**Handling:**
- API endpoint returns 404
- Frontend shows placeholder or broken image icon
- Add "Reindex" button to re-extract images from PDF

### Large PDFs

**Scenario:** PDF with 100+ images causes slow upload

**Mitigation:**
1. **Progress indicator:** Update frontend to show "Extracting images... 15/25"
2. **Timeout:** Set reasonable GLM-SDK timeout (already configurable)
3. **Limit:** Warn users about PDFs > 50 pages (existing in code)

### Disk Space Management

**Scenario:** Images accumulate and fill disk

**Solutions:**
1. **Cleanup on document delete:** Remove image directory when doc deleted
2. **Periodic cleanup:** Cron job to remove orphaned images
3. **Monitoring:** Track disk usage in Grafana

```python
async def delete_document(doc_id: str, collection: str):
    # ... existing deletion logic ...

    # NEW: Clean up image directory
    image_dir = Path("data/uploads/images") / collection / doc_id
    if image_dir.exists():
        shutil.rmtree(image_dir)
        logger.info(f"Deleted images for {doc_id}")
```

### Invalid Bbox Coordinates

**Scenario:** GLM-SDK returns out-of-bounds bbox

**Handling:**
```python
# Validate bbox before cropping
page_rect = page.rect
if not page_rect.contains(rect):
    logger.warning(f"Bbox {bbox} out of bounds for page {page_num}, clipping")
    rect = rect.intersect(page_rect)  # Clip to page boundaries
```

### Concurrent Uploads

**Scenario:** Two users upload same doc_id simultaneously

**Handling:**
- Use unique doc_id (timestamp + UUID): `ppd407_20260210_a3f7b9c2`
- Or add file locking during image extraction
- Or use transaction-safe database storage (Option 2 from Section 3)

## 8. Testing Strategy

### Unit Tests

**File:** `tests/test_image_extraction.py`

```python
import pytest
from pathlib import Path
from services.admin_endpoints import _extract_images_from_pdf, _replace_image_placeholders

@pytest.fixture
def sample_json_result():
    return [[
        {
            "bbox_2d": [45, 107, 272, 468],
            "label": "image",
            "index": 0,
            "page": 0
        },
        {
            "bbox_2d": [42, 555, 272, 877],
            "label": "image",
            "index": 1,
            "page": 0
        }
    ]]

@pytest.fixture
def sample_markdown():
    return """## Discoloration

![](page=0,bbox=[45, 107, 272, 468])

<table>...</table>

![](page=0,bbox=[42, 555, 272, 877])"""

def test_extract_images_from_pdf(sample_json_result, tmp_path):
    """Test image extraction from PDF."""
    pdf_path = Path("docs/ppd407.pdf")

    manifest = await _extract_images_from_pdf(
        pdf_path=pdf_path,
        json_result=sample_json_result,
        doc_id="test_doc",
        collection="test"
    )

    assert len(manifest) == 2
    assert "p0_img0" in manifest
    assert "p0_img1" in manifest
    assert manifest["p0_img0"]["page"] == 0
    assert manifest["p0_img0"]["bbox"] == [45, 107, 272, 468]

    # Check files exist
    image_dir = Path("data/uploads/images/test/test_doc")
    assert (image_dir / "p0_img0.png").exists()
    assert (image_dir / "p0_img1.png").exists()

def test_replace_image_placeholders(sample_markdown):
    """Test markdown placeholder replacement."""
    manifest = {
        "p0_img0": {"page": 0, "bbox": [45, 107, 272, 468], "file": "p0_img0.png"},
        "p0_img1": {"page": 0, "bbox": [42, 555, 272, 877], "file": "p0_img1.png"}
    }

    result = _replace_image_placeholders(sample_markdown, manifest)

    assert "![](page=0,bbox=" not in result
    assert "<!-- image:p0_img0 -->" in result
    assert "<!-- image:p0_img1 -->" in result
    assert "<table>" in result  # Tables unchanged

def test_placeholder_replacement_with_missing_image(sample_markdown):
    """Test handling of missing images in manifest."""
    manifest = {"p0_img0": {...}}  # Only first image

    result = _replace_image_placeholders(sample_markdown, manifest)

    assert "<!-- image:p0_img0 -->" in result
    # Second placeholder should remain unchanged
    assert "![](page=0,bbox=[42, 555, 272, 877])" in result
```

### Integration Tests

**File:** `tests/test_glm_ocr_integration.py`

```python
import pytest
import httpx
from pathlib import Path

@pytest.mark.asyncio
async def test_upload_with_image_extraction():
    """Test full upload pipeline with image extraction."""
    pdf_path = Path("docs/ppd407.pdf")

    async with httpx.AsyncClient() as client:
        # Upload PDF
        with open(pdf_path, "rb") as f:
            response = await client.post(
                "http://localhost:8000/admin/documents/upload",
                params={
                    "collection": "test_kb",
                    "domain": "test",
                    "ocr_engine": "glm-ocr"
                },
                files={"file": ("ppd407.pdf", f, "application/pdf")}
            )

        assert response.status_code == 200
        result = response.json()

        # Verify layout stats
        assert result["layout_detected"]["images"] > 0
        assert result["layout_detected"]["tables"] > 0

        # Verify image files created
        doc_id = result.get("doc_id", "ppd407")
        image_dir = Path("data/uploads/images/test_kb") / doc_id
        assert image_dir.exists()

        image_files = list(image_dir.glob("p*.png"))
        assert len(image_files) == result["layout_detected"]["images"]

@pytest.mark.asyncio
async def test_image_endpoint():
    """Test image serving endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/admin/kb/images/mold_reference_kb/ppd407/p0_img0",
            headers={"admin-token": "test_token"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 0

@pytest.mark.asyncio
async def test_document_detail_with_images():
    """Test document detail includes image manifest."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/admin/kb/documents/ppd407",
            params={"collection": "mold_reference_kb"},
            headers={"admin-token": "test_token"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "image_manifest" in data
        assert data["total_images"] > 0
        assert "chunks" in data

        # Verify chunks contain image IDs
        for chunk in data["chunks"]:
            if "<!-- image:" in chunk["text"]:
                assert "image_ids" in chunk
                assert len(chunk["image_ids"]) > 0
```

### Manual Testing Checklist

- [ ] Upload PDF with images via admin documents page
- [ ] Verify "Layout detected" shows correct image count
- [ ] Open document in KB viewer
- [ ] Verify images display inline (not placeholders)
- [ ] Click image to view fullscreen lightbox
- [ ] Verify tables render as HTML tables (not markdown)
- [ ] Test with PDF with 0 images (should still work)
- [ ] Test with PDF with 50+ images (check performance)
- [ ] Delete document and verify images cleaned up
- [ ] Search KB and verify results include image IDs
- [ ] Test image endpoint 404 handling (non-existent image)
- [ ] Verify caching headers work (check browser dev tools)

## 9. Implementation Checklist

### Phase 1: Backend Image Extraction (Day 1)

- [ ] **Create image extraction function** (`_extract_images_from_pdf`)
  - [ ] Parse JSON result for image elements
  - [ ] Crop bbox regions with PyMuPDF
  - [ ] Save as PNG to organized directory
  - [ ] Generate image manifest
  - [ ] Handle errors gracefully

- [ ] **Create placeholder replacement function** (`_replace_image_placeholders`)
  - [ ] Regex to match `![](page=N,bbox=[...])`
  - [ ] Replace with `<!-- image:pN_imgX -->`
  - [ ] Preserve order and mapping

- [ ] **Integrate into upload pipeline** (`_process_with_glm_ocr`)
  - [ ] Call extraction after GLM-SDK response
  - [ ] Call placeholder replacement
  - [ ] Store manifest in metadata
  - [ ] Update return structure

- [ ] **Add image serving endpoint**
  - [ ] Create `GET /admin/kb/images/{collection}/{doc_id}/{image_id}`
  - [ ] Validate parameters (security)
  - [ ] Serve file with caching headers
  - [ ] Add authentication check

- [ ] **Add cleanup on delete**
  - [ ] Delete image directory when document deleted
  - [ ] Log cleanup actions

### Phase 2: Frontend Integration (Day 1-2)

- [ ] **Update image components**
  - [ ] Add `collection` and `docId` props
  - [ ] Update fetch URLs
  - [ ] Test image loading

- [ ] **Update ChunkContent component**
  - [ ] Parse `<!-- image:ID -->` placeholders
  - [ ] Pass collection and docId to InlineImage
  - [ ] Handle mixed text and images

- [ ] **Add table rendering**
  - [ ] Install react-markdown + rehype-raw + rehype-sanitize
  - [ ] Configure markdown renderer
  - [ ] Style tables with Tailwind prose

- [ ] **Enhance document detail**
  - [ ] Display image count in header
  - [ ] Show image manifest metadata
  - [ ] Add image thumbnails section (optional)

### Phase 3: Testing & Refinement (Day 2)

- [ ] **Write unit tests**
  - [ ] Test image extraction logic
  - [ ] Test placeholder replacement
  - [ ] Test edge cases

- [ ] **Write integration tests**
  - [ ] Test full upload pipeline
  - [ ] Test image endpoint
  - [ ] Test document detail

- [ ] **Manual testing**
  - [ ] Run through testing checklist
  - [ ] Test with various PDFs
  - [ ] Performance testing with large PDFs

- [ ] **Documentation**
  - [ ] Update CLAUDE.md
  - [ ] Add API documentation
  - [ ] Create user guide

### Phase 4: Deployment & Monitoring (Day 3)

- [ ] **Create migration script**
  - [ ] Re-extract images for existing GLM-OCR documents
  - [ ] Run on mold_reference_kb collection

- [ ] **Add monitoring**
  - [ ] Track image extraction failures
  - [ ] Monitor disk usage
  - [ ] Add Grafana dashboard panel

- [ ] **Performance optimization**
  - [ ] Add image compression if needed
  - [ ] Tune DPI settings
  - [ ] Add rate limiting if needed

## 10. Performance Considerations

### Image Extraction Performance

**Estimated overhead per PDF:**
- 30 images × 0.1s per crop = **3s**
- Acceptable for 72s total GLM-SDK processing time

**Optimization opportunities:**
1. Parallel extraction (use `asyncio.gather`)
2. Lower DPI for large images (trade quality for speed)
3. Progressive JPEG for photos (smaller files)

### Storage Estimates

**Per document:**
- Average image: 50KB (diagrams/charts at 200 DPI)
- 25 images × 50KB = **1.25 MB per document**

**For 1000 documents:**
- 1000 × 1.25 MB = **1.25 GB**

**Mitigation:**
- Image compression (use PIL optimize=True)
- Periodic cleanup of unused docs
- Monitor with Grafana disk usage alerts

### API Performance

**Image serving:**
- Static file serving is fast (<10ms)
- Caching headers reduce repeated requests
- Consider nginx reverse proxy for static assets in production

## 11. Future Enhancements

### Phase 2 (Post-MVP)

1. **Image Search**
   - Extract image embeddings (CLIP)
   - Enable "find similar images" queries
   - Visual search in KB

2. **OCR on Images**
   - Run GLM-OCR on extracted image regions
   - Extract text from diagrams
   - Enable full-text search within images

3. **Image Annotations**
   - Allow users to add notes/highlights to images
   - Store annotations in metadata
   - Display in viewer

4. **Thumbnail Generation**
   - Generate small thumbnails (100x100) for faster loading
   - Use for document preview cards
   - Lazy load full resolution

5. **WebP Format**
   - Convert to WebP for better compression
   - Fall back to PNG for compatibility
   - Reduce storage by 30-50%

### Production Readiness

1. **Database Migration**
   - Move from filesystem to PostgreSQL (Section 3, Option 2)
   - Add proper indexing
   - Enable transactional guarantees

2. **CDN Integration**
   - Upload to S3-compatible storage
   - Serve via CloudFront/CDN
   - Reduce server load

3. **Background Processing**
   - Migrate to async task queue (Celery)
   - Non-blocking uploads
   - Retry logic for failures

4. **Multi-tenant Support**
   - Isolate images by organization
   - Implement quotas
   - Add billing integration

## 12. Success Metrics

**Technical Metrics:**
- ✅ Image extraction success rate > 95%
- ✅ Upload time increase < 5s per document
- ✅ API response time < 100ms for image serving
- ✅ Zero data loss (all images recoverable from PDF)

**User Experience Metrics:**
- ✅ KB document views with images > 80% of total views
- ✅ User feedback: "Much better than raw markdown"
- ✅ Search quality improvement (images provide context)

**Operational Metrics:**
- ✅ Disk usage < 2GB for 1000 documents
- ✅ Zero security incidents (path traversal, etc.)
- ✅ Uptime 99.9% for image endpoint

## 13. Dependencies

**Python Libraries:**
- `PyMuPDF` (fitz) - Already installed for PDF rendering
- `Pillow` (PIL) - Already installed for image handling

**Frontend Libraries:**
- `react-markdown` - For markdown rendering
- `rehype-raw` - For HTML in markdown
- `rehype-sanitize` - **Critical for security** - prevents XSS

**No new services required** - everything works with existing infrastructure.

---

**End of Design Document**

**Next Steps:**
1. Review and approve this design
2. Create implementation plan (3-day sprint)
3. Set up git worktree for isolated development
4. Begin Phase 1: Backend implementation
