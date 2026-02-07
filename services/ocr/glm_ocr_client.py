"""
GLM-OCR Client for OCR-VL escalation
Async client for GLM-OCR service via Ollama API
"""

import os
import logging
from typing import Optional
from pathlib import Path

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class GLMOCRClient:
    """Async client for GLM-OCR service."""
    
    DEFAULT_TIMEOUT = 60.0
    MAX_RETRIES = 3
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        scheduler_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """Initialize GLM-OCR client."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx package required")
        
        self.base_url = (base_url or os.getenv("GLM_OCR_URL", "http://localhost:11434")).rstrip("/")
        self.scheduler_url = (scheduler_url or os.getenv("GPU_SCHEDULER_URL", "http://localhost:8086")).rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=10.0)
            )
        return self._client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def _acquire_gpu_lock(self, worker_id: str) -> bool:
        """Acquire GPU lock via scheduler."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.scheduler_url}/lock",
                    json={
                        "worker_id": worker_id,
                        "workload_type": "ocr-vl",
                        "timeout": 300
                    },
                    timeout=10.0
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get("acquired"):
                        logger.info(f"🔒 GPU lock acquired for OCR-VL: {worker_id}")
                        return True
                    else:
                        logger.warning(f"⚠️ Could not acquire GPU lock: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"Error acquiring GPU lock: {e}")
            return False
    
    async def _release_gpu_lock(self, worker_id: str) -> None:
        """Release GPU lock via scheduler."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.scheduler_url}/lock/release",
                    params={"worker_id": worker_id},
                    timeout=10.0
                )
                logger.info(f"🔓 GPU lock released: {worker_id}")
        except Exception as e:
            logger.error(f"Error releasing GPU lock: {e}")
    
    async def extract_text(
        self,
        image_path: Path,
        prompt: str = "Extract all text from this image. Preserve the layout and formatting.",
        worker_id: Optional[str] = None
    ) -> str:
        """Extract text from image using GLM-OCR with GPU scheduling."""
        
        worker_id = worker_id or f"glm-ocr-{os.getpid()}"
        
        # Acquire GPU lock
        if not await self._acquire_gpu_lock(worker_id):
            raise RuntimeError("Could not acquire GPU lock for OCR-VL")
        
        try:
            client = await self._get_client()
            
            # Read image and encode as base64
            import base64
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            
            # Call Ollama API
            response = await client.post(
                "/api/generate",
                json={
                    "model": "glm-ocr",
                    "prompt": prompt,
                    "images": [image_data],
                    "stream": False
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            extracted_text = result.get("response", "")
            
            logger.info(f"✅ GLM-OCR extracted {len(extracted_text)} chars from {image_path.name}")
            return extracted_text
            
        finally:
            # Always release GPU lock
            await self._release_gpu_lock(worker_id)
    
    async def extract_text_bytes(
        self,
        image_bytes: bytes,
        filename: str = "image.png",
        prompt: str = "Extract all text from this image. Preserve the layout and formatting.",
        worker_id: Optional[str] = None
    ) -> str:
        """Extract text from image bytes using GLM-OCR with GPU scheduling."""
        
        worker_id = worker_id or f"glm-ocr-{os.getpid()}"
        
        # Acquire GPU lock
        if not await self._acquire_gpu_lock(worker_id):
            raise RuntimeError("Could not acquire GPU lock for OCR-VL")
        
        try:
            client = await self._get_client()
            
            # Encode as base64
            import base64
            image_data = base64.b64encode(image_bytes).decode("utf-8")
            
            # Call Ollama API
            response = await client.post(
                "/api/generate",
                json={
                    "model": "glm-ocr",
                    "prompt": prompt,
                    "images": [image_data],
                    "stream": False
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            extracted_text = result.get("response", "")
            
            logger.info(f"✅ GLM-OCR extracted {len(extracted_text)} chars from {filename}")
            return extracted_text
            
        finally:
            # Always release GPU lock
            await self._release_gpu_lock(worker_id)
    
    async def check_health(self) -> dict:
        """Check GLM-OCR service health."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags", timeout=10.0)
            response.raise_for_status()
            
            data = response.json()
            models = data.get("models", [])
            glm_ocr_available = any("glm-ocr" in m.get("name", "") for m in models)
            
            return {
                "status": "healthy" if glm_ocr_available else "model_not_loaded",
                "glm_ocr_available": glm_ocr_available,
                "models": [m.get("name") for m in models]
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Convenience function
async def extract_with_glm_ocr(
    image_path: Path,
    prompt: str = "Extract all text from this image. Preserve the layout and formatting."
) -> str:
    """Quick extract text from image using GLM-OCR."""
    async with GLMOCRClient() as client:
        return await client.extract_text(image_path, prompt)
