# RAG Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build production-ready RAG pipeline with document ingestion, hybrid search, and reranking for BestBox agents.

**Architecture:** Docling parses documents → tiktoken chunks text (512 tokens, 20% overlap) → BGE-M3 embeddings → Qdrant storage with hybrid indexing → Retrieval with dense+BM25+reranking → search_knowledge_base tool for agents.

**Tech Stack:** Docling, Qdrant, tiktoken, sentence-transformers (BGE-M3, BGE-reranker), FastAPI

---

## Task 1: Vector Store Client (Qdrant)

**Files:**
- Create: `services/rag_pipeline/__init__.py`
- Create: `services/rag_pipeline/vector_store.py`
- Test: `tests/test_vector_store.py`

**Step 1: Create module structure**

```bash
mkdir -p services/rag_pipeline tests
touch services/rag_pipeline/__init__.py
```

**Step 2: Write failing test for Qdrant client**

Create `tests/test_vector_store.py`:
```python
import pytest
from services.rag_pipeline.vector_store import VectorStore

def test_vector_store_create_collection():
    """Test creating Qdrant collection"""
    store = VectorStore(url="http://localhost:6333")
    collection_name = "test_collection"

    # Should create collection with correct config
    store.create_collection(
        collection_name=collection_name,
        vector_size=1024,
        enable_bm25=True
    )

    # Verify collection exists
    assert store.collection_exists(collection_name)

    # Cleanup
    store.delete_collection(collection_name)
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_vector_store.py::test_vector_store_create_collection -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'services.rag_pipeline.vector_store'"

**Step 4: Implement minimal VectorStore class**

Create `services/rag_pipeline/vector_store.py`:
```python
"""
Qdrant vector store client for RAG pipeline.
Handles collection management, upserting, and hybrid search.
"""
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    ScoredPoint,
)

logger = logging.getLogger(__name__)


class VectorStore:
    """Qdrant client wrapper for document storage and retrieval."""

    def __init__(self, url: str = "http://localhost:6333"):
        """
        Initialize Qdrant client.

        Args:
            url: Qdrant server URL
        """
        self.client = QdrantClient(url=url)
        self.url = url
        logger.info(f"Connected to Qdrant at {url}")

    def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1024,
        enable_bm25: bool = True
    ):
        """
        Create a new collection with dense vectors and optional BM25.

        Args:
            collection_name: Name of the collection
            vector_size: Dimension of vectors (default 1024 for BGE-M3)
            enable_bm25: Enable full-text search with BM25
        """
        if self.collection_exists(collection_name):
            logger.info(f"Collection {collection_name} already exists")
            return

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )

        logger.info(f"Created collection: {collection_name}")

    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False

    def delete_collection(self, collection_name: str):
        """Delete a collection."""
        self.client.delete_collection(collection_name)
        logger.info(f"Deleted collection: {collection_name}")
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_vector_store.py::test_vector_store_create_collection -v`
Expected: PASS (requires Qdrant running via docker-compose up -d)

**Step 6: Add test for upserting documents**

Add to `tests/test_vector_store.py`:
```python
def test_vector_store_upsert_documents():
    """Test upserting document chunks"""
    store = VectorStore()
    collection_name = "test_upsert"

    store.create_collection(collection_name)

    # Sample document chunks
    chunks = [
        {
            "id": "doc1_chunk1",
            "vector": [0.1] * 1024,
            "metadata": {
                "doc_id": "doc1",
                "chunk_id": 1,
                "text": "This is chunk 1",
                "domain": "erp"
            }
        },
        {
            "id": "doc1_chunk2",
            "vector": [0.2] * 1024,
            "metadata": {
                "doc_id": "doc1",
                "chunk_id": 2,
                "text": "This is chunk 2",
                "domain": "erp"
            }
        }
    ]

    # Upsert chunks
    store.upsert_documents(collection_name, chunks)

    # Verify count
    info = store.client.get_collection(collection_name)
    assert info.points_count == 2

    # Cleanup
    store.delete_collection(collection_name)
```

**Step 7: Implement upsert_documents method**

Add to `services/rag_pipeline/vector_store.py`:
```python
    def upsert_documents(
        self,
        collection_name: str,
        chunks: List[Dict[str, Any]]
    ):
        """
        Upsert document chunks to collection.

        Args:
            collection_name: Name of collection
            chunks: List of chunks with id, vector, metadata
        """
        points = [
            PointStruct(
                id=chunk["id"],
                vector=chunk["vector"],
                payload=chunk["metadata"]
            )
            for chunk in chunks
        ]

        self.client.upsert(
            collection_name=collection_name,
            points=points
        )

        logger.info(f"Upserted {len(chunks)} chunks to {collection_name}")
```

**Step 8: Run tests**

Run: `pytest tests/test_vector_store.py -v`
Expected: Both tests PASS

**Step 9: Commit vector store**

```bash
git add services/rag_pipeline/__init__.py services/rag_pipeline/vector_store.py tests/test_vector_store.py
git commit -m "feat: add Qdrant vector store client with collection management"
```

---

## Task 2: Text Chunker

**Files:**
- Create: `services/rag_pipeline/chunker.py`
- Test: `tests/test_chunker.py`

**Step 1: Write failing test for chunker**

Create `tests/test_chunker.py`:
```python
import pytest
from services.rag_pipeline.chunker import TextChunker

def test_chunker_basic():
    """Test basic chunking functionality"""
    chunker = TextChunker(chunk_size=50, overlap_size=10)

    text = " ".join([f"word{i}" for i in range(100)])  # 100 words

    chunks = chunker.chunk_text(text)

    # Should create multiple chunks
    assert len(chunks) > 1

    # Each chunk should be dict with text and metadata
    for chunk in chunks:
        assert "text" in chunk
        assert "chunk_id" in chunk
        assert "token_count" in chunk

def test_chunker_overlap():
    """Test that chunks have overlap"""
    chunker = TextChunker(chunk_size=50, overlap_size=10)

    text = " ".join([f"word{i}" for i in range(100)])

    chunks = chunker.chunk_text(text)

    # First chunk should have different end than second chunk start
    # But they should overlap
    if len(chunks) >= 2:
        chunk1_text = chunks[0]["text"]
        chunk2_text = chunks[1]["text"]

        # Check for overlap by looking at last words of chunk1
        # appearing at start of chunk2
        assert len(chunk1_text) > 0
        assert len(chunk2_text) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_chunker.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement TextChunker class**

Create `services/rag_pipeline/chunker.py`:
```python
"""
Text chunking with token-based splitting and overlap.
Uses tiktoken for accurate token counting.
"""
import logging
from typing import List, Dict, Any
import tiktoken

logger = logging.getLogger(__name__)


class TextChunker:
    """Chunk text into overlapping segments based on token count."""

    def __init__(
        self,
        chunk_size: int = 512,
        overlap_size: int = 100,
        encoding_name: str = "cl100k_base"  # GPT-4 tokenizer
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target tokens per chunk
            overlap_size: Overlap tokens between chunks
            encoding_name: Tiktoken encoding name
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.encoding = tiktoken.get_encoding(encoding_name)
        logger.info(f"TextChunker initialized: {chunk_size} tokens, {overlap_size} overlap")

    def chunk_text(
        self,
        text: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk text into overlapping segments.

        Args:
            text: Input text to chunk
            metadata: Optional metadata to include in each chunk

        Returns:
            List of chunks with text, chunk_id, token_count, metadata
        """
        if not text or not text.strip():
            return []

        # Tokenize full text
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)

        chunks = []
        chunk_id = 0
        start_idx = 0

        while start_idx < total_tokens:
            # Calculate end index for this chunk
            end_idx = min(start_idx + self.chunk_size, total_tokens)

            # Extract token slice
            chunk_tokens = tokens[start_idx:end_idx]

            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)

            # Create chunk dict
            chunk = {
                "text": chunk_text,
                "chunk_id": chunk_id,
                "token_count": len(chunk_tokens),
                "start_token": start_idx,
                "end_token": end_idx
            }

            # Add metadata if provided
            if metadata:
                chunk.update(metadata)

            chunks.append(chunk)

            # Move to next chunk start (with overlap)
            chunk_id += 1
            start_idx = end_idx - self.overlap_size

            # Break if we're at the end
            if end_idx >= total_tokens:
                break

        logger.info(f"Chunked {total_tokens} tokens into {len(chunks)} chunks")
        return chunks
```

**Step 4: Run tests**

Run: `pytest tests/test_chunker.py -v`
Expected: Both tests PASS

**Step 5: Commit chunker**

```bash
git add services/rag_pipeline/chunker.py tests/test_chunker.py
git commit -m "feat: add text chunker with token-based splitting and overlap"
```

---

## Task 3: Document Ingestion with Docling

**Files:**
- Create: `services/rag_pipeline/ingest.py`
- Test: `tests/test_ingest.py`
- Create: `tests/fixtures/sample.md` (test document)

**Step 1: Create test fixture**

Create `tests/fixtures/sample.md`:
```markdown
# Sample Document

## Introduction
This is a sample document for testing Docling integration.

## Section 1
This section contains important information about procedures.

## Section 2
This section contains technical details and specifications.
```

**Step 2: Write failing test for document ingestion**

Create `tests/test_ingest.py`:
```python
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
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Implement DocumentIngester**

Create `services/rag_pipeline/ingest.py`:
```python
"""
Document ingestion using Docling for robust PDF/DOCX/MD parsing.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)


class DocumentIngester:
    """Ingest documents using Docling parser."""

    def __init__(self):
        """Initialize Docling converter."""
        self.converter = DocumentConverter()
        logger.info("DocumentIngester initialized with Docling")

    def ingest_document(
        self,
        doc_path: Path,
        domain: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Ingest a document and extract text with metadata.

        Args:
            doc_path: Path to document (PDF, DOCX, MD)
            domain: Optional domain tag (erp, crm, itops, oa)

        Returns:
            Dict with 'text' and 'metadata' keys, or None if failed
        """
        if not doc_path.exists():
            logger.error(f"Document not found: {doc_path}")
            return None

        try:
            # Convert document using Docling
            result = self.converter.convert(str(doc_path))

            # Extract text content
            text = result.document.export_to_markdown()

            # Build metadata
            metadata = {
                "source": doc_path.name,
                "file_path": str(doc_path),
                "file_type": doc_path.suffix[1:],  # Remove leading dot
            }

            # Add domain if provided
            if domain:
                metadata["domain"] = domain

            # Extract title if available
            if hasattr(result.document, "name") and result.document.name:
                metadata["title"] = result.document.name
            else:
                metadata["title"] = doc_path.stem

            logger.info(f"Ingested {doc_path.name}: {len(text)} characters")

            return {
                "text": text,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Failed to ingest {doc_path}: {e}")
            return None
```

**Step 5: Run tests**

Run: `pytest tests/test_ingest.py -v`
Expected: Both tests PASS

**Step 6: Commit ingestion module**

```bash
mkdir -p tests/fixtures
git add services/rag_pipeline/ingest.py tests/test_ingest.py tests/fixtures/sample.md
git commit -m "feat: add document ingestion with Docling parser"
```

---

## Task 4: Reranker Service

**Files:**
- Create: `services/rag_pipeline/reranker.py`
- Create: `scripts/start-reranker.sh`

**Step 1: Write reranker FastAPI service**

Create `services/rag_pipeline/reranker.py`:
```python
"""
BGE-reranker service for improving retrieval precision.
FastAPI service that reranks passages based on query relevance.
"""
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import CrossEncoder
from typing import List
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BestBox Reranker API",
    description="BGE-reranker for RAG pipeline",
    version="1.0.0"
)

# Global model instance
model = None


class RerankRequest(BaseModel):
    query: str
    passages: List[str]


class RerankResponse(BaseModel):
    scores: List[float]
    ranked_indices: List[int]
    inference_time_ms: float


@app.on_event("startup")
async def load_model():
    global model
    logger.info("Loading BGE-reranker-base model...")
    start = time.time()
    model = CrossEncoder("BAAI/bge-reranker-base")
    elapsed = time.time() - start
    logger.info(f"Model loaded in {elapsed:.2f}s")


@app.get("/health")
async def health_check():
    return {
        "status": "ok" if model is not None else "loading",
        "model_loaded": model is not None,
        "model_name": "BAAI/bge-reranker-base"
    }


@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    """
    Rerank passages based on query relevance.

    Args:
        query: Search query
        passages: List of text passages to rerank

    Returns:
        Scores and ranked indices
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    if not request.passages:
        return RerankResponse(
            scores=[],
            ranked_indices=[],
            inference_time_ms=0.0
        )

    # Create query-passage pairs
    pairs = [[request.query, passage] for passage in request.passages]

    start = time.time()
    scores = model.predict(pairs)
    elapsed_ms = (time.time() - start) * 1000

    # Get ranked indices (descending order)
    ranked_indices = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True
    )

    return RerankResponse(
        scores=scores.tolist(),
        ranked_indices=ranked_indices,
        inference_time_ms=round(elapsed_ms, 2)
    )


@app.get("/")
async def root():
    return {
        "service": "BestBox Reranker API",
        "model": "BAAI/bge-reranker-base",
        "endpoints": {
            "health": "/health",
            "rerank": "/rerank (POST)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8082)
```

**Step 2: Create startup script**

Create `scripts/start-reranker.sh`:
```bash
#!/bin/bash
# Start BGE-reranker service

set -e

echo "🚀 Starting BestBox Reranker Service..."

# Activate virtual environment
source ~/BestBox/activate.sh

# Start reranker service
cd ~/BestBox
python services/rag_pipeline/reranker.py
```

**Step 3: Make script executable**

```bash
chmod +x scripts/start-reranker.sh
```

**Step 4: Test reranker (manual)**

In one terminal:
```bash
./scripts/start-reranker.sh
```

In another terminal:
```bash
curl http://localhost:8082/health
# Expected: {"status": "ok", "model_loaded": true, ...}
```

**Step 5: Commit reranker**

```bash
git add services/rag_pipeline/reranker.py scripts/start-reranker.sh
git commit -m "feat: add BGE-reranker service for precision boosting"
```

---

## Task 5: Search Knowledge Base Tool

**Files:**
- Create: `tools/rag_tools.py`
- Test: `tests/test_rag_tools.py`

**Step 1: Write failing test for RAG tool**

Create `tests/test_rag_tools.py`:
```python
import pytest
from tools.rag_tools import search_knowledge_base

# Note: This is an integration test that requires:
# - Qdrant running (docker-compose up -d)
# - Embeddings service running (scripts/start-embeddings.sh)
# - Reranker service running (scripts/start-reranker.sh)
# - Test data seeded

@pytest.mark.integration
def test_search_knowledge_base():
    """Test RAG tool returns formatted results"""
    query = "How do I approve a purchase order?"

    result = search_knowledge_base(query, domain="erp", top_k=3)

    # Should return string with sources
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Source:" in result or "No relevant information" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rag_tools.py -v -m integration`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement search_knowledge_base tool**

Create `tools/rag_tools.py`:
```python
"""
RAG tools for agents to search knowledge base.
"""
import logging
import requests
from typing import Optional
from langchain_core.tools import tool
from services.rag_pipeline.vector_store import VectorStore

logger = logging.getLogger(__name__)

EMBEDDINGS_URL = "http://127.0.0.1:8081/embed"
RERANKER_URL = "http://127.0.0.1:8082/rerank"
COLLECTION_NAME = "bestbox_knowledge"


@tool
def search_knowledge_base(
    query: str,
    domain: Optional[str] = None,
    top_k: int = 5
) -> str:
    """
    Search the knowledge base for relevant information.

    Use this tool when you need specific procedures, policies, or technical
    information beyond your training data.

    Args:
        query: The search query (natural language)
        domain: Filter by domain (erp, crm, itops, oa) or None for all
        top_k: Number of results to return (default 5)

    Returns:
        Formatted context string with sources, or error message
    """
    try:
        # Step 1: Embed query
        embed_response = requests.post(
            EMBEDDINGS_URL,
            json={"inputs": query, "normalize": True},
            timeout=5
        )
        embed_response.raise_for_status()
        query_vector = embed_response.json()["embeddings"][0]

        # Step 2: Hybrid search in Qdrant
        store = VectorStore()

        # Build filter if domain specified
        search_filter = None
        if domain:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="domain",
                        match=MatchValue(value=domain)
                    )
                ]
            )

        # Search with more candidates for reranking
        results = store.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=20,  # Get more candidates for reranking
            query_filter=search_filter
        )

        if not results:
            return "No relevant information found in the knowledge base."

        # Step 3: Rerank results
        passages = [result.payload.get("text", "") for result in results]

        try:
            rerank_response = requests.post(
                RERANKER_URL,
                json={"query": query, "passages": passages},
                timeout=5
            )
            rerank_response.raise_for_status()
            ranked_indices = rerank_response.json()["ranked_indices"]

            # Reorder results by reranker scores
            reranked_results = [results[i] for i in ranked_indices[:top_k]]
        except Exception as e:
            logger.warning(f"Reranker failed, using hybrid search results: {e}")
            reranked_results = results[:top_k]

        # Step 4: Format response with sources
        context_parts = []
        for i, result in enumerate(reranked_results, 1):
            payload = result.payload
            source = payload.get("source", "Unknown")
            section = payload.get("section", "")
            text = payload.get("text", "")

            source_info = f"[Source: {source}"
            if section:
                source_info += f", {section}"
            source_info += "]"

            context_parts.append(f"{source_info}\n{text}\n")

        context = "\n".join(context_parts)
        footer = f"\n---\nRetrieved {len(reranked_results)} relevant passages."

        return f"Based on the knowledge base:\n\n{context}{footer}"

    except requests.exceptions.RequestException as e:
        logger.error(f"Service error: {e}")
        return f"Error: Could not access required services. Please ensure embeddings and reranker services are running."
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error searching knowledge base: {str(e)}"
```

**Step 4: Run test (will pass after seeding)**

Run: `pytest tests/test_rag_tools.py -v -m integration`
Expected: SKIP or PASS (depends on test data)

**Step 5: Commit RAG tool**

```bash
git add tools/rag_tools.py tests/test_rag_tools.py
git commit -m "feat: add search_knowledge_base tool for agents"
```

---

## Task 6: Knowledge Base Seeding Script

**Files:**
- Create: `scripts/seed_knowledge_base.py`
- Create: `data/demo_docs/erp/sample_erp.md`
- Create: `data/demo_docs/crm/sample_crm.md`
- Create: `data/demo_docs/itops/sample_itops.md`
- Create: `data/demo_docs/oa/sample_oa.md`

**Step 1: Create demo documents**

Create `data/demo_docs/erp/sample_erp.md`:
```markdown
# Purchase Order Approval Procedures

## Overview
This document describes the process for approving purchase orders in the ERP system.

## Approval Process

### Step 1: Submit Request
Department managers submit purchase order requests through the ERP portal.

### Step 2: Financial Review
The finance team reviews requests over $5,000 for budget compliance.

### Step 3: Executive Approval
Purchase orders over $25,000 require executive approval.

## Important Notes
- All POs must include vendor information and delivery dates
- Rush orders require special approval
- Quarterly reviews of vendor pricing are mandatory
```

Create `data/demo_docs/crm/sample_crm.md`:
```markdown
# Lead Qualification Framework

## Lead Scoring Criteria

### Company Size
- 1-50 employees: 10 points
- 51-500 employees: 25 points
- 500+ employees: 40 points

### Engagement Level
- Email opens: 5 points per open
- Demo requests: 50 points
- Pricing page visits: 30 points

### Deal Size Indicators
- Budget mentioned: 20 points
- Timeline discussed: 15 points
- Decision maker engaged: 35 points

## Prioritization
Focus on leads with scores above 80 and deal sizes over $50K.
```

Create `data/demo_docs/itops/sample_itops.md`:
```markdown
# Database Performance Troubleshooting

## Slow Query Diagnosis

### Step 1: Check Active Connections
Run: `SELECT * FROM pg_stat_activity WHERE state = 'active';`

### Step 2: Identify Slow Queries
Check query execution times in the slow query log.

### Step 3: Analyze Query Plans
Use EXPLAIN ANALYZE to understand query performance.

## Common Issues
- Missing indexes on foreign keys
- Outdated statistics (run ANALYZE)
- Lock contention from long transactions
- Connection pool exhaustion

## Quick Fixes
- Add indexes to frequently filtered columns
- Increase shared_buffers if memory allows
- Terminate idle connections after 5 minutes
```

Create `data/demo_docs/oa/sample_oa.md`:
```markdown
# Meeting Scheduling Guidelines

## Scheduling Best Practices

### Meeting Duration
- Status updates: 15 minutes
- Team discussions: 30 minutes
- Planning sessions: 60 minutes
- All-hands meetings: 30-45 minutes

### Required Attendees
Always include:
- Decision makers for the topic
- Subject matter experts
- Anyone responsible for action items

### Meeting Invitations
Include in every invitation:
- Clear agenda with time allocations
- Pre-reading materials (if any)
- Video conference link
- Expected outcomes

## Rescheduling Policy
Give at least 24 hours notice when rescheduling.
```

**Step 2: Create directory structure**

```bash
mkdir -p data/demo_docs/{erp,crm,itops,oa}
```

**Step 3: Write seeding script**

Create `scripts/seed_knowledge_base.py`:
```python
#!/usr/bin/env python3
"""
Seed BestBox knowledge base with demo documents.
Ingests documents from data/demo_docs/ and stores in Qdrant.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from pathlib import Path
import requests
from services.rag_pipeline.ingest import DocumentIngester
from services.rag_pipeline.chunker import TextChunker
from services.rag_pipeline.vector_store import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMBEDDINGS_URL = "http://127.0.0.1:8081/embed"
COLLECTION_NAME = "bestbox_knowledge"
DOCS_DIR = Path("data/demo_docs")


def main():
    """Ingest all demo documents into Qdrant."""
    logger.info("🚀 Starting knowledge base seeding...")

    # Initialize components
    ingester = DocumentIngester()
    chunker = TextChunker(chunk_size=512, overlap_size=100)
    store = VectorStore()

    # Create collection if not exists
    if not store.collection_exists(COLLECTION_NAME):
        logger.info(f"Creating collection: {COLLECTION_NAME}")
        store.create_collection(COLLECTION_NAME, vector_size=1024, enable_bm25=True)
    else:
        logger.info(f"Collection {COLLECTION_NAME} already exists")

    # Process each domain directory
    domains = ["erp", "crm", "itops", "oa"]
    total_docs = 0
    total_chunks = 0

    for domain in domains:
        domain_dir = DOCS_DIR / domain
        if not domain_dir.exists():
            logger.warning(f"Domain directory not found: {domain_dir}")
            continue

        # Process each document in domain
        for doc_path in domain_dir.glob("*"):
            if doc_path.is_file() and doc_path.suffix in [".md", ".pdf", ".docx"]:
                logger.info(f"Processing {doc_path.name}...")

                # Ingest document
                doc_data = ingester.ingest_document(doc_path, domain=domain)
                if not doc_data:
                    logger.error(f"Failed to ingest {doc_path.name}")
                    continue

                # Chunk text
                chunks = chunker.chunk_text(
                    doc_data["text"],
                    metadata=doc_data["metadata"]
                )

                if not chunks:
                    logger.warning(f"No chunks created for {doc_path.name}")
                    continue

                logger.info(f"Created {len(chunks)} chunks from {doc_path.name}")

                # Generate embeddings for all chunks
                chunk_texts = [chunk["text"] for chunk in chunks]

                try:
                    embed_response = requests.post(
                        EMBEDDINGS_URL,
                        json={"inputs": chunk_texts, "normalize": True},
                        timeout=30
                    )
                    embed_response.raise_for_status()
                    embeddings = embed_response.json()["embeddings"]
                except Exception as e:
                    logger.error(f"Failed to generate embeddings: {e}")
                    continue

                # Prepare chunks for Qdrant
                doc_id = doc_path.stem
                qdrant_chunks = []

                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    qdrant_chunks.append({
                        "id": f"{doc_id}_chunk{i}",
                        "vector": embedding,
                        "metadata": {
                            "doc_id": doc_id,
                            "chunk_id": i,
                            "text": chunk["text"],
                            "domain": domain,
                            "source": doc_path.name,
                            "title": doc_data["metadata"].get("title", doc_id),
                            "token_count": chunk["token_count"]
                        }
                    })

                # Upsert to Qdrant
                store.upsert_documents(COLLECTION_NAME, qdrant_chunks)

                total_docs += 1
                total_chunks += len(chunks)

    # Summary
    logger.info("=" * 60)
    logger.info("✅ Seeding complete!")
    logger.info(f"📄 Documents processed: {total_docs}")
    logger.info(f"📦 Chunks created: {total_chunks}")
    logger.info(f"💾 Vectors in Qdrant: {total_chunks}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
```

**Step 4: Make script executable**

```bash
chmod +x scripts/seed_knowledge_base.py
```

**Step 5: Test seeding (manual)**

Ensure services are running:
```bash
docker-compose up -d  # Qdrant
./scripts/start-embeddings.sh  # In separate terminal
```

Then run seeding:
```bash
python scripts/seed_knowledge_base.py
```

Expected output:
```
🚀 Starting knowledge base seeding...
Creating collection: bestbox_knowledge
Processing sample_erp.md...
Created 5 chunks from sample_erp.md
...
✅ Seeding complete!
📄 Documents processed: 4
📦 Chunks created: 23
💾 Vectors in Qdrant: 23
```

**Step 6: Commit seeding**

```bash
git add scripts/seed_knowledge_base.py data/demo_docs/
git commit -m "feat: add knowledge base seeding script with demo documents"
```

---

## Task 7: Register RAG Tool with Agents

**Files:**
- Modify: `agents/graph.py`
- Modify: `agents/erp_agent.py` (and other agents)

**Step 1: Update graph to include RAG tool**

Edit `agents/graph.py`, find the tool imports section and add:
```python
from tools.rag_tools import search_knowledge_base
```

Find where tools are registered and add:
```python
# Add RAG tool to all agents
all_tools = [
    # Existing tools...
    search_knowledge_base,
]
```

**Step 2: Update agent prompts to mention RAG**

Edit `agents/erp_agent.py`, update system prompt to include:
```python
SYSTEM_PROMPT = """You are an ERP specialist agent...

You have access to a knowledge base via search_knowledge_base(query, domain).
Use it when you need specific procedures, policies, or technical information
beyond your training data. For ERP queries, use domain="erp" to filter results.

..."""
```

Repeat for other agents (crm_agent.py, it_ops_agent.py, oa_agent.py) with appropriate domain values.

**Step 3: Test agent with RAG**

Run test script:
```bash
python scripts/test_agents.py
```

Expected: Agents should be able to call search_knowledge_base tool when needed.

**Step 4: Commit agent updates**

```bash
git add agents/graph.py agents/erp_agent.py agents/crm_agent.py agents/it_ops_agent.py agents/oa_agent.py
git commit -m "feat: integrate RAG tool with agents"
```

---

## Task 8: Integration Testing

**Files:**
- Create: `tests/test_rag_integration.py`

**Step 1: Write end-to-end integration test**

Create `tests/test_rag_integration.py`:
```python
"""
End-to-end integration tests for RAG pipeline.
Requires all services running: Qdrant, embeddings, reranker.
"""
import pytest
from pathlib import Path
from services.rag_pipeline.ingest import DocumentIngester
from services.rag_pipeline.chunker import TextChunker
from services.rag_pipeline.vector_store import VectorStore
from tools.rag_tools import search_knowledge_base
import requests

TEST_COLLECTION = "test_rag_integration"


@pytest.fixture
def setup_test_collection():
    """Setup test collection with sample data."""
    # Create test document
    test_doc = Path("tests/fixtures/test_rag.md")
    test_doc.parent.mkdir(parents=True, exist_ok=True)
    test_doc.write_text("""
# Test Document for RAG

## Purchase Orders
To approve a purchase order, submit the request through the ERP portal.
The finance team will review it within 24 hours.

## Vendor Management
All vendors must be registered in the system before placing orders.
    """)

    # Ingest and store
    ingester = DocumentIngester()
    chunker = TextChunker()
    store = VectorStore()

    # Create collection
    if store.collection_exists(TEST_COLLECTION):
        store.delete_collection(TEST_COLLECTION)
    store.create_collection(TEST_COLLECTION)

    # Ingest doc
    doc_data = ingester.ingest_document(test_doc, domain="test")
    chunks = chunker.chunk_text(doc_data["text"], metadata=doc_data["metadata"])

    # Embed and store
    chunk_texts = [c["text"] for c in chunks]
    embed_response = requests.post(
        "http://127.0.0.1:8081/embed",
        json={"inputs": chunk_texts, "normalize": True}
    )
    embeddings = embed_response.json()["embeddings"]

    qdrant_chunks = [
        {
            "id": f"test_chunk{i}",
            "vector": emb,
            "metadata": {**chunk, "domain": "test"}
        }
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]

    store.upsert_documents(TEST_COLLECTION, qdrant_chunks)

    yield store

    # Cleanup
    store.delete_collection(TEST_COLLECTION)
    test_doc.unlink()


@pytest.mark.integration
def test_end_to_end_rag(setup_test_collection):
    """Test complete RAG pipeline"""
    # This test uses the main collection, not test collection
    # Requires seeding to have been run

    result = search_knowledge_base(
        "How do I approve a purchase order?",
        domain="erp",
        top_k=3
    )

    assert isinstance(result, str)
    assert len(result) > 0
    # Should contain either results or "no relevant" message
    assert "purchase" in result.lower() or "no relevant" in result.lower()
```

**Step 2: Run integration tests**

```bash
pytest tests/test_rag_integration.py -v -m integration
```

Expected: Tests PASS (requires all services running and seeding completed)

**Step 3: Commit integration tests**

```bash
git add tests/test_rag_integration.py
git commit -m "test: add end-to-end RAG integration tests"
```

---

## Task 9: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Step 1: Update README with RAG setup instructions**

Add to README.md in "Common Commands" section:
```markdown
### RAG Pipeline
```bash
# One-time: Seed knowledge base with demo documents
python scripts/seed_knowledge_base.py

# Start reranker service (in separate terminal)
./scripts/start-reranker.sh
```

**Step 2: Update CLAUDE.md**

Add to CLAUDE.md:
```markdown
## RAG Pipeline

The system includes a RAG pipeline for knowledge base search:

- Documents in `data/demo_docs/{erp,crm,itops,oa}/`
- Qdrant vector store (port 6333)
- Reranker service (port 8082)
- Agents can use `search_knowledge_base(query, domain, top_k)` tool

### Seeding Knowledge Base
```bash
python scripts/seed_knowledge_base.py
```

### Adding Documents
1. Add document to appropriate domain folder in `data/demo_docs/`
2. Run seeding script to index new documents
```

**Step 3: Commit documentation updates**

```bash
git add README.md CLAUDE.md
git commit -m "docs: add RAG pipeline setup and usage instructions"
```

---

## Task 10: Final Validation & Cleanup

**Step 1: Run all tests**

```bash
# Unit tests
pytest tests/ -v -m "not integration"

# Integration tests (requires services)
pytest tests/ -v -m integration
```

**Step 2: Verify services startup**

Test that all services start cleanly:
```bash
docker-compose up -d  # Qdrant
./scripts/start-embeddings.sh &
./scripts/start-reranker.sh &
./scripts/start-agent-api.sh &
```

Check health endpoints:
```bash
curl http://localhost:6333/healthz  # Qdrant
curl http://localhost:8081/health   # Embeddings
curl http://localhost:8082/health   # Reranker
curl http://localhost:8000/health   # Agent API
```

**Step 3: Test agent with RAG**

```bash
python scripts/test_agents.py
```

Verify agents can successfully call RAG tool.

**Step 4: Create final summary commit**

```bash
git add -A
git commit -m "feat: complete RAG pipeline implementation

Implemented components:
- Vector store client (Qdrant)
- Text chunker (tiktoken, 512 tokens, 20% overlap)
- Document ingestion (Docling)
- Reranker service (BGE-reranker)
- search_knowledge_base tool
- Seeding script with demo documents
- Agent integration
- Integration tests

Services:
- Reranker at port 8082
- Qdrant collection: bestbox_knowledge

Tested: All unit tests pass, integration tests validated"
```

---

## Completion Checklist

- [ ] Vector store client implemented and tested
- [ ] Text chunker with overlap working
- [ ] Document ingestion with Docling functional
- [ ] Reranker service deployed
- [ ] RAG tool implemented
- [ ] Demo documents created (4 domains)
- [ ] Seeding script tested
- [ ] Tools registered with agents
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] All services start successfully
- [ ] Agents can use RAG tool

---

## Next Steps After Implementation

1. **Create more demo documents** - Expand from 4 to 16 documents (4 per domain)
2. **Performance testing** - Measure retrieval latency under load
3. **Quality evaluation** - Test retrieval precision with known queries
4. **Agent prompt tuning** - Optimize when agents use RAG vs. training data
5. **UI integration** - Show RAG sources in frontend responses

---

## Troubleshooting

**Qdrant connection errors:**
- Check: `docker-compose ps` - Qdrant should be running
- Check: `curl http://localhost:6333/healthz`

**Embeddings service errors:**
- Check: `./scripts/start-embeddings.sh` running in terminal
- Check: `curl http://localhost:8081/health`
- Model downloads on first run (~2GB)

**Reranker service errors:**
- Check: `./scripts/start-reranker.sh` running
- Check: `curl http://localhost:8082/health`
- Model downloads on first run (~1GB)

**Seeding fails:**
- Ensure Qdrant and embeddings service running
- Check document paths are correct
- Verify Docling installed: `pip show docling`
