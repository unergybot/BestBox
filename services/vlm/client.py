"""
Async VLM Service Client

Provides async client for the external Qwen3-VL 8B service.
Supports multipart file upload, webhook/polling callbacks, and retry logic.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import json

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .models import (
    VLMResult,
    VLMJobResponse,
    VLMJobStatusResponse,
    VLMHealthStatus,
    VLMCompareResult,
    VLMBatchResult,
    VLMJobOptions,
    JobStatus,
    AnalysisDepth
)
from .job_store import VLMJobStore

logger = logging.getLogger(__name__)


class VLMServiceClient:
    """
    Async client for the external VLM service.

    Supports:
    - Multipart file upload (for direct file submission)
    - Dual callback strategy (webhook check first, polling fallback)
    - Retry logic with exponential backoff
    - Health checks
    """

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_JOB_TIMEOUT = 600  # 10 minutes for job completion
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2.0

    def __init__(
        self,
        base_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        job_store: Optional[VLMJobStore] = None
    ):
        """
        Initialize VLM service client.

        Args:
            base_url: VLM service base URL. Defaults to VLM_SERVICE_URL env var.
            webhook_url: URL for webhook callbacks. Set if webhook receiver is available.
            api_key: Optional API key for authentication.
            timeout: Default request timeout in seconds.
            job_store: Optional VLMJobStore for webhook result retrieval.
        """
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx package not installed. Install with: pip install httpx")

        self.base_url = (base_url or os.getenv("VLM_SERVICE_URL", "http://192.168.1.196:8080")).rstrip("/")
        self.webhook_url = webhook_url
        self.api_key = api_key or os.getenv("VLM_API_KEY")
        self.timeout = timeout
        self.job_store = job_store or VLMJobStore()

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout, connect=10.0)
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client and job store"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        await self.job_store.close()

    async def check_health(self) -> VLMHealthStatus:
        """
        Check VLM service availability.

        Returns:
            VLMHealthStatus with service health information

        Raises:
            httpx.HTTPError: If health check fails
        """
        client = await self._get_client()
        response = await client.get("/api/v1/health")
        response.raise_for_status()

        data = response.json()
        return VLMHealthStatus(**data)

    async def is_available(self) -> bool:
        """
        Quick check if VLM service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            health = await self.check_health()
            return health.status == "healthy"
        except Exception as e:
            logger.warning(f"VLM service health check failed: {e}")
            return False

    async def submit_file(
        self,
        file_path: Union[str, Path],
        prompt_template: Optional[str] = "mold_defect_analysis",
        options: Optional[VLMJobOptions] = None
    ) -> VLMJobResponse:
        """
        Upload file via multipart form and submit for VLM processing.

        Args:
            file_path: Path to the file to analyze
            prompt_template: Built-in template ID or None for default
            options: Processing options

        Returns:
            VLMJobResponse with job_id for tracking

        Raises:
            FileNotFoundError: If file does not exist
            httpx.HTTPError: If submission fails
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        client = await self._get_client()

        # Build multipart form data
        files = {
            "file": (file_path.name, open(file_path, "rb"), self._guess_content_type(file_path))
        }

        data = {}
        if self.webhook_url:
            data["webhook_url"] = self.webhook_url
        if prompt_template:
            data["prompt_template"] = prompt_template
        if options:
            data["options"] = options.model_dump_json()

        # Submit with retry
        response = await self._request_with_retry(
            "POST",
            "/api/v1/jobs/upload",
            files=files,
            data=data
        )

        job_response = VLMJobResponse(
            job_id=response["job_id"],
            status=JobStatus(response["status"]),
            estimated_duration=response.get("estimated_duration"),
            check_status_url=response.get("check_status_url"),
            submitted_at=datetime.fromisoformat(response["submitted_at"].replace("Z", "+00:00"))
        )

        # Mark as pending in job store
        await self.job_store.mark_pending(job_response.job_id)

        logger.info(f"Submitted VLM job {job_response.job_id} for {file_path.name}")
        return job_response

    async def submit_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        prompt_template: Optional[str] = "mold_defect_analysis",
        options: Optional[VLMJobOptions] = None
    ) -> VLMJobResponse:
        """
        Upload file bytes directly for VLM processing.

        Args:
            file_bytes: File content as bytes
            filename: Filename for the upload
            content_type: MIME type of the file
            prompt_template: Built-in template ID or None for default
            options: Processing options

        Returns:
            VLMJobResponse with job_id for tracking
        """
        client = await self._get_client()

        files = {
            "file": (filename, file_bytes, content_type)
        }

        data = {}
        if self.webhook_url:
            data["webhook_url"] = self.webhook_url
        if prompt_template:
            data["prompt_template"] = prompt_template
        if options:
            data["options"] = options.model_dump_json()

        response = await self._request_with_retry(
            "POST",
            "/api/v1/jobs/upload",
            files=files,
            data=data
        )

        job_response = VLMJobResponse(
            job_id=response["job_id"],
            status=JobStatus(response["status"]),
            estimated_duration=response.get("estimated_duration"),
            check_status_url=response.get("check_status_url"),
            submitted_at=datetime.fromisoformat(response["submitted_at"].replace("Z", "+00:00"))
        )

        await self.job_store.mark_pending(job_response.job_id)
        logger.info(f"Submitted VLM job {job_response.job_id} for {filename}")
        return job_response

    async def get_job_status(self, job_id: str) -> VLMJobStatusResponse:
        """
        Get current status of a VLM job.

        Args:
            job_id: Job identifier

        Returns:
            VLMJobStatusResponse with current status and result if completed
        """
        client = await self._get_client()
        response = await client.get(f"/api/v1/jobs/{job_id}")
        response.raise_for_status()

        data = response.json()

        result = None
        if data.get("result"):
            result = VLMResult(**data["result"])

        return VLMJobStatusResponse(
            job_id=data["job_id"],
            status=JobStatus(data["status"]),
            progress=data.get("progress"),
            estimated_remaining=data.get("estimated_remaining"),
            result=result,
            error=data.get("error"),
            completed_at=datetime.fromisoformat(data["completed_at"].replace("Z", "+00:00")) if data.get("completed_at") else None
        )

    async def wait_for_result(
        self,
        job_id: str,
        timeout: int = DEFAULT_JOB_TIMEOUT,
        poll_interval: float = 2.0
    ) -> VLMResult:
        """
        Wait for job result - tries job store first (webhook), falls back to polling.

        Args:
            job_id: Job identifier
            timeout: Maximum wait time in seconds
            poll_interval: How often to poll if needed

        Returns:
            VLMResult when job completes

        Raises:
            TimeoutError: If job doesn't complete within timeout
            RuntimeError: If job fails
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            # First, check job store (webhook may have delivered result)
            result = await self.job_store.get_result(job_id)
            if result:
                logger.info(f"Got VLM result for {job_id} from job store (webhook)")
                return result

            # Check for error in store
            error = await self.job_store.get_error(job_id)
            if error:
                raise RuntimeError(f"VLM job {job_id} failed: {error}")

            # Poll VLM service directly
            try:
                status = await self.get_job_status(job_id)

                if status.status == JobStatus.COMPLETED and status.result:
                    # Store in job store for future reference
                    await self.job_store.store_result(job_id, status.result)
                    logger.info(f"Got VLM result for {job_id} from polling")
                    return status.result

                if status.status == JobStatus.FAILED:
                    error_msg = status.error or "Unknown error"
                    await self.job_store.store_error(job_id, error_msg)
                    raise RuntimeError(f"VLM job {job_id} failed: {error_msg}")

            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    logger.warning(f"Error polling job {job_id}: {e}")

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Timeout waiting for VLM job {job_id} after {timeout}s")

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    async def analyze_file(
        self,
        file_path: Union[str, Path],
        prompt_template: Optional[str] = "mold_defect_analysis",
        options: Optional[VLMJobOptions] = None,
        timeout: int = DEFAULT_JOB_TIMEOUT
    ) -> VLMResult:
        """
        Convenience method: submit file and wait for result.

        Args:
            file_path: Path to file to analyze
            prompt_template: Built-in template ID
            options: Processing options
            timeout: Maximum wait time

        Returns:
            VLMResult with analysis
        """
        job = await self.submit_file(file_path, prompt_template, options)
        return await self.wait_for_result(job.job_id, timeout)

    async def analyze_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        prompt_template: Optional[str] = "mold_defect_analysis",
        options: Optional[VLMJobOptions] = None,
        timeout: int = DEFAULT_JOB_TIMEOUT
    ) -> VLMResult:
        """
        Convenience method: submit bytes and wait for result.

        Args:
            file_bytes: File content
            filename: Filename
            content_type: MIME type
            prompt_template: Built-in template ID
            options: Processing options
            timeout: Maximum wait time

        Returns:
            VLMResult with analysis
        """
        job = await self.submit_bytes(file_bytes, filename, content_type, prompt_template, options)
        return await self.wait_for_result(job.job_id, timeout)

    async def compare_images(
        self,
        reference_path: Union[str, Path],
        comparison_paths: List[Union[str, Path]],
        comparison_type: str = "defect_similarity",
        timeout: int = DEFAULT_JOB_TIMEOUT
    ) -> VLMCompareResult:
        """
        Compare multiple images to find similar defect patterns.

        Args:
            reference_path: Path to reference image
            comparison_paths: Paths to images to compare
            comparison_type: Type of comparison
            timeout: Maximum wait time

        Returns:
            VLMCompareResult with similarity scores

        Raises:
            httpx.HTTPError: If comparison fails
        """
        reference_path = Path(reference_path)
        if not reference_path.exists():
            raise FileNotFoundError(f"Reference image not found: {reference_path}")

        client = await self._get_client()

        # Build multipart form
        files = [
            ("reference_image", (reference_path.name, open(reference_path, "rb"), self._guess_content_type(reference_path)))
        ]

        for path in comparison_paths:
            path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"Comparison image not found: {path}")
            files.append(
                ("comparison_images[]", (path.name, open(path, "rb"), self._guess_content_type(path)))
            )

        data = {"comparison_type": comparison_type}

        response = await self._request_with_retry(
            "POST",
            "/api/v1/compare",
            files=files,
            data=data,
            timeout=timeout
        )

        return VLMCompareResult(**response)

    async def submit_batch(
        self,
        file_paths: List[Union[str, Path]],
        options: Optional[Dict[str, Any]] = None
    ) -> VLMJobResponse:
        """
        Submit multiple files for batch processing.

        Args:
            file_paths: List of file paths to process
            options: Batch processing options

        Returns:
            VLMJobResponse with batch_job_id
        """
        client = await self._get_client()

        files = []
        for path in file_paths:
            path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            files.append(
                ("files[]", (path.name, open(path, "rb"), self._guess_content_type(path)))
            )

        data = {}
        if self.webhook_url:
            data["webhook_url"] = self.webhook_url
        if options:
            data["options"] = json.dumps(options)

        response = await self._request_with_retry(
            "POST",
            "/api/v1/jobs/batch",
            files=files,
            data=data
        )

        return VLMJobResponse(
            job_id=response.get("batch_job_id", response.get("job_id")),
            status=JobStatus(response["status"]),
            estimated_duration=response.get("estimated_duration"),
            check_status_url=response.get("check_status_url"),
            submitted_at=datetime.now()
        )

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        files: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method
            url: URL path
            files: Multipart files
            data: Form data
            timeout: Optional timeout override

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPError: If all retries fail
        """
        client = await self._get_client()
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                if files:
                    response = await client.request(
                        method,
                        url,
                        files=files,
                        data=data,
                        timeout=timeout or self.timeout
                    )
                else:
                    response = await client.request(
                        method,
                        url,
                        json=data,
                        timeout=timeout or self.timeout
                    )

                response.raise_for_status()
                return response.json()

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_BACKOFF_BASE ** attempt
                    logger.warning(f"VLM request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"VLM request failed after {self.MAX_RETRIES} attempts: {e}")
                    raise

        raise last_error  # Should not reach here

    def _guess_content_type(self, file_path: Path) -> str:
        """Guess content type from file extension"""
        suffix = file_path.suffix.lower()
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
            ".md": "text/markdown"
        }
        return content_types.get(suffix, "application/octet-stream")


# Convenience function for quick usage
async def analyze_image(
    image_path: Union[str, Path],
    prompt_template: str = "mold_defect_analysis",
    timeout: int = 120
) -> VLMResult:
    """
    Quick analysis of a single image.

    Args:
        image_path: Path to image file
        prompt_template: Analysis template
        timeout: Maximum wait time

    Returns:
        VLMResult with analysis
    """
    async with VLMServiceClient() as client:
        return await client.analyze_file(image_path, prompt_template, timeout=timeout)


# Context manager support
VLMServiceClient.__aenter__ = lambda self: self._get_client()
VLMServiceClient.__aexit__ = lambda self, *args: self.close()


if __name__ == "__main__":
    # Test VLM client
    import asyncio

    async def test():
        print("Testing VLM Service Client")
        print("=" * 70)

        client = VLMServiceClient()

        # Test health check
        print("\n1. Health check...")
        try:
            health = await client.check_health()
            print(f"   Status: {health.status}")
            print(f"   Model: {health.model}")
        except Exception as e:
            print(f"   Failed: {e}")

        # Test availability
        print("\n2. Checking availability...")
        available = await client.is_available()
        print(f"   Available: {available}")

        await client.close()
        print("\n✅ VLM client test complete")

    asyncio.run(test())
