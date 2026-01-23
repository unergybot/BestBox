import pytest
from pathlib import Path
from services.rag_pipeline.ingest import DocumentIngester

def test_ingest_markdown():
    """Test ingesting markdown document"""
    ingester = DocumentIngester()

    doc_path = Path("tests/fixtures/sample.md")

    result = ingester.ingest_document(doc_path)

    # Should return document with text and metadata
    assert result is not None
    assert "text" in result
    assert "metadata" in result
    assert len(result["text"]) > 0
    assert result["metadata"]["source"] == "sample.md"

def test_ingest_with_domain():
    """Test ingesting with domain metadata"""
    ingester = DocumentIngester()

    doc_path = Path("tests/fixtures/sample.md")

    result = ingester.ingest_document(doc_path, domain="erp")

    assert result["metadata"]["domain"] == "erp"
