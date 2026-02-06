"""Tests for _download_url helper in admin_endpoints."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_tmp_upload_dir(tmp_path, monkeypatch):
    """Redirect UPLOAD_DIR to a temporary directory for every test."""
    import services.admin_endpoints as mod

    monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path)


# ---------------------------------------------------------------------------
# Helpers for building mock httpx responses
# ---------------------------------------------------------------------------

def _make_mock_response(*, status_code=200, headers=None, content=b"%PDF-fake"):
    """Return a mock httpx.Response suitable for async streaming."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {"content-length": str(len(content))}

    # aiter_bytes must be an async generator
    async def _aiter_bytes(chunk_size=8192):
        yield content

    resp.aiter_bytes = _aiter_bytes

    # Support async context manager (async with client.stream(...) as resp)
    resp.aclose = AsyncMock()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _make_mock_client(response):
    """Return a mock httpx.AsyncClient whose .stream() returns *response*."""
    client = MagicMock()
    client.stream = MagicMock(return_value=response)
    client.aclose = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_url_saves_file(tmp_path, monkeypatch):
    """A successful PDF download should save the file and return its path."""
    import services.admin_endpoints as mod

    pdf_bytes = b"%PDF-1.4 fake content for test"
    mock_resp = _make_mock_response(
        status_code=200,
        headers={"content-length": str(len(pdf_bytes))},
        content=pdf_bytes,
    )
    mock_client = _make_mock_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        saved_path, original_name = await mod._download_url(
            "https://example.com/reports/annual_report.pdf"
        )

    assert saved_path.exists(), "Downloaded file should exist on disk"
    assert saved_path.suffix == ".pdf"
    assert original_name == "annual_report.pdf"
    assert saved_path.read_bytes() == pdf_bytes


@pytest.mark.asyncio
async def test_download_url_rejects_bad_extension():
    """A URL pointing to a disallowed extension (.exe) should raise 400."""
    import services.admin_endpoints as mod

    with pytest.raises(HTTPException) as exc_info:
        await mod._download_url("https://example.com/malware.exe")

    assert exc_info.value.status_code == 400
    assert "Unsupported" in str(exc_info.value.detail) or "extension" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_download_url_rejects_bad_scheme():
    """An ftp:// URL should be rejected with 400."""
    import services.admin_endpoints as mod

    with pytest.raises(HTTPException) as exc_info:
        await mod._download_url("ftp://example.com/file.pdf")

    assert exc_info.value.status_code == 400
    assert "http" in str(exc_info.value.detail).lower()
