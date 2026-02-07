"""
Docling Serve REST API client.

Wraps the Docling Serve sidecar container (:5001) for document conversion.
The Agent API proxies all conversion requests through this client —
Docling Serve is never exposed directly to the frontend.
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DOCLING_BASE_URL = os.getenv("DOCLING_SERVE_URL", "http://localhost:5001")

# Default conversion options per the design doc
DOCLING_CONVERT_OPTIONS: Dict[str, Any] = {
    "to_formats": ["md", "json"],
    "image_export_mode": "embedded",
    "do_ocr": True,
    "ocr_engine": "easyocr",
    "ocr_lang": ["en"],
    "table_mode": "accurate",
}

# Size threshold for async processing (5 MB)
ASYNC_SIZE_THRESHOLD = 5 * 1024 * 1024


class DoclingClient:
    """Async HTTP client for Docling Serve."""

    def __init__(self, base_url: str = DOCLING_BASE_URL, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Check Docling Serve health status."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/health")
                resp.raise_for_status()
                return {"status": "healthy", "detail": resp.json()}
            except Exception as e:
                return {"status": "unhealthy", "detail": str(e)}

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    async def convert_file(
        self,
        file_path: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convert a document using Docling Serve.

        For files < ASYNC_SIZE_THRESHOLD: synchronous POST to /v1/convert/file.
        For larger files: async conversion with polling.

        Returns the Docling JSON result containing structured document data,
        extracted tables, images, and Markdown text.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = path.stat().st_size
        merge_opts = {**DOCLING_CONVERT_OPTIONS, **(options or {})}

        # Force async processing for all files as the sync endpoint is unreliable
        # if file_size >= ASYNC_SIZE_THRESHOLD:
        return await self._convert_async(path, merge_opts)
        # return await self._convert_sync(path, merge_opts)

    def _build_form_data(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Build multipart form data fields from options dict."""
        data: Dict[str, Any] = {}
        for key, value in options.items():
            if isinstance(value, list):
                # Docling Serve expects repeated form fields for arrays
                data[key] = value
            elif isinstance(value, bool):
                data[key] = str(value).lower()
            else:
                data[key] = str(value)
        return data

    async def _convert_sync(
        self, path: Path, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synchronous (blocking) conversion for small files."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            form_data = self._build_form_data(options)
            with open(path, "rb") as f:
                resp = await client.post(
                    f"{self.base_url}/v1/convert/file",
                    files=[("files", (path.name, f, "application/octet-stream"))],
                    data=form_data,
                )
            resp.raise_for_status()
            result = resp.json()
            # Extract markdown from Docling response
            md = ""
            if isinstance(result, dict):
                # Docling returns {document: [...], ...} or direct result
                docs = result.get("document", [])
                if isinstance(docs, list) and docs:
                    md = docs[0].get("md_content", "") or docs[0].get("markdown", "")
                elif isinstance(result, dict):
                    md = result.get("md_content", "") or result.get("markdown", "")
            return {
                "md": md,
                "json": result,
                "document": result,
            }

    async def _convert_async(
        self, path: Path, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Async conversion with task polling for large files."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            form_data = self._build_form_data(options)
            with open(path, "rb") as f:
                resp = await client.post(
                    f"{self.base_url}/v1/convert/file/async",
                    files=[("files", (path.name, f, "application/octet-stream"))],
                    data=form_data,
                )
            resp.raise_for_status()
            task_data = resp.json()
            task_id = task_data.get("task_id")

            if not task_id:
                # Service returned a synchronous result anyway
                return task_data

            # Poll for completion
            return await self._poll_task(client, task_id)

    async def _poll_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        max_wait: float = 300.0,
        interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Poll Docling Serve for async task completion."""
        elapsed = 0.0
        while elapsed < max_wait:
            resp = await client.get(
                f"{self.base_url}/v1/status/poll/{task_id}",
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("task_status") or data.get("status")

            if status in ("success", "completed"):
                return data.get("result", data)
            if status in ("failure", "failed"):
                raise RuntimeError(
                    f"Docling conversion failed: {data.get('error', 'unknown')}"
                )

            await asyncio.sleep(interval)
            elapsed += interval

        raise TimeoutError(
            f"Docling conversion timed out after {max_wait}s for task {task_id}"
        )

    # ------------------------------------------------------------------
    # Format-specific helpers
    # ------------------------------------------------------------------

    def options_for_format(self, file_ext: str) -> Dict[str, Any]:
        """
        Return Docling conversion options tuned for a specific file format.
        """
        ext = file_ext.lower().lstrip(".")
        base = dict(DOCLING_CONVERT_OPTIONS)

        if ext in ("xlsx", "xls"):
            base.update({
                "table_mode": "accurate",
                "image_export_mode": "embedded",
            })
        elif ext == "pdf":
            base.update({
                "ocr_engine": "easyocr",
                "table_mode": "accurate",
                "image_export_mode": "embedded",
            })
        elif ext in ("jpg", "jpeg", "png", "webp", "tiff", "bmp"):
            base.update({
                "do_ocr": True,
                "image_export_mode": "embedded",
            })
        elif ext in ("docx", "pptx"):
            # Standard conversion — defaults are fine
            pass

        return base
