# GLM-OCR Admin Upload Integration Design

**Date:** 2026-02-10
**Status:** Design Complete
**Owner:** BestBox Team

## Overview

Integrate GLM-OCR with GPU-accelerated layout detection as an explicit OCR engine option in the admin documents upload page. Users can select "GLM-OCR (GPU + Layout)" to leverage RTX 3080 for advanced document processing with table extraction, image detection, and structured markdown output.

## Goals

1. **Primary:** Expose GLM-OCR as a user-selectable OCR engine with full layout detection capabilities
2. **Transparency:** Show users what layout features were detected (tables, images, sections)
3. **Performance:** Direct GLM-SDK integration bypassing quality gate for predictable processing
4. **Value Clarity:** Demonstrate GLM-OCR's unique features to justify GPU cost

## Non-Goals

- Replacing the existing quality gate system (keep for automatic escalation)
- Changing behavior of existing OCR engines (easyocr, tesseract, rapidocr)
- Real-time layout visualization (future enhancement)

## Current State

### Existing Architecture

```
PDF Upload → admin_upload_document()
  ├─> MoldDocumentIngester
  │   └─> Docling Service (port 8085)
  │       ├─> P100 OCR (classical)
  │       └─> Quality Gate → GLM-OCR fallback (conditional)
  └─> Chunking → Qdrant indexing
```

### Existing OCR Flow

1. **Frontend:** User selects `easyocr`, `tesseract`, or `rapidocr`
2. **Backend:** For PDFs, routes through Docling service with quality gate
3. **Docling:** Uses P100 OCR, escalates to GLM-OCR only if quality is poor
4. **Result:** Generic text extraction, no layout information

### Limitations

- GLM-OCR only triggered automatically via quality gate
- Layout detection capabilities hidden from users
- No visibility into tables, images, or structure extracted
- Users can't choose GLM-OCR explicitly

## Proposed Architecture

### New GLM-OCR Path

```
PDF Upload with ocr_engine="glm-ocr"
  ↓
admin_upload_document() detects GLM-OCR
  ↓
Direct GLM-SDK call (bypass Docling)
  ↓
GLM-SDK (port 5002) /glmocr/parse
  ├─> Layout Detection (PP-DocLayoutV3)
  ├─> GLM-Transformers OCR (port 11436)
  └─> Structured Markdown Output
  ↓
Parse layout metadata (tables, images, headers)
  ↓
Return enhanced response with layout stats
  ↓
Frontend displays rich results
```

### Component Integration

```
┌─────────────────────────────────────────────┐
│ Frontend (documents/page.tsx)               │
│ - Dropdown: "GLM-OCR (GPU + Layout)"       │
│ - Enhanced result display                   │
└─────────────────┬───────────────────────────┘
                  │ POST /admin/documents/upload
                  │ ocr_engine="glm-ocr"
┌─────────────────▼───────────────────────────┐
│ Backend (admin_endpoints.py)                │
│ - Route detection: if ocr_engine="glm-ocr" │
│ - Direct GLM-SDK call                       │
│ - Layout metadata parsing                   │
└─────────────────┬───────────────────────────┘
                  │ POST /glmocr/parse
                  │ {"images": ["/app/shared/doc.pdf"]}
┌─────────────────▼───────────────────────────┐
│ GLM-SDK Service (port 5002)                 │
│ - PP-DocLayoutV3 layout detection          │
│ - GLM-Transformers OCR                      │
│ - Structured markdown generation            │
└─────────────────┬───────────────────────────┘
                  │ Returns markdown + metadata
┌─────────────────▼───────────────────────────┐
│ Response Enhancement                         │
│ - Parse markdown for layout features        │
│ - Count tables, images, headers             │
│ - Add processing metadata                   │
└─────────────────────────────────────────────┘
```

## Design Details

### Frontend Changes

#### 1. OCR Engine Dropdown Enhancement

**File:** `frontend/copilot-demo/app/[locale]/admin/documents/page.tsx`

**Current (lines 280-290):**
```typescript
<select value={ocrEngine} onChange={(e) => setOcrEngine(e.target.value)}>
  <option value="easyocr">EasyOCR</option>
  <option value="tesseract">Tesseract</option>
  <option value="rapidocr">RapidOCR</option>
</select>
```

**Proposed:**
```typescript
<select value={ocrEngine} onChange={(e) => setOcrEngine(e.target.value)}>
  <option value="easyocr">EasyOCR</option>
  <option value="tesseract">Tesseract</option>
  <option value="rapidocr">RapidOCR</option>
  <option value="glm-ocr">GLM-OCR (GPU + Layout)</option>
</select>
{ocrEngine === "glm-ocr" && (
  <p className="text-xs text-blue-600 mt-1">
    🔬 Detects tables, images, and structure. RTX 3080 GPU processing (~5-7s/page)
  </p>
)}
```

#### 2. Enhanced Result Display

**Add layout statistics section:**

```typescript
interface UploadResult {
  status: string;
  filename: string;
  file_type: string;
  chunks_extracted: number;
  chunks_indexed: number;
  collection: string;
  domain: string;
  processing_method: string;
  processing_time?: number;
  layout_detected?: {
    tables: number;
    images: number;
    headers: number;
  };
}
```

**Display component:**
```typescript
{entry.result?.layout_detected && (
  <div className="mt-2 p-2 bg-blue-50 rounded text-xs">
    <div className="font-medium text-blue-900 mb-1">📊 Layout Analysis:</div>
    <div className="grid grid-cols-3 gap-2 text-blue-700">
      <div>📋 {entry.result.layout_detected.tables} tables</div>
      <div>🖼️ {entry.result.layout_detected.images} images</div>
      <div>📑 {entry.result.layout_detected.headers} sections</div>
    </div>
    {entry.result.processing_time && (
      <div className="text-blue-600 mt-1">
        ⚡ Processed in {entry.result.processing_time.toFixed(2)}s
      </div>
    )}
  </div>
)}
```

#### 3. Internationalization

**File:** `frontend/copilot-demo/messages/en.json`

```json
{
  "AdminNew": {
    "documents": {
      "upload": {
        "ocrEngine": "OCR Engine",
        "ocrEngines": {
          "easyocr": "EasyOCR",
          "tesseract": "Tesseract",
          "rapidocr": "RapidOCR",
          "glmocr": "GLM-OCR (GPU + Layout)",
          "glmocrHint": "Detects tables, images, and structure. GPU processing."
        },
        "layoutAnalysis": "Layout Analysis",
        "tables": "tables",
        "images": "images",
        "sections": "sections"
      }
    }
  }
}
```

**File:** `frontend/copilot-demo/messages/zh.json`

```json
{
  "AdminNew": {
    "documents": {
      "upload": {
        "ocrEngine": "OCR 引擎",
        "ocrEngines": {
          "easyocr": "EasyOCR",
          "tesseract": "Tesseract",
          "rapidocr": "RapidOCR",
          "glmocr": "GLM-OCR（GPU + 版式检测）",
          "glmocrHint": "检测表格、图像和文档结构。GPU 加速处理。"
        },
        "layoutAnalysis": "版式分析",
        "tables": "表格",
        "images": "图像",
        "sections": "章节"
      }
    }
  }
}
```

### Backend Changes

#### 1. Main Upload Endpoint Modification

**File:** `services/admin_endpoints.py`

**Current flow (lines 436-461):**
```python
if ext == ".pdf":
    # Route through GPU OCR service (P100 + RTX 3080 with quality gate)
    from services.rag_pipeline.mold_document_ingester import MoldDocumentIngester

    ingester = MoldDocumentIngester()
    try:
        parse_result = await ingester.ingest_document(...)
```

**Proposed modification:**
```python
if ext == ".pdf":
    # Check if user explicitly selected GLM-OCR
    if ocr_engine == "glm-ocr":
        # Direct GLM-SDK path with layout detection
        docling_result, layout_stats, processing_time = await _process_with_glm_ocr(
            saved_path, domain
        )
        logger.info(f"GLM-OCR: {layout_stats['tables']} tables, "
                   f"{layout_stats['images']} images, "
                   f"{layout_stats['headers']} headers in {processing_time:.2f}s")
    else:
        # Existing path: Docling with quality gate
        from services.rag_pipeline.mold_document_ingester import MoldDocumentIngester
        ingester = MoldDocumentIngester()
        try:
            parse_result = await ingester.ingest_document(...)
            docling_result = {
                "md": parse_result.get("text", ""),
                # ... existing code ...
            }
            layout_stats = None
            processing_time = None
        finally:
            await ingester.close()
```

#### 2. GLM-OCR Processing Function

**File:** `services/admin_endpoints.py` (add new function)

```python
async def _process_with_glm_ocr(
    pdf_path: Path,
    domain: str
) -> tuple[Dict[str, Any], Dict[str, int], float]:
    """
    Process PDF with GLM-OCR SDK for layout detection and structured extraction.

    Args:
        pdf_path: Path to PDF file
        domain: Domain classification

    Returns:
        Tuple of (docling_result, layout_stats, processing_time)
    """
    import time
    import httpx
    from pathlib import Path

    start_time = time.time()

    # Copy PDF to shared volume for GLM-SDK access
    shared_dir = Path("/tmp/glm_shared")
    shared_dir.mkdir(exist_ok=True)

    shared_pdf = shared_dir / pdf_path.name
    import shutil
    shutil.copy(pdf_path, shared_pdf)

    try:
        # Copy to GLM-SDK container
        import subprocess
        subprocess.run([
            "docker", "cp",
            str(shared_pdf),
            "bestbox-glm-sdk:/app/shared/"
        ], check=True)

        container_path = f"/app/shared/{pdf_path.name}"

        # Call GLM-SDK
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                "http://localhost:5002/glmocr/parse",
                json={"images": [container_path]},
                headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:
                raise RuntimeError(f"GLM-SDK error: {response.status_code} - {response.text}")

            result = response.json()
            markdown = result.get("markdown_result", "")

            # Parse layout statistics from markdown
            layout_stats = {
                "tables": markdown.count("<table"),
                "images": markdown.count("![](page="),
                "headers": markdown.count("##")
            }

            processing_time = time.time() - start_time

            # Convert to docling_result format for compatibility
            docling_result = {
                "md": markdown,
                "document": {
                    "content": [{"text": markdown}]
                },
                "pictures": [],
                "metadata": {
                    "domain": domain,
                    "processing_method": "glm-ocr-layout",
                    "layout_detected": layout_stats
                }
            }

            return docling_result, layout_stats, processing_time

    finally:
        # Cleanup
        if shared_pdf.exists():
            shared_pdf.unlink()
```

#### 3. Response Enhancement

**File:** `services/admin_endpoints.py` (modify return statement around line 520)

**Current:**
```python
return {
    "status": "success",
    "filename": file.filename,
    "file_type": ext.lstrip("."),
    "chunks_extracted": len(chunks),
    "chunks_indexed": indexed_count,
    "collection": collection,
    "domain": domain,
    "processing_method": processing_method,
}
```

**Proposed:**
```python
response_data = {
    "status": "success",
    "filename": file.filename,
    "file_type": ext.lstrip("."),
    "chunks_extracted": len(chunks),
    "chunks_indexed": indexed_count,
    "collection": collection,
    "domain": domain,
    "processing_method": processing_method,
}

# Add GLM-OCR specific metadata
if ocr_engine == "glm-ocr" and layout_stats:
    response_data["layout_detected"] = layout_stats
    response_data["processing_time"] = processing_time

return response_data
```

### Data Flow

#### 1. Request Flow

```
Frontend                    Backend                     GLM-SDK
   |                           |                           |
   |-- POST /upload ---------> |                           |
   |  ocr_engine="glm-ocr"    |                           |
   |  file: document.pdf      |                           |
   |                           |                           |
   |                           |-- Copy to shared vol ---> |
   |                           |                           |
   |                           |-- POST /glmocr/parse ---> |
   |                           |  {images: [path]}         |
   |                           |                           |
   |                           |                    Process PDF
   |                           |                    - Layout detect
   |                           |                    - OCR pages
   |                           |                    - Generate MD
   |                           |                           |
   |                           |<-- Return markdown ------- |
   |                           |  {markdown_result: "..."}|
   |                           |                           |
   |                    Parse layout stats                 |
   |                    (tables, images, headers)          |
   |                           |                           |
   |                    Convert to docling format          |
   |                           |                           |
   |                    Chunk & index                      |
   |                           |                           |
   |<-- Return results --------|                           |
   |  {status, chunks,         |                           |
   |   layout_detected: {...}} |                           |
   |                           |                           |
Display rich results          |                           |
```

#### 2. Data Transformations

**GLM-SDK Response:**
```json
{
  "markdown_result": "## Section\n\n<table>...</table>\n\n![](page=0,bbox=[10,20,100,200])",
  "json_result": { ... }
}
```

**Parsed Layout Stats:**
```python
{
  "tables": 3,      # Count of <table> tags
  "images": 5,      # Count of ![](page= patterns
  "headers": 8      # Count of ## headers
}
```

**Docling Result Format:**
```python
{
  "md": "full markdown text",
  "document": {
    "content": [{"text": "..."}]
  },
  "pictures": [],
  "metadata": {
    "domain": "mold",
    "processing_method": "glm-ocr-layout",
    "layout_detected": {...}
  }
}
```

**Final Response:**
```json
{
  "status": "success",
  "filename": "manual.pdf",
  "file_type": "pdf",
  "chunks_extracted": 15,
  "chunks_indexed": 15,
  "collection": "mold_reference_kb",
  "domain": "mold",
  "processing_method": "glm-ocr-layout",
  "processing_time": 5.25,
  "layout_detected": {
    "tables": 3,
    "images": 5,
    "headers": 8
  }
}
```

## Error Handling

### GLM-SDK Unavailable

**Scenario:** GLM-SDK service is down or unreachable

**Detection:**
```python
try:
    response = await client.post("http://localhost:5002/glmocr/parse", ...)
except httpx.ConnectError:
    logger.error("GLM-SDK unavailable")
    # Fallback to quality gate path
```

**Fallback Strategy:**
1. Log warning: "GLM-OCR selected but service unavailable, falling back to quality gate"
2. Route through existing Docling + quality gate path
3. Set `processing_method` to "fallback-quality-gate"
4. Return normal results without layout stats

### GPU Memory Exhausted

**Scenario:** RTX 3080 OOM during large PDF processing

**Detection:** GLM-SDK returns 500 error with OOM message

**Handling:**
```python
if response.status_code == 500 and "out of memory" in response.text.lower():
    logger.error(f"GPU OOM processing {pdf_path.name}")
    raise HTTPException(
        status_code=507,
        detail="PDF too large for GPU processing. Try splitting into smaller files."
    )
```

**User Feedback:**
- Frontend shows: "GPU memory exceeded. Please split PDF into smaller files (max 50 pages recommended)"

### Invalid PDF Format

**Scenario:** Corrupted or unsupported PDF structure

**Detection:** GLM-SDK returns parsing error

**Handling:**
```python
if "parse error" in result.get("error", "").lower():
    logger.warning(f"GLM-OCR parse failed, trying fallback")
    # Fall back to P100 OCR path
    return await _fallback_to_docling(pdf_path, domain)
```

### Timeout

**Scenario:** Processing takes longer than 300s

**Configuration:**
- GLM-SDK timeout: 300s (5 minutes)
- For very large PDFs, consider increasing to 600s

**Handling:**
```python
async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
    try:
        response = await client.post(...)
    except httpx.TimeoutException:
        logger.error("GLM-OCR timeout")
        raise HTTPException(
            status_code=504,
            detail="Processing timeout. PDF may be too large or complex."
        )
```

### Empty Results

**Scenario:** GLM-SDK returns empty markdown

**Detection:**
```python
markdown = result.get("markdown_result", "")
if not markdown or len(markdown.strip()) < 10:
    logger.warning("GLM-OCR returned empty result")
```

**Handling:**
- Log warning with PDF details
- Try fallback to quality gate
- If fallback also fails, return error to user

## Testing Strategy

### Unit Tests

**File:** `tests/test_glm_ocr_integration.py`

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

class TestGLMOCRIntegration:

    @pytest.mark.asyncio
    async def test_process_with_glm_ocr_success(self):
        """Test successful GLM-OCR processing"""
        pdf_path = Path("test.pdf")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "markdown_result": "## Test\n\n<table><tr><td>data</td></tr></table>\n\n![](page=0,bbox=[10,20,30,40])"
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result, stats, time = await _process_with_glm_ocr(pdf_path, "mold")

            assert stats["tables"] == 1
            assert stats["images"] == 1
            assert stats["headers"] == 1
            assert "glm-ocr-layout" in result["metadata"]["processing_method"]

    @pytest.mark.asyncio
    async def test_glm_sdk_unavailable_fallback(self):
        """Test fallback when GLM-SDK is unavailable"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.ConnectError("Connection refused")

            # Should fall back to quality gate path
            with pytest.raises(RuntimeError, match="GLM-SDK unavailable"):
                await _process_with_glm_ocr(Path("test.pdf"), "mold")

    @pytest.mark.asyncio
    async def test_layout_stats_parsing(self):
        """Test correct parsing of layout statistics"""
        markdown = """
        ## Header 1
        <table><tr><td>A</td></tr></table>
        ## Header 2
        ![](page=0,bbox=[1,2,3,4])
        ![](page=1,bbox=[5,6,7,8])
        <table><tr><td>B</td></tr></table>
        """

        stats = {
            "tables": markdown.count("<table"),
            "images": markdown.count("![](page="),
            "headers": markdown.count("##")
        }

        assert stats["tables"] == 2
        assert stats["images"] == 2
        assert stats["headers"] == 2
```

### Integration Tests

**File:** `tests/test_admin_upload_glm_ocr.py`

```python
import pytest
from fastapi.testclient import TestClient
from services.agent_api import app
from pathlib import Path

@pytest.fixture
def test_pdf():
    """Fixture providing test PDF path"""
    return Path("docs/ppd407_p4.pdf")

@pytest.fixture
def auth_headers():
    """Fixture providing admin auth headers"""
    return {"admin-token": "test-token"}

class TestAdminUploadGLMOCR:

    def test_upload_with_glm_ocr_engine(self, test_pdf, auth_headers):
        """Test uploading PDF with glm-ocr engine selected"""
        client = TestClient(app)

        with open(test_pdf, "rb") as f:
            response = client.post(
                "/admin/documents/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                params={
                    "collection": "test_kb",
                    "domain": "mold",
                    "ocr_engine": "glm-ocr"
                },
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["processing_method"] == "glm-ocr-layout"
        assert "layout_detected" in data
        assert data["layout_detected"]["tables"] > 0
        assert "processing_time" in data

    def test_upload_with_other_ocr_engine_unchanged(self, test_pdf, auth_headers):
        """Test that other OCR engines still work"""
        client = TestClient(app)

        with open(test_pdf, "rb") as f:
            response = client.post(
                "/admin/documents/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                params={
                    "collection": "test_kb",
                    "domain": "mold",
                    "ocr_engine": "easyocr"
                },
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()

        # Should use existing quality gate path
        assert data["processing_method"] == "gpu_ocr"
        assert "layout_detected" not in data
```

### End-to-End Tests

**File:** `tests/e2e/test_glm_ocr_workflow.py`

```python
import pytest
from playwright.sync_api import Page, expect

class TestGLMOCRWorkflow:

    def test_select_glm_ocr_and_upload(self, page: Page):
        """Test selecting GLM-OCR from UI and uploading PDF"""

        # Navigate to documents page
        page.goto("http://localhost:3000/zh/admin/documents")

        # Login (assuming auth is required)
        page.fill('input[type="password"]', "admin-password")
        page.click('button:has-text("Login")')

        # Select GLM-OCR engine
        page.select_option('select[name="ocrEngine"]', "glm-ocr")

        # Verify hint text appears
        expect(page.locator('text=GPU 加速处理')).to_be_visible()

        # Upload file
        page.set_input_files('input[type="file"]', "docs/ppd407_p4.pdf")

        # Click upload
        page.click('button:has-text("Upload")')

        # Wait for processing
        expect(page.locator('text=Done ✓')).to_be_visible(timeout=60000)

        # Verify layout analysis section appears
        expect(page.locator('text=📊 Layout Analysis')).to_be_visible()
        expect(page.locator('text=tables')).to_be_visible()
        expect(page.locator('text=images')).to_be_visible()
```

### Performance Tests

**File:** `tests/performance/test_glm_ocr_performance.py`

```python
import pytest
import time
from pathlib import Path

class TestGLMOCRPerformance:

    @pytest.mark.slow
    def test_processing_time_single_page(self):
        """Test GLM-OCR processing time for single page PDF"""
        # Single page should process in under 10 seconds
        start = time.time()

        # Process single page PDF
        result = process_pdf_with_glm_ocr("tests/fixtures/single_page.pdf")

        duration = time.time() - start
        assert duration < 10.0, f"Single page took {duration}s, expected < 10s"

    @pytest.mark.slow
    def test_processing_time_multi_page(self):
        """Test GLM-OCR processing time for 10-page PDF"""
        # 10 pages should process in under 60 seconds (6s/page)
        start = time.time()

        result = process_pdf_with_glm_ocr("tests/fixtures/ten_pages.pdf")

        duration = time.time() - start
        assert duration < 60.0, f"10 pages took {duration}s, expected < 60s"
        assert duration / 10 < 6.5, f"Average {duration/10}s per page, expected < 6.5s"
```

## Implementation Plan

### Phase 1: Backend Core (Day 1, 2-3 hours)

1. **Add GLM-OCR processing function** (`services/admin_endpoints.py`)
   - `_process_with_glm_ocr()` function
   - Shared volume handling
   - GLM-SDK API call
   - Layout stats parsing
   - Estimated: 1 hour

2. **Modify upload endpoint** (`services/admin_endpoints.py`)
   - Add `ocr_engine == "glm-ocr"` branch
   - Integrate new processing function
   - Enhanced response format
   - Estimated: 30 minutes

3. **Error handling**
   - Fallback logic for SDK unavailable
   - Timeout handling
   - Empty result handling
   - Estimated: 30 minutes

4. **Unit tests**
   - Test GLM-OCR processing
   - Test layout parsing
   - Test fallback scenarios
   - Estimated: 1 hour

### Phase 2: Frontend UI (Day 1-2, 1-2 hours)

1. **Dropdown enhancement** (`documents/page.tsx`)
   - Add "glm-ocr" option
   - Add hint text
   - Estimated: 15 minutes

2. **Result display enhancement**
   - Add layout_detected interface
   - Create layout stats component
   - Display processing time
   - Estimated: 45 minutes

3. **Internationalization**
   - Add English strings
   - Add Chinese strings
   - Estimated: 15 minutes

4. **UI testing**
   - Manual testing of flow
   - Visual verification
   - Estimated: 15 minutes

### Phase 3: Integration Testing (Day 2, 1 hour)

1. **Integration tests**
   - Test upload with glm-ocr
   - Test other engines unchanged
   - Estimated: 30 minutes

2. **E2E tests** (optional)
   - Playwright workflow test
   - Estimated: 30 minutes

### Phase 4: Documentation & Deployment (Day 2, 30 minutes)

1. **Update documentation**
   - Update CLAUDE.md with new option
   - Update GLM_OCR_FIX_SUMMARY.md
   - Estimated: 15 minutes

2. **Deployment**
   - Restart frontend: `npm run dev`
   - Restart backend: `./scripts/start-agent-api.sh`
   - Verify services: `docker ps | grep glm`
   - Estimated: 15 minutes

### Total Estimated Time: 5-7 hours

## Acceptance Criteria

### Functional Requirements

- [ ] "GLM-OCR (GPU + Layout)" appears in OCR engine dropdown
- [ ] Selecting GLM-OCR shows GPU processing hint
- [ ] PDF uploads with glm-ocr use GLM-SDK directly
- [ ] Response includes layout_detected with accurate counts
- [ ] Frontend displays layout statistics (tables, images, headers)
- [ ] Processing time is shown
- [ ] Other OCR engines (easyocr, tesseract, rapidocr) work unchanged
- [ ] Fallback to quality gate works when GLM-SDK unavailable

### Performance Requirements

- [ ] Single page PDF processes in < 10 seconds
- [ ] Multi-page PDF processes at ~5-7 seconds per page
- [ ] No memory leaks (verify with 10 consecutive uploads)
- [ ] GPU memory usage stays under 10GB

### Quality Requirements

- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Code coverage > 80% for new functions
- [ ] No console errors in frontend
- [ ] Proper error messages for all failure modes

### UX Requirements

- [ ] Clear indication when GLM-OCR is selected
- [ ] Processing status updates smoothly
- [ ] Layout statistics are easy to understand
- [ ] Error messages are actionable
- [ ] Internationalization works (English + Chinese)

## Monitoring & Observability

### Metrics to Track

1. **Usage Metrics**
   - GLM-OCR selection rate vs. other engines
   - Average PDF size processed
   - Average processing time per page

2. **Performance Metrics**
   - P50, P95, P99 processing times
   - GPU utilization during processing
   - GPU memory usage peaks

3. **Error Metrics**
   - GLM-SDK availability rate
   - Timeout rate
   - Fallback activation rate
   - OOM error rate

### Logging

**Add structured logging:**
```python
logger.info(
    "GLM-OCR processing started",
    extra={
        "filename": pdf_path.name,
        "file_size_mb": pdf_path.stat().st_size / 1024 / 1024,
        "domain": domain
    }
)

logger.info(
    "GLM-OCR processing completed",
    extra={
        "filename": pdf_path.name,
        "processing_time": processing_time,
        "tables": layout_stats["tables"],
        "images": layout_stats["images"],
        "headers": layout_stats["headers"]
    }
)
```

## Future Enhancements

### Phase 2 Features (Post-Launch)

1. **Visual Layout Preview**
   - Render bounding boxes on PDF
   - Highlight detected tables/images
   - Interactive region selection

2. **Batch Processing Optimization**
   - Parallel page processing
   - GPU queue management
   - Progress streaming

3. **Advanced Layout Options**
   - User-adjustable confidence thresholds
   - Custom label mappings
   - Layout visualization export

4. **Quality Comparison View**
   - Side-by-side: GLM-OCR vs. EasyOCR
   - Quality metrics display
   - User feedback collection

### Integration Opportunities

1. **Workflow Canvas Integration**
   - GLM-OCR as workflow node
   - Layout-aware chunking strategies
   - Table extraction for structured Q&A

2. **RAG Pipeline Enhancement**
   - Use layout info for better chunking
   - Separate indexing for tables vs. text
   - Image-based retrieval

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| GLM-SDK instability | High | Medium | Fallback to quality gate, monitoring alerts |
| GPU OOM on large PDFs | Medium | Medium | Document size limits, user guidance |
| Slower than expected | Medium | Low | Set expectations in UI (5-7s/page) |
| Layout stats inaccurate | Low | Low | Improve parsing logic, add validation |
| User confusion | Medium | Low | Clear UI hints, documentation |

## Dependencies

### Service Dependencies

- **GLM-Transformers** (port 11436): Must be running and healthy
- **GLM-SDK** (port 5002): Must be running with layout detection enabled
- **Shared volume**: `/app/shared` must be accessible by GLM-SDK container

### Code Dependencies

- `services/ocr/glm_ocr_client.py`: Already exists, no changes needed
- `docker-compose.ocr.yml`: Already configured, no changes needed
- `httpx`: Already installed for async HTTP

### Infrastructure

- RTX 3080 GPU with CUDA 12.4
- Docker containers for GLM services
- ~10GB GPU memory available

## Rollback Plan

If issues arise post-deployment:

1. **Quick Rollback** (5 minutes)
   - Revert frontend change: Remove "glm-ocr" option from dropdown
   - Users can't select it, existing paths unaffected

2. **Full Rollback** (15 minutes)
   - `git revert <commit-hash>`
   - Restart services
   - Verify other OCR engines work

3. **Partial Rollback** (10 minutes)
   - Keep frontend option
   - Add feature flag to force fallback
   - Debug backend in staging

## Success Metrics

### Week 1 Post-Launch

- [ ] 20+ successful GLM-OCR uploads
- [ ] 0 critical errors
- [ ] Average processing time < 6s per page
- [ ] 90%+ user satisfaction (if feedback collected)

### Month 1 Post-Launch

- [ ] GLM-OCR usage > 30% of total uploads
- [ ] 95%+ success rate
- [ ] No GPU memory incidents
- [ ] User feedback indicates value in layout detection

## References

- [GLM-OCR Fix Summary](../GLM_OCR_FIX_SUMMARY.md)
- [GLM-OCR Test Script](../../scripts/test_glm_ocr_full.py)
- [Admin Documents Page](../../frontend/copilot-demo/app/[locale]/admin/documents/page.tsx)
- [Admin Endpoints](../../services/admin_endpoints.py)
- [Docker Compose OCR](../../docker/docker-compose.ocr.yml)
