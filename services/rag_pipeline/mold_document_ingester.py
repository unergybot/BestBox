"""Mold Document Ingester - calls Docker service for P100-compatible processing.

Delegates document parsing and OCR to the Docker container running on CUDA 11.8.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Configuration - Docker service URL
DOC_SERVICE_URL = os.environ.get("DOC_SERVICE_URL", "http://localhost:8085")
DOC_TIMEOUT = float(os.environ.get("DOC_TIMEOUT", "120.0"))


class MoldDocumentIngester:
    """Document ingester that delegates to Docker service for P100 compatibility."""

    def __init__(self, service_url: str = DOC_SERVICE_URL):
        """
        Initialize the MoldDocumentIngester.
        
        Args:
            service_url: URL of the document processing Docker service
        """
        self.service_url = service_url
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=DOC_TIMEOUT)
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def check_service_health(self) -> bool:
        """Check if document processing service is available."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.service_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Document service not available: {e}")
            return False

    async def ingest_document(
        self,
        doc_path: Path,
        domain: Optional[str] = None,
        run_ocr: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Ingest a document by calling the Docker service.
        
        Args:
            doc_path: Path to document (PDF, DOCX, PPTX)
            domain: Optional domain classification
            run_ocr: Whether to run OCR on extracted images
            
        Returns:
            Dictionary with text, images, OCR results, and metadata
        """
        try:
            if not doc_path.exists():
                logger.error(f"File not found: {doc_path}")
                return None

            logger.info(f"Ingesting document: {doc_path}")
            
            client = await self._get_client()
            
            # Call Docker service /parse endpoint
            with open(doc_path, "rb") as f:
                files = {"file": (doc_path.name, f, "application/octet-stream")}
                params = {
                    "run_ocr": str(run_ocr).lower(),
                    "domain": domain or "mold"
                }
                
                response = await client.post(
                    f"{self.service_url}/parse",
                    files=files,
                    params=params
                )
            
            if response.status_code != 200:
                logger.error(f"Parse failed: {response.status_code} - {response.text}")
                return None
            
            result = response.json()
            
            logger.info(f"Successfully ingested: {doc_path.name} ({result.get('image_count', 0)} images, {len(result.get('ocr_results', []))} OCR)")
            
            return {
                "text": result.get("text", ""),
                "raw_text": result.get("raw_text", ""),
                "ocr_results": result.get("ocr_results", []),
                "image_count": result.get("image_count", 0),
                "metadata": result.get("metadata", {
                    "source": doc_path.name,
                    "domain": domain or "mold"
                })
            }

        except Exception as e:
            logger.error(f"Error ingesting document {doc_path}: {e}")
            return None


# Convenience function
async def ingest_mold_document(
    doc_path: str | Path,
    domain: Optional[str] = "mold",
    run_ocr: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to ingest a mold document.
    """
    ingester = MoldDocumentIngester()
    try:
        return await ingester.ingest_document(Path(doc_path), domain, run_ocr)
    finally:
        await ingester.close()


if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python mold_document_ingester.py <document_path>")
            sys.exit(1)
        
        doc_path = Path(sys.argv[1])
        result = await ingest_mold_document(doc_path)
        
        if result:
            print(f"Title: {result['metadata'].get('title', 'Unknown')}")
            print(f"Images: {result['image_count']}")
            print(f"OCR results: {len(result['ocr_results'])}")
            print(f"\n--- Text Preview ---\n{result['text'][:500]}...")
        else:
            print("Ingestion failed")
    
    asyncio.run(main())
