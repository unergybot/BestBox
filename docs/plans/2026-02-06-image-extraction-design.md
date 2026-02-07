# Image Extraction Support for Document Ingestion Pipeline

**Date**: 2026-02-06
**Status**: Design

## Summary

Add image extraction to the document ingestion pipeline. Images from PDFs and documents are decoded from Docling's base64 output, saved to disk as JPEG files, linked to their source chunks via `image_ids` metadata, and served through an authenticated API endpoint. The KB browse frontend displays image thumbnails inline with chunk text.

## Goals

1. Save images extracted by Docling to disk instead of dropping them
2. Link images to their source chunks via placeholder-position mapping
3. Serve images through an authenticated endpoint (same RBAC as KB)
4. Display image thumbnails in the KB browse chunk detail view

## Pipeline Flow

```
Docling JSON → _extract_and_save_images()
    → Decode base64, save as JPEG to data/uploads/images/{doc_id}/
    → Return image metadata list

Markdown text → scan for <!-- image --> placeholders
    → Map placeholder positions to images (same order)

_hierarchical_chunk(docling_result, images=image_list)
    → Assign image_ids to chunks based on placeholder positions
    → Set has_images and image_count in chunk metadata

GET /admin/kb/images/{image_id}
    → Resolve image_id to file path
    → Return FileResponse with auth check
```

## Image Storage

**Path**: `data/uploads/images/{doc_id}/page{N}_img{M}.jpg`

**Image ID format**: `{doc_id}_page{N}_img{M}` — globally unique, deterministic.

**Format**: All images converted to JPEG (quality 90) via Pillow for consistency. Original format preserved as fallback if Pillow can't convert.

## Chunk-Image Linking

Images are linked to chunks via `<!-- image -->` placeholders in Docling's markdown output:

1. Scan markdown for `<!-- image -->` positions (character offset)
2. Each placeholder corresponds to an image in Docling's `pictures` array (same order)
3. During chunking, each chunk covers `[start, end]` character range
4. Image is linked to the chunk whose range contains the placeholder
5. Fallback: if placeholder count != image count, attach all images at doc level

**Chunk metadata additions**:
```json
{
  "image_ids": ["doc1_page2_img0", "doc1_page3_img1"],
  "has_images": true,
  "image_count": 1
}
```

## Image Serving Endpoint

### `GET /admin/kb/images/{image_id}`

- Auth: `require_permission("view")`
- Parses doc_id from image_id prefix
- Resolves to `data/uploads/images/{doc_id}/{filename}.jpg`
- Returns `FileResponse` with `media_type="image/jpeg"`
- 404 if image not found

## Frontend Changes

### KB Browse Page (`app/admin/kb/page.tsx`)

**Chunk display**: When chunk has `image_ids`, render 80x80px thumbnails below text:
- `object-cover` with rounded corners
- Click opens lightbox modal with full-size image
- Images loaded via `${API_BASE}/admin/kb/images/{image_id}` with auth headers
- Graceful fallback if image fails to load

**Document metadata**: Show image count alongside chunk count.

## Files Changed

| File | Change |
|------|--------|
| `services/admin_endpoints.py` | Add `_extract_and_save_images()`, add `GET /admin/kb/images/{image_id}`, update `_hierarchical_chunk()` to accept images param and link to chunks, update `admin_upload_document` and `_process_url_job` to call extraction |
| `frontend/.../app/admin/kb/page.tsx` | Image thumbnails in chunks, lightbox modal, image count |

## Dependencies

- `Pillow` (already installed) — image decoding and JPEG conversion
- No new packages required

## Error Handling

- No images in Docling result → empty list, `has_images: False` as before
- Base64 decode failure → skip image, log warning, continue
- Unrecognized format → save raw bytes with original extension
- Image endpoint unknown ID → 404
