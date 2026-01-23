"""Document ingestion module using Docling for parsing."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)


class DocumentIngester:
    """Ingests documents using Docling parser and extracts text with metadata."""

    def __init__(self):
        """Initialize the DocumentIngester with Docling converter."""
        self.converter = DocumentConverter()

    def ingest_document(
        self, doc_path: Path, domain: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Ingest a document and extract text with metadata.

        Args:
            doc_path: Path to the document file (PDF, DOCX, or MD)
            domain: Optional domain classification (erp, crm, it_ops, oa)

        Returns:
            Dictionary with 'text' and 'metadata' keys, or None on error.
            Metadata includes: source, file_path, file_type, domain (if provided), title

        Example:
            >>> ingester = DocumentIngester()
            >>> result = ingester.ingest_document(Path("doc.pdf"), domain="erp")
            >>> print(result["text"])
            >>> print(result["metadata"]["source"])
        """
        try:
            # Check if file exists
            if not doc_path.exists():
                logger.error(f"File not found: {doc_path}")
                return None

            # Convert document using Docling
            logger.info(f"Ingesting document: {doc_path}")
            result = self.converter.convert(str(doc_path))

            # Export to markdown to get text
            text = result.document.export_to_markdown()

            # Extract metadata
            metadata = {
                "source": doc_path.name,
                "file_path": str(doc_path.absolute()),
                "file_type": doc_path.suffix.lstrip("."),
            }

            # Add domain if provided
            if domain:
                metadata["domain"] = domain

            # Try to extract title from document (first heading or filename)
            title = doc_path.stem
            if text:
                lines = text.split("\n")
                for line in lines:
                    if line.startswith("# "):
                        title = line.lstrip("# ").strip()
                        break
            metadata["title"] = title

            logger.info(f"Successfully ingested document: {doc_path.name}")
            return {"text": text, "metadata": metadata}

        except Exception as e:
            logger.error(f"Error ingesting document {doc_path}: {e}")
            return None
