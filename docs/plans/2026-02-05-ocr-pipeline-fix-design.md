# OCR Pipeline Fix: Disable Docling RapidOCR + GPU OCR for Page Images

**Date:** 2026-02-05
**Status:** Design

## Problem

The current OCR pipeline has three issues:

1. **Docling's built-in RapidOCR runs by default** on every page image during `DocumentConverter.convert()`, producing endless "RapidOCR returned empty result!" warnings. RapidOCR is a CPU-only lightweight OCR that fails on Chinese content.

2. **GPU GOT-OCR service (P100) never receives requests.** The code attempts to extract images via `result.document.pictures`, but for born-digital PDFs this attribute contains embedded figures/illustrations, not page images. With 0 images extracted, the GPU OCR delegation code never fires.

3. **The P100 GPU is idle.** Health checks pass, the model is loaded, but no actual OCR work arrives.

## Solution

Disable Docling's internal OCR and add PDF-to-image rendering to delegate OCR to the GPU service.

### Architecture

```
PDF Upload -> Docling Service (CPU, port 8085)
  |
  +-- Step 1: Docling converts with do_ocr=False
  |     -> Extracts embedded text, tables, layout -> Markdown
  |     -> No RapidOCR warnings
  |
  +-- Step 2: Render PDF pages as images (pypdfium2)
  |     -> For each page, check if Docling extracted text
  |     -> Pages with < 50 chars of text -> need OCR
  |
  +-- Step 3: Send sparse pages to GOT-OCR (GPU P100, port 8084)
      -> Returns OCR text per page
      -> Merge into final Markdown output
```

## Files Changed

### `services/ocr/doc_parsing_service.py`

1. Configure `DocumentConverter` with `do_ocr=False` via `PdfPipelineOptions`
2. Add `pypdfium2` for PDF page rendering (lightweight, no system deps)
3. After Docling conversion, analyze per-page text coverage
4. Render pages with insufficient text as 300 DPI images
5. POST each image to GPU OCR service at `OCR_SERVICE_URL/ocr`
6. Merge GPU OCR results into the combined output

### `docker/Dockerfile.docling`

1. Add `pypdfium2` to pip install list

### No changes to:

- `got_ocr_service.py` -- already accepts image POST
- `docker-compose.ocr.yml` -- networking already correct
- `mold_document_ingester.py` -- API contract unchanged

## Key Decisions

- **pypdfium2** over pdf2image: No Poppler system dependency, pure Python bindings to PDFium
- **50-char threshold**: Pages with < 50 characters of extracted text get sent to GPU OCR
- **300 DPI rendering**: Good quality for OCR without excessive memory usage
- **Per-page granularity**: Only OCR pages that need it, not the entire document
