"""Enhanced Mold Document Ingester with Docling + GOT-OCR2.0 integration.

Combines Docling's document parsing with GOT-OCR2.0 for image text extraction.
Optimized for mold manufacturing documents (PDFs, PowerPoints with embedded images).
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)

# Configuration
OCR_SERVICE_URL = os.environ.get("OCR_SERVICE_URL", "http://localhost:8084")
OCR_TIMEOUT = float(os.environ.get("OCR_TIMEOUT", "60.0"))


class MoldDocumentIngester:
    """Enhanced document ingester with OCR support for mold KB documents."""

    def __init__(self, ocr_url: str = OCR_SERVICE_URL):
        """
        Initialize the MoldDocumentIngester.
        
        Args:
            ocr_url: URL of the GOT-OCR2.0 service
        """
        self.converter = DocumentConverter()
        self.ocr_url = ocr_url
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=OCR_TIMEOUT)
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def check_ocr_health(self) -> bool:
        """Check if OCR service is available."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.ocr_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"OCR service not available: {e}")
            return False

    async def ocr_image(self, image_path: Path) -> Optional[str]:
        """
        Extract text from image using OCR service.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Extracted text or None on error
        """
        try:
            client = await self._get_client()
            
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/png")}
                response = await client.post(
                    f"{self.ocr_url}/ocr",
                    files=files
                )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("text", "")
            else:
                logger.error(f"OCR failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"OCR request failed: {e}")
            return None

    def _extract_images_from_result(self, result, output_dir: Path) -> List[Dict[str, Any]]:
        """
        Extract images from Docling result.
        
        Args:
            result: Docling conversion result
            output_dir: Directory to save images
            
        Returns:
            List of image info dictionaries with paths
        """
        images = []
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Docling stores images in the document
            if hasattr(result.document, 'pictures'):
                for i, picture in enumerate(result.document.pictures):
                    if hasattr(picture, 'image') and picture.image:
                        image_path = output_dir / f"image_{i:03d}.png"
                        picture.image.save(str(image_path))
                        images.append({
                            "path": str(image_path),
                            "index": i,
                            "page": getattr(picture, 'page_no', None)
                        })
                        logger.info(f"Extracted image: {image_path}")
        except Exception as e:
            logger.warning(f"Could not extract images: {e}")
        
        return images

    async def ingest_document(
        self,
        doc_path: Path,
        domain: Optional[str] = None,
        run_ocr: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Ingest a document with full OCR processing.
        
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
            
            # Step 1: Parse document with Docling
            result = self.converter.convert(str(doc_path))
            text = result.document.export_to_markdown()
            
            # Step 2: Extract images to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                images = self._extract_images_from_result(result, temp_path)
                
                # Step 3: Run OCR on extracted images
                ocr_texts = []
                if run_ocr and images:
                    ocr_available = await self.check_ocr_health()
                    
                    if ocr_available:
                        logger.info(f"Running OCR on {len(images)} images")
                        for img_info in images:
                            ocr_text = await self.ocr_image(Path(img_info["path"]))
                            if ocr_text:
                                ocr_texts.append({
                                    "image_index": img_info["index"],
                                    "page": img_info["page"],
                                    "text": ocr_text
                                })
                    else:
                        logger.warning("OCR service not available, skipping image OCR")
            
            # Step 4: Build metadata
            metadata = {
                "source": doc_path.name,
                "file_path": str(doc_path.absolute()),
                "file_type": doc_path.suffix.lstrip("."),
                "image_count": len(images),
                "ocr_count": len(ocr_texts),
            }
            
            if domain:
                metadata["domain"] = domain
            
            # Extract title from document
            title = doc_path.stem
            if text:
                lines = text.split("\n")
                for line in lines:
                    if line.startswith("# "):
                        title = line.lstrip("# ").strip()
                        break
            metadata["title"] = title
            
            # Combine OCR text with main text
            combined_text = text
            if ocr_texts:
                combined_text += "\n\n## Extracted Image Text\n\n"
                for ocr_item in ocr_texts:
                    combined_text += f"### Image {ocr_item['image_index'] + 1}"
                    if ocr_item["page"]:
                        combined_text += f" (Page {ocr_item['page']})"
                    combined_text += f"\n\n{ocr_item['text']}\n\n"
            
            logger.info(f"Successfully ingested: {doc_path.name} ({len(images)} images, {len(ocr_texts)} OCR)")
            
            return {
                "text": combined_text,
                "raw_text": text,
                "ocr_results": ocr_texts,
                "image_count": len(images),
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Error ingesting document {doc_path}: {e}")
            return None


# Convenience function for simple usage
async def ingest_mold_document(
    doc_path: str | Path,
    domain: Optional[str] = "mold",
    run_ocr: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to ingest a mold document.
    
    Args:
        doc_path: Path to document
        domain: Domain classification (default: "mold")
        run_ocr: Whether to run OCR
        
    Returns:
        Ingestion result dictionary
    """
    ingester = MoldDocumentIngester()
    try:
        return await ingester.ingest_document(Path(doc_path), domain, run_ocr)
    finally:
        await ingester.close()


if __name__ == "__main__":
    # Test usage
    import sys
    
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python mold_document_ingester.py <document_path>")
            sys.exit(1)
        
        doc_path = Path(sys.argv[1])
        result = await ingest_mold_document(doc_path)
        
        if result:
            print(f"Title: {result['metadata']['title']}")
            print(f"Images: {result['image_count']}")
            print(f"OCR results: {len(result['ocr_results'])}")
            print(f"\n--- Text Preview ---\n{result['text'][:500]}...")
        else:
            print("Ingestion failed")
    
    asyncio.run(main())
