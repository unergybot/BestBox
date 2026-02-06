"""
End-to-end smoke test for URL ingestion + LLM enrichment pipeline.

Requires: Agent API on :8000, Qdrant on :6333
Optional: Embeddings on :8004, LLM on :8001 (enrichment skipped if unavailable)

Run with: pytest tests/test_url_ingestion_e2e.py -v
"""

import asyncio
import time

import httpx
import pytest

API_BASE = "http://localhost:8000"
QDRANT_URL = "http://localhost:6333"
TEST_COLLECTION = "test_url_import_e2e"


def _services_available():
    """Check if required services are running."""
    import httpx as hx

    for url in [f"{API_BASE}/health", QDRANT_URL]:
        try:
            r = hx.get(url, timeout=3)
            r.raise_for_status()
        except Exception:
            return False
    return True


@pytest.fixture(autouse=True)
def skip_if_no_services():
    if not _services_available():
        pytest.skip("Agent API or Qdrant not running")


@pytest.fixture(autouse=True)
def cleanup_collection():
    """Clean up test collection after each test."""
    yield
    try:
        hx = httpx
        hx.delete(f"{QDRANT_URL}/collections/{TEST_COLLECTION}", timeout=5)
    except Exception:
        pass


def test_upload_url_endpoint_exists():
    """The upload-url endpoint should be reachable and validate input."""
    resp = httpx.post(
        f"{API_BASE}/admin/documents/upload-url",
        json={"url": "https://example.com/test.exe"},
        headers={"admin-token": "dev"},
        timeout=10,
    )
    # Should reject .exe with 400, not 404 (endpoint exists)
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


def test_upload_url_rejects_invalid_scheme():
    """Should reject non-http URLs."""
    resp = httpx.post(
        f"{API_BASE}/admin/documents/upload-url",
        json={"url": "ftp://example.com/test.pdf"},
        headers={"admin-token": "dev"},
        timeout=10,
    )
    assert resp.status_code == 400


def test_upload_url_returns_job_id_on_valid_url():
    """Should accept a valid PDF URL and return a job_id.

    Note: The actual download may fail (URL may not exist), but the
    endpoint should accept the request and create a job.
    """
    resp = httpx.post(
        f"{API_BASE}/admin/documents/upload-url",
        json={
            "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            "collection": TEST_COLLECTION,
            "domain": "general",
            "enrich": False,
            "force": True,
        },
        headers={"admin-token": "dev"},
        timeout=30,
    )
    # Should return 200 with job_id (download happens in background)
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "processing"
    assert "dummy.pdf" in data["filename"]


def test_kb_documents_endpoint_works():
    """The KB documents listing should work with the new grouping logic."""
    resp = httpx.get(
        f"{API_BASE}/admin/kb/documents",
        params={"collection": "mold_reference_kb", "limit": 10},
        headers={"admin-token": "dev"},
        timeout=10,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "documents" in data
    assert "total" in data
    # Should have 3 documents from earlier work (not 126)
    if data["total"] > 0:
        doc = data["documents"][0]
        assert "doc_id" in doc
        assert "chunk_count" in doc
        assert doc["chunk_count"] > 1  # Grouped, not individual chunks


def test_kb_document_detail_returns_chunks():
    """Clicking a document should return its chunks."""
    # First get a document ID
    list_resp = httpx.get(
        f"{API_BASE}/admin/kb/documents",
        params={"collection": "mold_reference_kb", "limit": 1},
        headers={"admin-token": "dev"},
        timeout=10,
    )
    if list_resp.status_code != 200 or not list_resp.json().get("documents"):
        pytest.skip("No documents in mold_reference_kb")

    doc_id = list_resp.json()["documents"][0]["doc_id"]

    detail_resp = httpx.get(
        f"{API_BASE}/admin/kb/documents/{doc_id}",
        params={"collection": "mold_reference_kb"},
        headers={"admin-token": "dev"},
        timeout=10,
    )
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert "chunks" in data
    assert data["total_chunks"] > 0
    assert len(data["chunks"]) > 0
    # Chunks should have text
    assert data["chunks"][0]["text"]
