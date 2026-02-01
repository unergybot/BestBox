"""
Redis-backed job result storage for VLM async jobs.

Stores job results received via webhook or polling for later retrieval.
"""

import os
import json
import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .models import VLMResult, VLMJobStatusResponse, JobStatus

logger = logging.getLogger(__name__)


class VLMJobStore:
    """
    Redis-backed storage for VLM job results.

    Used to store webhook-delivered results and allow clients
    to retrieve them without polling the VLM service.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        key_prefix: str = "vlm:job:",
        result_ttl: int = 3600  # 1 hour default TTL
    ):
        """
        Initialize job store.

        Args:
            redis_url: Redis connection URL. Defaults to VLM_REDIS_URL env var.
            key_prefix: Prefix for Redis keys
            result_ttl: TTL for stored results in seconds
        """
        self.redis_url = redis_url or os.getenv("VLM_REDIS_URL", "redis://localhost:6379/1")
        self.key_prefix = key_prefix
        self.result_ttl = result_ttl
        self._redis: Optional["aioredis.Redis"] = None

    async def _get_redis(self) -> "aioredis.Redis":
        """Get or create Redis connection"""
        if not REDIS_AVAILABLE:
            raise RuntimeError("redis package not installed. Install with: pip install redis")

        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis

    def _key(self, job_id: str) -> str:
        """Generate Redis key for job"""
        return f"{self.key_prefix}{job_id}"

    def _status_key(self, job_id: str) -> str:
        """Generate Redis key for job status"""
        return f"{self.key_prefix}{job_id}:status"

    async def store_result(self, job_id: str, result: VLMResult) -> None:
        """
        Store a completed job result.

        Args:
            job_id: Job identifier
            result: VLM result to store
        """
        try:
            redis = await self._get_redis()
            key = self._key(job_id)

            # Store result as JSON
            result_json = result.model_dump_json()
            await redis.set(key, result_json, ex=self.result_ttl)

            # Update status
            status_key = self._status_key(job_id)
            await redis.set(status_key, JobStatus.COMPLETED.value, ex=self.result_ttl)

            logger.info(f"Stored VLM result for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to store VLM result for {job_id}: {e}")
            raise

    async def store_error(self, job_id: str, error: str) -> None:
        """
        Store a job error.

        Args:
            job_id: Job identifier
            error: Error message
        """
        try:
            redis = await self._get_redis()
            key = self._key(job_id)

            error_data = {
                "job_id": job_id,
                "status": JobStatus.FAILED.value,
                "error": error,
                "timestamp": datetime.utcnow().isoformat()
            }

            await redis.set(key, json.dumps(error_data), ex=self.result_ttl)

            status_key = self._status_key(job_id)
            await redis.set(status_key, JobStatus.FAILED.value, ex=self.result_ttl)

            logger.info(f"Stored VLM error for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to store VLM error for {job_id}: {e}")
            raise

    async def get_result(self, job_id: str) -> Optional[VLMResult]:
        """
        Get a stored job result.

        Args:
            job_id: Job identifier

        Returns:
            VLMResult if found and completed, None otherwise
        """
        try:
            redis = await self._get_redis()
            key = self._key(job_id)

            result_json = await redis.get(key)
            if not result_json:
                return None

            # Check if it's an error
            data = json.loads(result_json)
            if isinstance(data, dict) and data.get("status") == JobStatus.FAILED.value:
                return None

            return VLMResult.model_validate_json(result_json)

        except Exception as e:
            logger.error(f"Failed to get VLM result for {job_id}: {e}")
            return None

    async def get_status(self, job_id: str) -> Optional[JobStatus]:
        """
        Get job status from store.

        Args:
            job_id: Job identifier

        Returns:
            JobStatus if found, None otherwise
        """
        try:
            redis = await self._get_redis()
            status_key = self._status_key(job_id)

            status = await redis.get(status_key)
            if status:
                return JobStatus(status)
            return None

        except Exception as e:
            logger.error(f"Failed to get VLM status for {job_id}: {e}")
            return None

    async def get_error(self, job_id: str) -> Optional[str]:
        """
        Get error message for a failed job.

        Args:
            job_id: Job identifier

        Returns:
            Error message if job failed, None otherwise
        """
        try:
            redis = await self._get_redis()
            key = self._key(job_id)

            result_json = await redis.get(key)
            if not result_json:
                return None

            data = json.loads(result_json)
            if isinstance(data, dict) and data.get("status") == JobStatus.FAILED.value:
                return data.get("error")
            return None

        except Exception as e:
            logger.error(f"Failed to get VLM error for {job_id}: {e}")
            return None

    async def wait_for_result(
        self,
        job_id: str,
        timeout: int = 600,
        poll_interval: float = 1.0
    ) -> Optional[VLMResult]:
        """
        Wait for a job result to appear in the store (from webhook).

        Args:
            job_id: Job identifier
            timeout: Maximum wait time in seconds
            poll_interval: How often to check for result

        Returns:
            VLMResult if found within timeout, None otherwise
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check for result
            result = await self.get_result(job_id)
            if result:
                return result

            # Check for error
            error = await self.get_error(job_id)
            if error:
                logger.warning(f"Job {job_id} failed: {error}")
                return None

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timeout waiting for job {job_id} result")
                return None

            # Wait before next check
            await asyncio.sleep(poll_interval)

    async def delete_result(self, job_id: str) -> None:
        """
        Delete a stored result.

        Args:
            job_id: Job identifier
        """
        try:
            redis = await self._get_redis()
            key = self._key(job_id)
            status_key = self._status_key(job_id)

            await redis.delete(key, status_key)
            logger.info(f"Deleted VLM result for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to delete VLM result for {job_id}: {e}")

    async def mark_pending(self, job_id: str) -> None:
        """
        Mark a job as pending (submitted).

        Args:
            job_id: Job identifier
        """
        try:
            redis = await self._get_redis()
            status_key = self._status_key(job_id)
            await redis.set(status_key, JobStatus.PENDING.value, ex=self.result_ttl)
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as pending: {e}")

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None
