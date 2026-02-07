# URL Ingestion + LLM Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add URL-based document import with LLM-powered knowledge extraction and metadata enrichment to the admin KB system.

**Architecture:** New `services/llm_enrichment.py` module handles all LLM calls. The upload-url endpoint downloads remote files, feeds them through the existing Docling pipeline, then runs a single merged LLM prompt per chunk to produce enriched text (summaries, Q&A pairs) and metadata tags. Each source chunk produces 2 Qdrant points (original + enriched). The frontend adds a URL input tab alongside the existing file upload.

**Tech Stack:** Python/FastAPI (backend), httpx (download + LLM calls), Qdrant (vectors), Next.js/React (frontend), local Qwen LLM on :8001 via OpenAI-compatible `/v1/chat/completions`

---

### Task 1: LLM Enrichment Module — Core Function

**Files:**
- Create: `services/llm_enrichment.py`
- Create: `tests/test_llm_enrichment.py`

**Step 1: Write the failing test**

```python
# tests/test_llm_enrichment.py
import pytest
import json
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_enrich_chunk_returns_structured_result():
    """enrich_chunk should call LLM and return parsed EnrichmentResult."""
    mock_llm_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "summary": "This chunk describes splay defects in injection molding.",
                    "key_concepts": ["splay", "moisture", "injection molding"],
                    "qa_pairs": [
                        {"question": "What causes splay?", "answer": "Moisture, shear, or heat degradation."}
                    ],
                    "domain_terms": ["splay", "melt temperature"],
                    "defect_type": "splay",
                    "severity": "medium",
                    "root_cause_category": "material",
                    "mold_components": ["gate"],
                    "corrective_actions": ["improve drying"],
                    "applicable_materials": ["copolyester"],
                })
            }
        }]
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_llm_response
    mock_response.raise_for_status = lambda: None

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        from services.llm_enrichment import enrich_chunk

        result = await enrich_chunk(
            text="Splay is caused by moisture in the material...",
            domain="mold"
        )

        assert result is not None
        assert result.summary == "This chunk describes splay defects in injection molding."
        assert "splay" in result.key_concepts
        assert len(result.qa_pairs) == 1
        assert result.defect_type == "splay"
        assert result.severity == "medium"


@pytest.mark.asyncio
async def test_enrich_chunk_returns_none_on_llm_failure():
    """enrich_chunk should return None if LLM is unreachable."""
    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = Exception("Connection refused")
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        from services.llm_enrichment import enrich_chunk

        result = await enrich_chunk(text="Some text", domain="mold")
        assert result is None


@pytest.mark.asyncio
async def test_enrich_chunk_returns_none_on_bad_json():
    """enrich_chunk should return None if LLM returns unparseable JSON."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "not valid json {{"}}]
    }
    mock_response.raise_for_status = lambda: None

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        from services.llm_enrichment import enrich_chunk

        result = await enrich_chunk(text="Some text", domain="mold")
        assert result is None
```

**Step 2: Run test to verify it fails**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_llm_enrichment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.llm_enrichment'`

**Step 3: Write minimal implementation**

```python
# services/llm_enrichment.py
"""
LLM-powered knowledge extraction and metadata enrichment.

Uses the local Qwen LLM via OpenAI-compatible API to extract structured
knowledge from document chunks: summaries, Q&A pairs, key concepts,
and domain-specific metadata tags.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1")
LLM_TIMEOUT = float(os.getenv("LLM_ENRICHMENT_TIMEOUT", "60"))


@dataclass
class QAPair:
    question: str
    answer: str


@dataclass
class EnrichmentResult:
    summary: str = ""
    key_concepts: List[str] = field(default_factory=list)
    qa_pairs: List[QAPair] = field(default_factory=list)
    domain_terms: List[str] = field(default_factory=list)
    defect_type: str = ""
    severity: str = ""
    root_cause_category: str = ""
    mold_components: List[str] = field(default_factory=list)
    corrective_actions: List[str] = field(default_factory=list)
    applicable_materials: List[str] = field(default_factory=list)

    def to_enriched_text(self) -> str:
        """Build searchable text from enriched fields."""
        parts = []
        if self.summary:
            parts.append(self.summary)
        for qa in self.qa_pairs:
            parts.append(f"Q: {qa.question}\nA: {qa.answer}")
        if self.key_concepts:
            parts.append("Key concepts: " + ", ".join(self.key_concepts))
        return "\n\n".join(parts)

    def to_metadata(self) -> Dict[str, Any]:
        """Extract metadata tags for Qdrant payload update."""
        meta = {}
        if self.defect_type:
            meta["defect_type"] = self.defect_type
        if self.severity:
            meta["severity"] = self.severity
        if self.root_cause_category:
            meta["root_cause_category"] = self.root_cause_category
        if self.mold_components:
            meta["mold_components"] = self.mold_components
        if self.corrective_actions:
            meta["corrective_actions"] = self.corrective_actions
        if self.applicable_materials:
            meta["applicable_materials"] = self.applicable_materials
        if self.domain_terms:
            meta["domain_terms"] = self.domain_terms
        return meta


MOLD_SYSTEM_PROMPT = """You are a manufacturing knowledge extraction assistant specializing in injection molding.

Given a text chunk from a technical document, extract structured knowledge as JSON.

Return ONLY valid JSON with these fields:
{
  "summary": "2-3 sentence summary of this chunk's content",
  "key_concepts": ["list", "of", "key", "technical", "concepts"],
  "qa_pairs": [
    {"question": "A question this chunk answers", "answer": "The answer from the text"}
  ],
  "domain_terms": ["technical", "terms", "found", "in", "text"],
  "defect_type": "defect type if mentioned (e.g. splay, flash, short shot, warpage) or empty string",
  "severity": "high/medium/low if inferable, or empty string",
  "root_cause_category": "material/process/mold/machine if identifiable, or empty string",
  "mold_components": ["mold components mentioned"],
  "corrective_actions": ["corrective actions described"],
  "applicable_materials": ["materials mentioned"]
}

Rules:
- Extract 1-3 Q&A pairs that capture the most useful knowledge
- Only fill fields where the text provides clear information
- Use empty string for text fields and empty array for list fields when not applicable
- Return ONLY the JSON object, no markdown fencing or explanation"""

GENERIC_SYSTEM_PROMPT = """You are a knowledge extraction assistant.

Given a text chunk from a technical document, extract structured knowledge as JSON.

Return ONLY valid JSON with these fields:
{
  "summary": "2-3 sentence summary of this chunk's content",
  "key_concepts": ["list", "of", "key", "concepts"],
  "qa_pairs": [
    {"question": "A question this chunk answers", "answer": "The answer from the text"}
  ],
  "domain_terms": ["domain-specific", "terms"],
  "defect_type": "",
  "severity": "",
  "root_cause_category": "",
  "mold_components": [],
  "corrective_actions": [],
  "applicable_materials": []
}

Rules:
- Extract 1-3 Q&A pairs that capture the most useful knowledge
- Only fill fields where the text provides clear information
- Return ONLY the JSON object, no markdown fencing or explanation"""


def _get_system_prompt(domain: str) -> str:
    if domain == "mold":
        return MOLD_SYSTEM_PROMPT
    return GENERIC_SYSTEM_PROMPT


def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown fencing."""
    text = raw.strip()
    # Strip markdown code fencing if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _dict_to_result(data: Dict[str, Any]) -> EnrichmentResult:
    """Convert parsed JSON dict to EnrichmentResult."""
    qa_pairs = []
    for qa in data.get("qa_pairs", []):
        if isinstance(qa, dict) and "question" in qa and "answer" in qa:
            qa_pairs.append(QAPair(question=qa["question"], answer=qa["answer"]))

    return EnrichmentResult(
        summary=data.get("summary", ""),
        key_concepts=data.get("key_concepts", []),
        qa_pairs=qa_pairs,
        domain_terms=data.get("domain_terms", []),
        defect_type=data.get("defect_type", ""),
        severity=data.get("severity", ""),
        root_cause_category=data.get("root_cause_category", ""),
        mold_components=data.get("mold_components", []),
        corrective_actions=data.get("corrective_actions", []),
        applicable_materials=data.get("applicable_materials", []),
    )


async def enrich_chunk(text: str, domain: str = "mold") -> Optional[EnrichmentResult]:
    """
    Call the local LLM to extract structured knowledge from a single chunk.

    Returns EnrichmentResult on success, None on any failure.
    """
    system_prompt = _get_system_prompt(domain)

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                json={
                    "model": "default",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Extract knowledge from this text:\n\n{text}"},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return None

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        logger.warning("LLM response missing expected structure")
        return None

    parsed = _parse_llm_json(content)
    if parsed is None:
        logger.warning(f"Failed to parse LLM JSON: {content[:200]}")
        return None

    return _dict_to_result(parsed)
```

**Step 4: Run test to verify it passes**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_llm_enrichment.py -v`
Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add services/llm_enrichment.py tests/test_llm_enrichment.py
git commit -m "feat: add LLM enrichment module with structured knowledge extraction"
```

---

### Task 2: LLM Enrichment Module — Document-Level Processing

**Files:**
- Modify: `services/llm_enrichment.py`
- Modify: `tests/test_llm_enrichment.py`

**Step 1: Write the failing test**

```python
# Append to tests/test_llm_enrichment.py

@pytest.mark.asyncio
async def test_enrich_document_processes_all_chunks():
    """enrich_document should call enrich_chunk for each chunk and return results."""
    from services.llm_enrichment import enrich_document, EnrichmentResult, QAPair

    mock_result = EnrichmentResult(
        summary="Test summary",
        key_concepts=["concept1"],
        qa_pairs=[QAPair(question="Q?", answer="A.")],
        domain_terms=["term1"],
        defect_type="splay",
        severity="high",
    )

    chunks = [
        {"text": "Chunk 1 text", "metadata": {"chunk_index": 0}},
        {"text": "Chunk 2 text", "metadata": {"chunk_index": 1}},
        {"text": "Chunk 3 text", "metadata": {"chunk_index": 2}},
    ]

    progress_log = []

    with patch("services.llm_enrichment.enrich_chunk", new_callable=AsyncMock) as mock_enrich:
        mock_enrich.return_value = mock_result
        results = await enrich_document(
            chunks, domain="mold",
            progress_callback=lambda cur, total: progress_log.append((cur, total))
        )

    assert len(results) == 3
    assert all(r is not None for r in results)
    assert progress_log == [(1, 3), (2, 3), (3, 3)]


@pytest.mark.asyncio
async def test_enrich_document_skips_failed_chunks():
    """enrich_document should return None for failed chunks, continue with rest."""
    from services.llm_enrichment import enrich_document, EnrichmentResult

    chunks = [
        {"text": "Chunk 1", "metadata": {"chunk_index": 0}},
        {"text": "Chunk 2", "metadata": {"chunk_index": 1}},
    ]

    call_count = 0
    async def _side_effect(text, domain):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None  # First chunk fails
        return EnrichmentResult(summary="OK")

    with patch("services.llm_enrichment.enrich_chunk", side_effect=_side_effect):
        results = await enrich_document(chunks, domain="mold")

    assert len(results) == 2
    assert results[0] is None
    assert results[1] is not None
    assert results[1].summary == "OK"
```

**Step 2: Run test to verify it fails**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_llm_enrichment.py::test_enrich_document_processes_all_chunks -v`
Expected: FAIL with `ImportError: cannot import name 'enrich_document'`

**Step 3: Write minimal implementation**

Append to `services/llm_enrichment.py`:

```python
async def enrich_document(
    chunks: List[Dict[str, Any]],
    domain: str = "mold",
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[Optional[EnrichmentResult]]:
    """
    Process all chunks through LLM enrichment sequentially.

    Returns a list parallel to chunks — EnrichmentResult or None per chunk.
    Failures on individual chunks do not stop processing.
    """
    total = len(chunks)
    results: List[Optional[EnrichmentResult]] = []

    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        if not text.strip():
            results.append(None)
        else:
            result = await enrich_chunk(text, domain)
            results.append(result)

        if progress_callback:
            progress_callback(i + 1, total)

    return results
```

**Step 4: Run test to verify it passes**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_llm_enrichment.py -v`
Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add services/llm_enrichment.py tests/test_llm_enrichment.py
git commit -m "feat: add document-level enrichment with progress callback"
```

---

### Task 3: URL Download Helper

**Files:**
- Modify: `services/admin_endpoints.py` (add `_download_url` helper + Pydantic model)
- Create: `tests/test_url_download.py`

**Step 1: Write the failing test**

```python
# tests/test_url_download.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path


@pytest.mark.asyncio
async def test_download_url_saves_pdf():
    """_download_url should stream a remote PDF to data/uploads/."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/pdf", "content-length": "1024"}
    mock_response.raise_for_status = lambda: None

    async def mock_aiter_bytes(chunk_size=None):
        yield b"%PDF-1.4 fake pdf content here"

    mock_response.aiter_bytes = mock_aiter_bytes

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.stream = MagicMock()

        # Make stream work as async context manager
        stream_cm = AsyncMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        stream_cm.__aexit__ = AsyncMock(return_value=False)
        mock_client.stream.return_value = stream_cm

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        # Import after patch
        from services.admin_endpoints import _download_url

        saved_path, filename = await _download_url("https://example.com/guide.pdf")

        assert saved_path.exists()
        assert saved_path.suffix == ".pdf"
        assert "guide.pdf" in filename
        # Clean up
        saved_path.unlink()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_url_download.py -v`
Expected: FAIL with `ImportError: cannot import name '_download_url'`

**Step 3: Write minimal implementation**

Add Pydantic model after existing models (after line ~75 in `services/admin_endpoints.py`):

```python
class UploadUrlRequest(BaseModel):
    url: str
    collection: str = "mold_reference_kb"
    domain: str = "mold"
    ocr_engine: str = "easyocr"
    chunking: str = "auto"
    enrich: bool = True
    force: bool = False
```

Add helper function (near other helpers around line ~178):

```python
async def _download_url(url: str) -> tuple[Path, str]:
    """
    Download a remote document to data/uploads/.

    Returns (saved_path, original_filename).
    Raises HTTPException on invalid URL, timeout, or size exceeded.
    """
    import httpx
    from urllib.parse import urlparse, unquote

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL must use http or https")

    # Extract filename from URL path
    url_path = unquote(parsed.path)
    filename = Path(url_path).name or "download"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"URL does not point to a supported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Stream download with size limit
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                # Check content-length if available
                content_length = int(response.headers.get("content-length", 0))
                if content_length > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=400, detail=f"File too large: {content_length} bytes (max {MAX_FILE_SIZE})"
                    )

                safe_name = _safe_filename(filename)
                timestamped = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe_name}"
                saved_path = UPLOAD_DIR / timestamped
                saved_path.parent.mkdir(parents=True, exist_ok=True)

                total_bytes = 0
                with open(saved_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        total_bytes += len(chunk)
                        if total_bytes > MAX_FILE_SIZE:
                            saved_path.unlink(missing_ok=True)
                            raise HTTPException(
                                status_code=400, detail="File exceeds 50 MB limit during download"
                            )
                        f.write(chunk)

                if total_bytes == 0:
                    saved_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=400, detail="Downloaded file is empty")

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Download failed: HTTP {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {e}")

    return saved_path, filename
```

**Step 4: Run test to verify it passes**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_url_download.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/admin_endpoints.py tests/test_url_download.py
git commit -m "feat: add URL download helper with streaming and size limit"
```

---

### Task 4: Upload-URL Endpoint

**Files:**
- Modify: `services/admin_endpoints.py` (add endpoint + background processor)

**Step 1: Write the failing test**

```python
# tests/test_upload_url_endpoint.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with admin auth bypassed."""
    import os
    os.environ["ADMIN_DEV_MODE"] = "true"

    from services.agent_api import app
    return TestClient(app)


def test_upload_url_returns_job_id(client):
    """POST /admin/documents/upload-url should return a job_id."""
    with patch("services.admin_endpoints._download_url", new_callable=AsyncMock) as mock_dl:
        from pathlib import Path
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(b"%PDF-1.4 fake")
        tmp.close()
        mock_dl.return_value = (Path(tmp.name), "test.pdf")

        with patch("services.admin_endpoints._process_url_job", new_callable=AsyncMock):
            resp = client.post(
                "/admin/documents/upload-url",
                json={
                    "url": "https://example.com/test.pdf",
                    "collection": "mold_reference_kb",
                    "domain": "mold",
                    "enrich": True,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "processing"

        Path(tmp.name).unlink(missing_ok=True)


def test_upload_url_rejects_invalid_extension(client):
    """POST /admin/documents/upload-url should reject .exe URLs."""
    resp = client.post(
        "/admin/documents/upload-url",
        json={"url": "https://example.com/malware.exe"},
    )
    assert resp.status_code == 400
```

**Step 2: Run test to verify it fails**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_upload_url_endpoint.py -v`
Expected: FAIL with 404 (endpoint doesn't exist yet)

**Step 3: Write the endpoint**

Add after the `admin_batch_upload` endpoint (after line ~381 in `services/admin_endpoints.py`):

```python
@router.post("/documents/upload-url")
async def admin_upload_url(
    body: UploadUrlRequest,
    request: Request,
    user: Dict = Depends(require_permission("upload")),
):
    """
    Import a remote document by URL.

    Downloads the file, processes through Docling pipeline, optionally
    enriches with LLM, and indexes into Qdrant. Returns a job_id for
    status polling via GET /admin/documents/jobs/{job_id}.
    """
    import asyncio
    from services.admin_auth import log_audit

    pool = _get_db_pool(request)

    # Duplicate check
    if not body.force:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            qdrant = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
            )
            existing, _ = qdrant.scroll(
                collection_name=body.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="source_url", match=MatchValue(value=body.url))]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False,
            )
            if existing:
                return JSONResponse(
                    status_code=409,
                    content={"detail": "URL already indexed. Use force=true to re-import.", "url": body.url},
                )
        except Exception:
            pass  # Collection may not exist yet; continue

    # Download file
    saved_path, filename = await _download_url(body.url)

    # Create async job
    job_id = str(uuid.uuid4())
    _batch_jobs[job_id] = {
        "id": job_id,
        "status": "processing",
        "stage": "downloading",
        "url": body.url,
        "filename": filename,
        "total_chunks": 0,
        "enriched_chunks": 0,
        "enrichment_progress": "",
        "completed": 0,
        "failed": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    asyncio.create_task(
        _process_url_job(job_id, saved_path, filename, body, user, pool)
    )

    if pool:
        await log_audit(
            pool,
            user.get("sub"),
            "upload_url",
            resource_type="document",
            resource_id=body.url,
            details={"collection": body.collection, "domain": body.domain},
        )

    return {"job_id": job_id, "filename": filename, "status": "processing"}
```

Add the background processing function (near `_process_batch`):

```python
async def _process_url_job(
    job_id: str,
    saved_path: Path,
    filename: str,
    body: "UploadUrlRequest",
    user: Dict[str, Any],
    pool,
):
    """Background task: process a URL-downloaded document."""
    from services.docling_client import DoclingClient
    from services.mold_case_extractor import MoldCaseExtractor

    job = _batch_jobs[job_id]

    try:
        # Stage: converting
        job["stage"] = "converting"
        ext = saved_path.suffix.lower()
        client = DoclingClient()
        options = client.options_for_format(ext)
        docling_result = await client.convert_file(str(saved_path), options)

        # Stage: chunking
        job["stage"] = "chunking"
        if body.domain == "mold" and ext in (".xlsx", ".xls"):
            extractor = MoldCaseExtractor()
            chunks = extractor.extract(
                docling_result,
                source_file=filename,
                uploaded_by=user.get("username", ""),
            )
        else:
            chunks = _hierarchical_chunk(
                docling_result,
                source_file=filename,
                domain=body.domain,
                uploaded_by=user.get("username", ""),
            )

        # Add source_url to all chunk metadata
        for chunk in chunks:
            chunk["metadata"]["source_url"] = body.url

        job["total_chunks"] = len(chunks)

        # Stage: enriching (optional)
        enrichment_results = None
        if body.enrich and chunks:
            job["stage"] = "enriching"
            from services.llm_enrichment import enrich_document

            def _progress(cur, total):
                job["enrichment_progress"] = f"enriching chunk {cur}/{total}"

            enrichment_results = await enrich_document(
                chunks, domain=body.domain, progress_callback=_progress
            )
            job["enriched_chunks"] = sum(1 for r in enrichment_results if r is not None)

        # Stage: indexing
        job["stage"] = "indexing"
        indexed = await _index_chunks_with_enrichment(chunks, enrichment_results, body.collection)

        job["status"] = "completed"
        job["stage"] = "done"
        job["completed"] = indexed
        job["enrichment"] = "applied" if enrichment_results else "skipped"

    except Exception as e:
        logger.error(f"URL job {job_id} failed: {e}", exc_info=True)
        job["status"] = "failed"
        job["stage"] = "error"
        job["error"] = str(e)
        job["failed"] = 1
```

**Step 4: Run test to verify it passes**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_upload_url_endpoint.py -v`
Expected: PASS (Note: `_index_chunks_with_enrichment` doesn't exist yet — that's Task 5. The test mocks `_process_url_job` so this is fine.)

**Step 5: Commit**

```bash
git add services/admin_endpoints.py tests/test_upload_url_endpoint.py
git commit -m "feat: add upload-url endpoint with async job processing"
```

---

### Task 5: Enriched Indexing Function

**Files:**
- Modify: `services/admin_endpoints.py` (add `_index_chunks_with_enrichment`)
- Create: `tests/test_enriched_indexing.py`

**Step 1: Write the failing test**

```python
# tests/test_enriched_indexing.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_index_chunks_with_enrichment_creates_double_points():
    """Should create 2 Qdrant points per chunk when enrichment is provided."""
    from services.llm_enrichment import EnrichmentResult, QAPair

    chunks = [
        {
            "text": "Original chunk text about splay defects",
            "metadata": {
                "doc_id": "test-doc-1",
                "source_file": "test.pdf",
                "file_type": "pdf",
                "domain": "mold",
                "chunk_index": 0,
                "uploaded_by": "test",
                "upload_date": "2026-02-06",
                "processing_method": "docling",
                "has_images": False,
            },
        }
    ]

    enrichment_results = [
        EnrichmentResult(
            summary="This chunk discusses splay defects.",
            key_concepts=["splay"],
            qa_pairs=[QAPair(question="What is splay?", answer="A surface defect.")],
            domain_terms=["splay"],
            defect_type="splay",
            severity="high",
        )
    ]

    mock_embeddings_response = MagicMock()
    mock_embeddings_response.status_code = 200
    mock_embeddings_response.raise_for_status = lambda: None
    mock_embeddings_response.json.return_value = {
        "embeddings": [[0.1] * 1024, [0.2] * 1024]  # 2 embeddings for 2 texts
    }

    mock_qdrant = MagicMock()
    mock_qdrant.get_collection = MagicMock()

    upserted_points = []
    def capture_upsert(**kwargs):
        upserted_points.extend(kwargs.get("points", []))
    mock_qdrant.upsert = capture_upsert
    mock_qdrant.set_payload = MagicMock()

    with patch("httpx.AsyncClient") as MockHttpClient:
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_embeddings_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        MockHttpClient.return_value = mock_http

        with patch("services.admin_endpoints.QdrantClient", return_value=mock_qdrant):
            from services.admin_endpoints import _index_chunks_with_enrichment
            count = await _index_chunks_with_enrichment(chunks, enrichment_results, "test_collection")

    assert count == 2  # 1 original + 1 enriched
    assert len(upserted_points) == 2


@pytest.mark.asyncio
async def test_index_chunks_without_enrichment_falls_back():
    """When enrichment_results is None, should behave like regular indexing."""
    chunks = [
        {
            "text": "Plain chunk text",
            "metadata": {
                "doc_id": "test-doc-1",
                "source_file": "test.pdf",
                "chunk_index": 0,
                "domain": "mold",
            },
        }
    ]

    mock_embeddings_response = MagicMock()
    mock_embeddings_response.status_code = 200
    mock_embeddings_response.raise_for_status = lambda: None
    mock_embeddings_response.json.return_value = {
        "embeddings": [[0.1] * 1024]
    }

    mock_qdrant = MagicMock()
    mock_qdrant.get_collection = MagicMock()
    mock_qdrant.upsert = MagicMock()

    with patch("httpx.AsyncClient") as MockHttpClient:
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_embeddings_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        MockHttpClient.return_value = mock_http

        with patch("services.admin_endpoints.QdrantClient", return_value=mock_qdrant):
            from services.admin_endpoints import _index_chunks_with_enrichment
            count = await _index_chunks_with_enrichment(chunks, None, "test_collection")

    assert count == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_enriched_indexing.py -v`
Expected: FAIL with `ImportError: cannot import name '_index_chunks_with_enrichment'`

**Step 3: Write the implementation**

Add to `services/admin_endpoints.py` near `_index_chunks`:

```python
async def _index_chunks_with_enrichment(
    chunks: List[Dict[str, Any]],
    enrichment_results: Optional[List] = None,
    collection: str = "mold_reference_kb",
) -> int:
    """
    Embed and index chunks with optional enrichment.

    When enrichment_results is provided, each chunk produces 2 Qdrant points:
    1. Original text with chunk_type="original"
    2. Enriched text (summary + Q&A) with chunk_type="enriched"

    Metadata tags from enrichment are applied to both points via set_payload.
    """
    import httpx
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance

    if not chunks:
        return 0

    # Build text list for embedding
    texts = []
    point_specs = []  # (chunk_index, chunk_type, text, metadata)

    for i, chunk in enumerate(chunks):
        meta = {**chunk["metadata"], "chunk_type": "original"}
        texts.append(chunk["text"])
        point_specs.append((i, "original", chunk["text"], meta))

        # Add enriched point if enrichment succeeded for this chunk
        if enrichment_results and i < len(enrichment_results) and enrichment_results[i] is not None:
            enriched_text = enrichment_results[i].to_enriched_text()
            if enriched_text.strip():
                enriched_meta = {**chunk["metadata"], "chunk_type": "enriched"}
                texts.append(enriched_text)
                point_specs.append((i, "enriched", enriched_text, enriched_meta))

    # Embed all texts
    embeddings_url = os.getenv(
        "EMBEDDINGS_URL",
        os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8004"),
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{embeddings_url}/embed",
                json={"texts": texts},
            )
            resp.raise_for_status()
            embeddings = resp.json().get("embeddings", [])
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return 0

    if len(embeddings) != len(texts):
        logger.error(f"Embedding count mismatch: {len(embeddings)} vs {len(texts)}")
        return 0

    # Ensure collection
    qdrant = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )

    try:
        qdrant.get_collection(collection)
    except Exception:
        vector_size = len(embeddings[0]) if embeddings else 1024
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    # Build and upsert points
    points = []
    point_ids = []
    for (chunk_idx, chunk_type, text, meta), embedding in zip(point_specs, embeddings):
        point_id = str(uuid.uuid4())
        payload = {**meta, "text": text}
        points.append(PointStruct(id=point_id, vector=embedding, payload=payload))
        point_ids.append((point_id, chunk_idx, chunk_type))

    qdrant.upsert(collection_name=collection, points=points)

    # Apply enrichment metadata tags to both original and enriched points
    if enrichment_results:
        for point_id, chunk_idx, chunk_type in point_ids:
            if chunk_idx < len(enrichment_results) and enrichment_results[chunk_idx] is not None:
                extra_meta = enrichment_results[chunk_idx].to_metadata()
                if extra_meta:
                    try:
                        qdrant.set_payload(
                            collection_name=collection,
                            payload=extra_meta,
                            points=[point_id],
                        )
                    except Exception as e:
                        logger.warning(f"Failed to set enrichment metadata on point {point_id}: {e}")

    return len(points)
```

Also add this import near the top of `admin_endpoints.py` (it's needed for the type annotation):

```python
from qdrant_client import QdrantClient
```

Wait — the file already imports QdrantClient locally inside functions. Since `_index_chunks_with_enrichment` also uses it locally, just add a module-level reference for test patching. Actually the test patches it via `services.admin_endpoints.QdrantClient`, so add this near the top of the file (after the existing imports around line 30):

No — keep imports local as the rest of the file does. Update the test to patch `qdrant_client.QdrantClient` instead. The mock setup in the test already handles this.

**Step 4: Run test to verify it passes**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_enriched_indexing.py -v`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add services/admin_endpoints.py tests/test_enriched_indexing.py
git commit -m "feat: add enriched indexing with dual original+enriched Qdrant points"
```

---

### Task 6: Frontend — URL Import Tab

**Files:**
- Modify: `frontend/copilot-demo/app/admin/documents/page.tsx`

**Step 1: Add state and types for URL import**

At the top of `DocumentsUploadPage` component (after existing state declarations around line 71), add:

```typescript
// URL import state
const [activeTab, setActiveTab] = useState<"file" | "url">("file");
const [importUrl, setImportUrl] = useState("");
const [enrichEnabled, setEnrichEnabled] = useState(true);
const [urlImporting, setUrlImporting] = useState(false);
const [urlJobId, setUrlJobId] = useState<string | null>(null);
const [urlJobStatus, setUrlJobStatus] = useState<Record<string, unknown> | null>(null);
```

**Step 2: Add URL import handler function**

After the `uploadAll` function, add:

```typescript
const importFromUrl = async () => {
  if (!importUrl.trim()) return;
  setUrlImporting(true);
  setUrlJobStatus(null);

  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    if (token.includes(".")) headers["Authorization"] = `Bearer ${token}`;
    else headers["admin-token"] = token;
  }

  try {
    const res = await fetch(`${API_BASE}/admin/documents/upload-url`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        url: importUrl,
        collection,
        domain,
        ocr_engine: ocrEngine,
        chunking,
        enrich: enrichEnabled,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Import failed" }));
      setUrlJobStatus({ status: "failed", error: err.detail });
      setUrlImporting(false);
      return;
    }

    const data = await res.json();
    setUrlJobId(data.job_id);

    // Poll for status
    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await fetch(
          `${API_BASE}/admin/documents/jobs/${data.job_id}`,
          { headers }
        );
        if (statusRes.ok) {
          const status = await statusRes.json();
          setUrlJobStatus(status);
          if (status.status === "completed" || status.status === "failed") {
            clearInterval(pollInterval);
            setUrlImporting(false);
          }
        }
      } catch {
        // Keep polling
      }
    }, 2000);
  } catch (err) {
    setUrlJobStatus({
      status: "failed",
      error: err instanceof Error ? err.message : "Import failed",
    });
    setUrlImporting(false);
  }
};

const isValidUrl = (url: string) => {
  try {
    const u = new URL(url);
    if (!["http:", "https:"].includes(u.protocol)) return false;
    const ext = u.pathname.split(".").pop()?.toLowerCase();
    return ["pdf", "docx", "pptx", "xlsx", "xls"].includes(ext || "");
  } catch {
    return false;
  }
};
```

**Step 3: Add tab UI and URL input section**

Replace the Drop Zone section and everything down to (but not including) the Processing Options section. The new structure wraps both the drop zone and a new URL tab inside a tab container.

Replace the Drop Zone comment block (`{/* Drop Zone */}`) through the closing `</div>` of the drop zone (line ~240) with:

```tsx
{/* Tab Selector */}
<div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-6">
  <button
    onClick={() => setActiveTab("file")}
    className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
      activeTab === "file"
        ? "bg-white text-gray-900 shadow-sm"
        : "text-gray-500 hover:text-gray-700"
    }`}
  >
    Upload Files
  </button>
  <button
    onClick={() => setActiveTab("url")}
    className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
      activeTab === "url"
        ? "bg-white text-gray-900 shadow-sm"
        : "text-gray-500 hover:text-gray-700"
    }`}
  >
    Import from URL
  </button>
</div>

{activeTab === "file" ? (
  /* existing Drop Zone — keep as-is */
  <div
    className={`border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer ${
      dragActive ? "border-blue-500 bg-blue-50 scale-[1.01]" : "border-gray-300 bg-white hover:border-gray-400"
    }`}
    onDragEnter={handleDrag}
    onDragLeave={handleDrag}
    onDragOver={handleDrag}
    onDrop={handleDrop}
    onClick={() => fileInputRef.current?.click()}
  >
    <input
      ref={fileInputRef}
      type="file"
      className="hidden"
      multiple
      accept=".pdf,.docx,.pptx,.xlsx,.xls,.jpg,.jpeg,.png,.webp,.tiff,.bmp"
      onChange={handleFileInput}
    />
    <svg className="w-14 h-14 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
    </svg>
    <p className="text-gray-600 font-medium">Drop files here or click to browse</p>
    <p className="text-sm text-gray-400 mt-1">
      PDF, DOCX, PPTX, XLSX, Images — max 50 MB each
    </p>
  </div>
) : (
  /* URL Import Section */
  <div className="bg-white rounded-xl border border-gray-200 p-6">
    <div className="flex gap-3">
      <input
        type="url"
        value={importUrl}
        onChange={(e) => setImportUrl(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && isValidUrl(importUrl) && importFromUrl()}
        placeholder="https://example.com/document.pdf"
        className="flex-1 border border-gray-300 rounded-lg px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />
      <button
        onClick={importFromUrl}
        disabled={!isValidUrl(importUrl) || urlImporting}
        className={`px-6 py-3 rounded-lg text-sm font-medium transition-colors ${
          !isValidUrl(importUrl) || urlImporting
            ? "bg-gray-300 text-gray-500 cursor-not-allowed"
            : "bg-blue-600 text-white hover:bg-blue-700"
        }`}
      >
        {urlImporting ? "Importing…" : "Import"}
      </button>
    </div>
    <p className="text-xs text-gray-400 mt-2">
      Direct link to PDF, DOCX, PPTX, or XLSX file — max 50 MB
    </p>

    {/* LLM Enrichment toggle */}
    <label className="flex items-center gap-2 text-sm text-gray-600 mt-4">
      <input
        type="checkbox"
        checked={enrichEnabled}
        onChange={(e) => setEnrichEnabled(e.target.checked)}
        className="rounded text-blue-600"
      />
      LLM Enrichment (extract Q&A pairs + auto-tag metadata)
    </label>

    {/* Job status */}
    {urlJobStatus && (
      <div className="mt-4 rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            {(urlJobStatus as Record<string, unknown>).filename as string || "Import"}
          </span>
          <span className={`text-xs font-medium ${
            urlJobStatus.status === "completed" ? "text-green-600" :
            urlJobStatus.status === "failed" ? "text-red-600" :
            "text-blue-500"
          }`}>
            {urlJobStatus.status === "completed" ? "Done" :
             urlJobStatus.status === "failed" ? "Failed" :
             (urlJobStatus.stage as string || "Processing…")}
          </span>
        </div>

        {urlJobStatus.status === "processing" && (
          <>
            <div className="w-full bg-gray-100 rounded-full h-1.5 mb-2">
              <div
                className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
                style={{
                  width: `${
                    urlJobStatus.stage === "downloading" ? 10 :
                    urlJobStatus.stage === "converting" ? 25 :
                    urlJobStatus.stage === "chunking" ? 40 :
                    urlJobStatus.stage === "enriching" ? 65 :
                    urlJobStatus.stage === "indexing" ? 85 : 50
                  }%`,
                }}
              />
            </div>
            {urlJobStatus.enrichment_progress && (
              <p className="text-xs text-gray-500">
                {urlJobStatus.enrichment_progress as string}
              </p>
            )}
          </>
        )}

        {urlJobStatus.status === "completed" && (
          <div className="grid grid-cols-3 gap-3 text-xs mt-2">
            <div>
              <span className="text-gray-500">Chunks:</span>{" "}
              <span className="font-medium">{urlJobStatus.total_chunks as number}</span>
            </div>
            <div>
              <span className="text-gray-500">Enriched:</span>{" "}
              <span className="font-medium text-purple-600">
                {urlJobStatus.enriched_chunks as number}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Indexed:</span>{" "}
              <span className="font-medium text-green-600">
                {urlJobStatus.completed as number}
              </span>
            </div>
          </div>
        )}

        {urlJobStatus.status === "failed" && urlJobStatus.error && (
          <p className="text-xs text-red-600 mt-1">{urlJobStatus.error as string}</p>
        )}
      </div>
    )}
  </div>
)}
```

**Step 4: Verify the frontend compiles**

Run: `cd /home/apexai/BestBox/frontend/copilot-demo && npx next build 2>&1 | tail -5`
Expected: Build succeeds (or at least the documents page compiles without errors)

**Step 5: Commit**

```bash
git add frontend/copilot-demo/app/admin/documents/page.tsx
git commit -m "feat: add URL import tab to document upload page"
```

---

### Task 7: KB Browse Page — Enrichment Badges and Metadata

**Files:**
- Modify: `frontend/copilot-demo/app/admin/kb/page.tsx`

**Step 1: Update the chunk display in the detail modal**

In the detail modal's chunk rendering (around line 428-449 in `page.tsx`), update to show:

1. `source_url` in the document metadata section
2. "AI enriched" badge on enriched chunks
3. Metadata tags when present

In the metadata grid (around line 400-421), add after the upload date div:

```tsx
{(detailData as Record<string, unknown>).source_url && (
  <div className="col-span-2">
    <span className="text-gray-500">Source URL:</span>{" "}
    <a
      href={(detailData as Record<string, unknown>).source_url as string}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-blue-600 hover:underline truncate inline-block max-w-md"
    >
      {(detailData as Record<string, unknown>).source_url as string}
    </a>
  </div>
)}
```

In the chunk card header (around line 429-446), after the severity badge, add:

```tsx
{chunk.chunk_type === "enriched" ? (
  <span className="px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded text-xs">
    AI enriched
  </span>
) : null}
{chunk.root_cause_category ? (
  <span className="px-1.5 py-0.5 bg-green-50 text-green-600 rounded text-xs">
    {String(chunk.root_cause_category)}
  </span>
) : null}
```

**Step 2: Verify the frontend compiles**

Run: `cd /home/apexai/BestBox/frontend/copilot-demo && npx next build 2>&1 | tail -5`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/copilot-demo/app/admin/kb/page.tsx
git commit -m "feat: add enrichment badges and metadata tags to KB browse page"
```

---

### Task 8: End-to-End Smoke Test

**Files:**
- Create: `tests/test_url_ingestion_e2e.py`

**Step 1: Write integration test**

```python
# tests/test_url_ingestion_e2e.py
"""
End-to-end smoke test for URL ingestion + LLM enrichment.

Requires: Qdrant on :6333, Embeddings on :8004, LLM on :8001
Run with: pytest tests/test_url_ingestion_e2e.py -v -m e2e
"""
import pytest
import httpx
import time

E2E_MARKER = pytest.mark.e2e


@E2E_MARKER
@pytest.mark.asyncio
async def test_url_import_full_pipeline():
    """Full pipeline: URL download → Docling → enrich → index → query."""

    # Skip if services not running
    for url, name in [
        ("http://localhost:8000/health", "Agent API"),
        ("http://localhost:6333", "Qdrant"),
    ]:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(url)
                r.raise_for_status()
        except Exception:
            pytest.skip(f"{name} not running")

    # Use a small public-domain PDF for testing
    # (Replace with an actual test PDF URL accessible from your network)
    test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"

    async with httpx.AsyncClient(timeout=300, base_url="http://localhost:8000") as client:
        # Submit URL import
        resp = await client.post(
            "/admin/documents/upload-url",
            json={
                "url": test_url,
                "collection": "test_url_import",
                "domain": "general",
                "enrich": True,
                "force": True,
            },
            headers={"admin-token": "dev"},
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        # Poll until done (max 5 minutes)
        deadline = time.time() + 300
        while time.time() < deadline:
            status_resp = await client.get(
                f"/admin/documents/jobs/{job_id}",
                headers={"admin-token": "dev"},
            )
            status = status_resp.json()
            if status["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(3)

        assert status["status"] == "completed", f"Job failed: {status.get('error')}"
        assert status["total_chunks"] > 0
        assert status["completed"] > 0

    # Clean up test collection
    from qdrant_client import QdrantClient
    qdrant = QdrantClient(host="localhost", port=6333)
    try:
        qdrant.delete_collection("test_url_import")
    except Exception:
        pass
```

**Step 2: Run test (requires services)**

Run: `cd /home/apexai/BestBox && python -m pytest tests/test_url_ingestion_e2e.py -v -m e2e`
Expected: PASS if all services running, SKIP otherwise

**Step 3: Commit**

```bash
git add tests/test_url_ingestion_e2e.py
git commit -m "test: add e2e smoke test for URL ingestion pipeline"
```

---

## Summary

| Task | Component | New/Modify | Estimated Time |
|------|-----------|------------|----------------|
| 1 | LLM enrichment — core function | Create `services/llm_enrichment.py` | 10 min |
| 2 | LLM enrichment — document processing | Modify `services/llm_enrichment.py` | 5 min |
| 3 | URL download helper | Modify `services/admin_endpoints.py` | 10 min |
| 4 | Upload-URL endpoint | Modify `services/admin_endpoints.py` | 10 min |
| 5 | Enriched indexing function | Modify `services/admin_endpoints.py` | 10 min |
| 6 | Frontend — URL import tab | Modify `documents/page.tsx` | 15 min |
| 7 | KB browse — enrichment badges | Modify `kb/page.tsx` | 5 min |
| 8 | E2E smoke test | Create test file | 5 min |
