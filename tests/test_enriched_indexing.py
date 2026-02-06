"""Tests for _index_chunks_with_enrichment in admin_endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.llm_enrichment import EnrichmentResult, QAPair


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    text: str = "Sample chunk text", doc_id: str = None, chunk_index: int = 0
):
    """Build a chunk dict matching the pipeline format."""
    return {
        "text": text,
        "metadata": {
            "doc_id": doc_id or str(uuid.uuid4()),
            "source_file": "test.pdf",
            "chunk_index": chunk_index,
            "domain": "mold",
        },
    }


def _make_enrichment_result():
    """Build a sample EnrichmentResult with all fields populated."""
    return EnrichmentResult(
        summary="Flash defect summary.",
        key_concepts=["flash", "injection pressure"],
        qa_pairs=[
            QAPair(question="What causes flash?", answer="Excess pressure."),
        ],
        domain_terms=["flash", "parting line"],
        defect_type="flash",
        severity="high",
        root_cause_category="process parameter",
        mold_components=["cavity"],
        corrective_actions=["reduce pressure"],
        applicable_materials=["ABS"],
    )


def _mock_embeddings_response(count: int, dim: int = 1024):
    """Return a fake httpx.Response for the /embed endpoint."""
    embeddings = [[0.1] * dim for _ in range(count)]
    return httpx.Response(
        status_code=200,
        json={"embeddings": embeddings},
        request=httpx.Request("POST", "http://localhost:8004/embed"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_with_enrichment_creates_double_points():
    """Pass 1 chunk with enrichment. Verify 2 points are upserted (original +
    enriched). Verify set_payload is called for enrichment metadata."""
    chunk = _make_chunk()
    enrichment = _make_enrichment_result()

    # 2 texts to embed: original + enriched
    embed_response = _mock_embeddings_response(count=2)

    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.return_value = True

    # Mock httpx.AsyncClient as an async context manager
    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = embed_response

    mock_async_client_cm = MagicMock()
    mock_async_client_cm.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_async_client_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("httpx.AsyncClient", return_value=mock_async_client_cm),
        patch(
            "qdrant_client.QdrantClient", return_value=mock_qdrant
        ),
    ):
        from services.admin_endpoints import _index_chunks_with_enrichment

        result = await _index_chunks_with_enrichment(
            chunks=[chunk],
            enrichment_results=[enrichment],
            collection="test_collection",
        )

    # Should have upserted 2 points (original + enriched)
    assert result == 2
    mock_qdrant.upsert.assert_called_once()
    upsert_kwargs = mock_qdrant.upsert.call_args
    points = upsert_kwargs.kwargs.get("points", [])
    assert len(points) == 2

    # Verify chunk_type in payloads
    payloads = [p.payload for p in points]
    chunk_types = [p.get("chunk_type") for p in payloads]
    assert "original" in chunk_types
    assert "enriched" in chunk_types

    # set_payload should be called to apply enrichment metadata tags
    assert mock_qdrant.set_payload.call_count >= 1


@pytest.mark.asyncio
async def test_index_without_enrichment_falls_back():
    """Pass 1 chunk with enrichment_results=None. Verify 1 point upserted,
    no set_payload called (behaves like regular _index_chunks)."""
    chunk = _make_chunk()

    # 1 text to embed: just original
    embed_response = _mock_embeddings_response(count=1)

    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.return_value = True

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = embed_response

    mock_async_client_cm = MagicMock()
    mock_async_client_cm.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_async_client_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("httpx.AsyncClient", return_value=mock_async_client_cm),
        patch(
            "qdrant_client.QdrantClient", return_value=mock_qdrant
        ),
    ):
        from services.admin_endpoints import _index_chunks_with_enrichment

        result = await _index_chunks_with_enrichment(
            chunks=[chunk],
            enrichment_results=None,
            collection="test_collection",
        )

    # Should have upserted 1 point (original only)
    assert result == 1
    mock_qdrant.upsert.assert_called_once()
    upsert_kwargs = mock_qdrant.upsert.call_args
    points = upsert_kwargs.kwargs.get("points", [])
    assert len(points) == 1

    # Payload should have chunk_type "original"
    assert points[0].payload.get("chunk_type") == "original"

    # set_payload should NOT be called when there is no enrichment
    mock_qdrant.set_payload.assert_not_called()
