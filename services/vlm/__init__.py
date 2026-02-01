"""
VLM (Vision-Language Model) Service Integration

Provides async client for the external Qwen3-VL 8B service at 192.168.1.196:8081.
Supports multipart file upload, webhook/polling callbacks, and Redis job storage.
"""

from .client import VLMServiceClient
from .models import (
    VLMResult,
    VLMJobResponse,
    VLMAnalysis,
    ExtractedImage,
    VLMMetadata,
    VLMHealthStatus,
    JobStatus
)
from .job_store import VLMJobStore

__all__ = [
    "VLMServiceClient",
    "VLMResult",
    "VLMJobResponse",
    "VLMAnalysis",
    "ExtractedImage",
    "VLMMetadata",
    "VLMHealthStatus",
    "VLMJobStore",
    "JobStatus"
]
