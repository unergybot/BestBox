import os
import httpx
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, start_service: bool = False):
        """
        Initialize embedding service client.
        
        Args:
            start_service: Whether to attempt starting the service if down (not implemented for client)
        """
        self.base_url = os.getenv("EMBEDDINGS_URL", "http://localhost:8004")
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]
            
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding for a single text string.
        """
        if not text:
            return None
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/embed",
                    json={"inputs": [text], "normalize": True}
                )
                response.raise_for_status()
                result = response.json()
                if "embeddings" in result and result["embeddings"]:
                    return result["embeddings"][0]
                return None
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts.
        """
        if not texts:
            return []
            
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/embed",
                    json={"inputs": texts, "normalize": True}
                )
                response.raise_for_status()
                result = response.json()
                return result.get("embeddings", [])
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return []
