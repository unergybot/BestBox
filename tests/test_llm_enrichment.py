"""Tests for LLM enrichment module."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from services.llm_enrichment import enrich_chunk, EnrichmentResult, QAPair


# --- Fixtures ---

VALID_LLM_RESPONSE = {
    "summary": "This document describes a flash defect in injection molding.",
    "key_concepts": ["flash defect", "injection pressure", "mold clamping"],
    "qa_pairs": [
        {
            "question": "What causes flash in injection molding?",
            "answer": "Excessive injection pressure or insufficient clamping force.",
        },
        {
            "question": "How to prevent flash defects?",
            "answer": "Reduce injection pressure and verify mold clamping tonnage.",
        },
    ],
    "domain_terms": ["flash", "clamping force", "injection pressure"],
    "defect_type": "flash",
    "severity": "high",
    "root_cause_category": "process parameter",
    "mold_components": ["cavity", "parting line"],
    "corrective_actions": ["reduce injection pressure", "increase clamping force"],
    "applicable_materials": ["ABS", "PP"],
}


def _make_httpx_response(payload: dict, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response wrapping an OpenAI-style chat completion."""
    body = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(payload),
                },
                "finish_reason": "stop",
            }
        ],
    }
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", "http://localhost:8001/v1/chat/completions"),
    )


# --- Tests ---


@pytest.mark.asyncio
async def test_enrich_chunk_returns_structured_result():
    """Mock the httpx call to return a valid JSON LLM response.
    Verify enrich_chunk returns an EnrichmentResult with correct fields."""
    mock_response = _make_httpx_response(VALID_LLM_RESPONSE)

    with patch("services.llm_enrichment.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await enrich_chunk("Sample mold troubleshooting text about flash defects.", domain="mold")

    assert result is not None
    assert isinstance(result, EnrichmentResult)
    assert result.summary == VALID_LLM_RESPONSE["summary"]
    assert result.key_concepts == VALID_LLM_RESPONSE["key_concepts"]
    assert result.defect_type == "flash"
    assert result.severity == "high"
    assert result.root_cause_category == "process parameter"
    assert result.mold_components == ["cavity", "parting line"]
    assert result.corrective_actions == ["reduce injection pressure", "increase clamping force"]
    assert result.applicable_materials == ["ABS", "PP"]

    # Verify qa_pairs
    assert len(result.qa_pairs) == 2
    assert isinstance(result.qa_pairs[0], QAPair)
    assert result.qa_pairs[0].question == "What causes flash in injection molding?"
    assert result.qa_pairs[0].answer == "Excessive injection pressure or insufficient clamping force."

    # Verify to_enriched_text contains summary and Q&A content
    enriched_text = result.to_enriched_text()
    assert VALID_LLM_RESPONSE["summary"] in enriched_text
    assert "What causes flash in injection molding?" in enriched_text
    assert "flash defect" in enriched_text

    # Verify to_metadata returns non-empty fields
    metadata = result.to_metadata()
    assert metadata["defect_type"] == "flash"
    assert metadata["severity"] == "high"
    assert "key_concepts" in metadata


@pytest.mark.asyncio
async def test_enrich_chunk_returns_none_on_llm_failure():
    """Mock httpx to raise ConnectionError. Verify enrich_chunk returns None."""
    with patch("services.llm_enrichment.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = httpx.ConnectError("Connection refused")
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await enrich_chunk("Some text that will fail.", domain="mold")

    assert result is None


@pytest.mark.asyncio
async def test_enrich_chunk_returns_none_on_bad_json():
    """Mock LLM returning invalid JSON. Verify enrich_chunk returns None."""
    bad_body = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is not valid JSON {{{",
                },
                "finish_reason": "stop",
            }
        ],
    }
    bad_response = httpx.Response(
        status_code=200,
        json=bad_body,
        request=httpx.Request("POST", "http://localhost:8001/v1/chat/completions"),
    )

    with patch("services.llm_enrichment.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = bad_response
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await enrich_chunk("Some text with bad LLM response.", domain="mold")

    assert result is None
