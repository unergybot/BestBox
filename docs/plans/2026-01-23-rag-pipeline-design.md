# RAG Pipeline Design

**Date:** 2026-01-23
**Status:** Approved
**Phase:** 3 - Demo Applications (RAG Track)

## Overview

This design implements a production-ready RAG (Retrieval-Augmented Generation) pipeline for BestBox that enables agents to search a knowledge base of domain-specific documents using hybrid search and reranking for maximum precision.

## Goals

1. **Document Ingestion** - Parse and chunk demo documents using Docling
2. **Vector Storage** - Store embeddings in Qdrant with hybrid indexing
3. **Semantic Search** - Enable agents to search knowledge base via tool
4. **High Precision** - Use dense + BM25 + reranking for best results

## Current State

**Existing Infrastructure:**
- Qdrant running via docker-compose (port 6333)
- BGE-M3 embeddings service at port 8081
- Docling available at /home/unergy/MyCode/docling
- System design mentions RAG but not implemented

**Gap:**
- No document ingestion pipeline
- No chunking strategy
- No retrieval tools for agents
- No reranker service

## Design

### 1. Overall Architecture & Data Flow

**RAG Pipeline Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                    INGESTION PHASE (Offline)                │
├─────────────────────────────────────────────────────────────┤
│ Demo Documents (PDF/DOCX/MD)                                │
│         ↓                                                    │
│ Docling Document Loader (/home/unergy/MyCode/docling)       │
│   - Handles complex layouts, tables, images                 │
│   - Preserves document structure                            │
│   - Extracts metadata (title, author, etc.)                 │
│         ↓                                                    │
│ Text Chunker (512 tokens, 20% overlap)                      │
│   - Respects document structure from Docling                │
│   - Preserves section headers in chunks                     │
│         ↓                                                    │
│ BGE-M3 Embeddings (via /embed at :8081)                     │
│         ↓                                                    │
│ Qdrant Storage (collection: "bestbox_knowledge")            │
│   - Dense vectors (1024-dim)                                │
│   - BM25 index (full-text)                                  │
│   - Metadata (doc_id, chunk_id, source, domain, title)      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   RETRIEVAL PHASE (Online)                  │
├─────────────────────────────────────────────────────────────┤
│ Agent calls search_knowledge_base(query, domain, top_k=5)   │
│         ↓                                                    │
│ Embed query with BGE-M3                                      │
│         ↓                                                    │
│ Qdrant Hybrid Search:                                       │
│   - Dense: cosine similarity (weight 0.7)                   │
│   - BM25: keyword match (weight 0.3)                        │
│   - Filter by domain if specified                           │
│   - Returns top 20 candidates                               │
│         ↓                                                    │
│ Reranker (BGE-reranker) - score top 20 → top 5             │
│         ↓                                                    │
│ Return formatted context to agent                            │
└─────────────────────────────────────────────────────────────┘
```

**Key Design Decisions:**
- Single Qdrant collection with domain filtering (not separate collections per agent)
- Hybrid search built into Qdrant query (no separate BM25 service needed)
- Reranker as separate FastAPI service for precision boost
- Metadata includes domain tags so agents can filter (e.g., ERP agent filters domain="erp")
- Docling for robust PDF/DOCX parsing instead of basic PyPDF2

**Docling Integration Benefits:**
- Better PDF parsing (tables, multi-column layouts)
- DOCX support out of the box
- Structured output makes chunking smarter
- Metadata extraction for better filtering

### 2. Component Specifications

**File Structure:**
```
BestBox/
├── services/
│   ├── rag_pipeline/
│   │   ├── __init__.py
│   │   ├── ingest.py          # Document ingestion logic
│   │   ├── chunker.py          # Text chunking with overlap
│   │   ├── vector_store.py     # Qdrant client wrapper
│   │   └── reranker.py         # BGE-reranker service
├── tools/
│   └── rag_tools.py            # search_knowledge_base tool for agents
├── scripts/
│   ├── seed_knowledge_base.py  # One-time script to ingest demo docs
│   └── start-reranker.sh       # Start reranker service
└── data/
    └── demo_docs/              # Sample documents
        ├── erp/
        ├── crm/
        ├── itops/
        └── oa/
```

**Component Details:**

**1. Document Ingestion (`services/rag_pipeline/ingest.py`):**
- Uses docling to parse PDFs/DOCX/MD
- Extracts text + metadata (title, source, domain)
- Handles errors gracefully (skip malformed docs)
- Returns structured Document objects

**2. Text Chunker (`services/rag_pipeline/chunker.py`):**
- 512 tokens per chunk (using tiktoken for GPT-like tokenization)
- 20% overlap (~100 tokens)
- Preserves section headers in each chunk
- Tracks chunk position for reassembly

**3. Vector Store (`services/rag_pipeline/vector_store.py`):**
- Qdrant client with collection management
- Creates collection with dense + sparse (BM25) indexing
- Batch upsert for efficiency (100 chunks at a time)
- Metadata schema: {doc_id, chunk_id, source, domain, title, text}

**4. Reranker (`services/rag_pipeline/reranker.py`):**
- Loads BGE-reranker-base locally (lighter than -large)
- FastAPI service similar to embeddings service
- Endpoint: POST /rerank with {query, passages}
- Returns scores for re-ranking

### 3. Retrieval Flow & Tool Implementation

**RAG Tool for Agents (`tools/rag_tools.py`):**

```python
@tool
def search_knowledge_base(
    query: str,
    domain: str = None,
    top_k: int = 5
) -> str:
    """
    Search the knowledge base for relevant information.

    Args:
        query: The search query (natural language)
        domain: Filter by domain (erp, crm, itops, oa) or None for all
        top_k: Number of results to return (default 5)

    Returns:
        Formatted context string with sources
    """
```

**Retrieval Pipeline Steps:**

1. **Query Embedding** (10-20ms)
   - Call embeddings service: POST /embed with query text
   - Get 1024-dim vector

2. **Hybrid Search** (20-50ms)
   - Qdrant query with:
     - Vector search (cosine similarity)
     - BM25 full-text search
     - Fusion: RRF (Reciprocal Rank Fusion)
   - Apply domain filter if specified
   - Return top 20 candidates

3. **Reranking** (50-100ms)
   - Send query + 20 passages to reranker
   - Get relevance scores (0-1)
   - Sort by score, take top_k

4. **Format Response**
   - Combine chunks into context string
   - Add source citations
   - Return to agent

**Example Tool Output:**
```
Based on the knowledge base:

[Source: ERP_Procedures.pdf, Section 2.3]
Purchase orders must be approved by department managers before submission...

[Source: Vendor_Management_Guide.pdf, Page 5]
Vendor price increases require quarterly review and re-negotiation...

---
Retrieved 5 relevant passages.
```

### 4. Demo Documents & Seeding Strategy

**Demo Document Structure:**

```
data/demo_docs/
├── erp/
│   ├── purchase_order_procedures.pdf
│   ├── inventory_management_guide.pdf
│   ├── vendor_approval_process.md
│   └── financial_reporting_standards.pdf
├── crm/
│   ├── lead_qualification_framework.pdf
│   ├── sales_playbook.md
│   ├── customer_lifecycle_guide.pdf
│   └── quote_generation_templates.md
├── itops/
│   ├── system_troubleshooting_runbook.pdf
│   ├── alert_response_procedures.md
│   ├── database_performance_guide.pdf
│   └── network_diagnostics_handbook.pdf
└── oa/
    ├── email_templates_library.md
    ├── meeting_scheduling_policy.pdf
    ├── document_approval_workflow.pdf
    └── leave_request_procedures.md
```

**Seeding Script (`scripts/seed_knowledge_base.py`):**

**Process:**
1. Check if Qdrant collection exists, create if not
2. Walk through `data/demo_docs/` directories
3. For each document:
   - Detect domain from folder name (erp/crm/itops/oa)
   - Use Docling to parse document
   - Chunk text into 512-token chunks with 20% overlap
   - Generate embeddings via embeddings service
   - Upsert to Qdrant with metadata
4. Create BM25 index for full-text search
5. Print summary: documents processed, chunks created, total vectors

**One-time execution:**
```bash
python scripts/seed_knowledge_base.py
# Output:
# Processing data/demo_docs/erp/purchase_order_procedures.pdf...
# Created 23 chunks from purchase_order_procedures.pdf
# Processing data/demo_docs/crm/lead_qualification_framework.pdf...
# Created 18 chunks from lead_qualification_framework.pdf
# ...
# Summary: 16 documents, 312 chunks, 312 vectors in Qdrant
```

**Metadata Schema per Vector:**
```json
{
  "doc_id": "erp_purchase_order_procedures",
  "chunk_id": 5,
  "source": "purchase_order_procedures.pdf",
  "domain": "erp",
  "title": "Purchase Order Procedures",
  "chunk_text": "Full text of this chunk...",
  "section": "Section 2.3: Approval Workflow"
}
```

### 5. Error Handling & Performance Targets

**Error Handling Strategy:**

**1. Ingestion Errors:**
- **Malformed documents**: Skip and log, continue with other docs
- **Docling parsing failure**: Fallback to basic text extraction, warn user
- **Embedding service down**: Retry 3 times with exponential backoff, fail gracefully
- **Qdrant connection error**: Halt ingestion, return clear error message

**2. Retrieval Errors:**
- **Empty results**: Return "No relevant information found" instead of erroring
- **Reranker timeout**: Fall back to hybrid search results without reranking
- **Embeddings service unavailable**: Cache recent embeddings, return cached or error
- **Invalid domain filter**: Warn and search all domains

**3. Graceful Degradation:**
```
Full pipeline: Hybrid + Reranking (best precision)
    ↓ (if reranker fails)
Hybrid only: Dense + BM25 (good precision)
    ↓ (if BM25 fails)
Dense only: Vector search (acceptable)
    ↓ (if all fails)
Return error to agent
```

**Performance Targets:**

| Operation | Target | Acceptable | Notes |
|-----------|--------|------------|-------|
| Document ingestion (per doc) | <2s | <5s | Offline, not critical |
| Chunk embedding (batch 100) | <500ms | <1s | Batched for efficiency |
| Hybrid search | <50ms | <100ms | Qdrant is fast |
| Reranking (20 passages) | <100ms | <200ms | CPU-bound |
| **Total retrieval latency** | **<200ms** | **<400ms** | P95 target |

**Monitoring:**
- Log all retrieval operations with latency
- Track cache hit rates for embeddings
- Alert if retrieval latency > 500ms
- Count empty result queries for improvement

### 6. Testing Strategy & Validation

**Testing Levels:**

**1. Unit Tests:**
```python
# Test chunking logic
def test_chunker_respects_token_limit():
    # Verify chunks are ~512 tokens
    # Verify 20% overlap exists

# Test Qdrant operations
def test_vector_store_upsert():
    # Verify documents are stored
    # Verify metadata is correct

# Test retrieval
def test_hybrid_search():
    # Verify both dense and BM25 work
    # Verify domain filtering works
```

**2. Integration Tests:**
```python
# End-to-end ingestion
def test_ingest_pdf_to_qdrant():
    # Parse sample PDF with Docling
    # Chunk and embed
    # Store in test collection
    # Verify retrievable

# End-to-end retrieval
def test_search_knowledge_base_tool():
    # Call tool with test query
    # Verify results returned
    # Verify sources cited
```

**3. Quality Tests:**
```python
# Retrieval accuracy
def test_retrieval_precision():
    # Test queries with known answers
    # Verify correct documents in top 5

# Examples:
test_queries = [
    ("How do I approve a purchase order?", "erp", "purchase_order_procedures.pdf"),
    ("What is the lead scoring criteria?", "crm", "lead_qualification_framework.pdf"),
    ("Database is slow, how to diagnose?", "itops", "database_performance_guide.pdf")
]
```

**4. Manual Validation:**
- Ingest all 16 demo documents
- Query from each domain
- Verify relevant results returned
- Check citation accuracy
- Test agent integration (ERP agent uses RAG for complex queries)

**Acceptance Criteria:**
- ✅ All 16 demo documents ingested successfully
- ✅ Retrieval latency < 400ms (P95)
- ✅ Test queries return correct domain docs in top 3
- ✅ Agents can call search_knowledge_base tool
- ✅ No errors on malformed documents (skip gracefully)

### 7. Implementation Plan & Dependencies

**Implementation Phases:**

**Phase 1: Core Infrastructure (Week 1, Days 1-2)**
- Install docling in venv: `pip install -e /home/unergy/MyCode/docling`
- Create `services/rag_pipeline/` module structure
- Implement `vector_store.py` with Qdrant client
- Create Qdrant collection with hybrid indexing
- Test basic vector operations

**Phase 2: Ingestion Pipeline (Week 1, Days 3-4)**
- Implement `ingest.py` with Docling integration
- Implement `chunker.py` with tiktoken tokenization
- Build `seed_knowledge_base.py` script
- Create demo documents (16 files across 4 domains)
- Test end-to-end ingestion

**Phase 3: Retrieval & Reranking (Week 1, Day 5)**
- Implement hybrid search in `vector_store.py`
- Build `reranker.py` service with BGE-reranker
- Create `start-reranker.sh` startup script
- Test retrieval with sample queries

**Phase 4: Agent Integration (Week 2, Days 1-2)**
- Implement `search_knowledge_base` tool in `tools/rag_tools.py`
- Register tool with agents in `agents/graph.py`
- Update agent prompts to use RAG when needed
- Test agents calling RAG tool

**Phase 5: Testing & Validation (Week 2, Day 3)**
- Write unit and integration tests
- Run quality tests with test queries
- Manual validation across all domains
- Performance benchmarking

**Dependencies to Install:**

```bash
# In BestBox venv
pip install -e /home/unergy/MyCode/docling  # Document parsing
pip install qdrant-client                    # Vector store client
pip install tiktoken                         # Tokenization for chunking
pip install sentence-transformers           # For reranker (already have for embeddings)
```

**Service Ports:**

| Service | Port | Status |
|---------|------|--------|
| Embeddings (BGE-M3) | 8081 | ✅ Existing |
| Reranker (BGE-reranker) | 8082 | 🆕 New |
| Qdrant | 6333 | ✅ Existing (Docker) |

**Estimated Effort:**
- Development: 2-3 days
- Testing: 1 day
- Demo document creation: 0.5 day (can use generated/sample docs)
- **Total: 3.5-4.5 days**

## Integration with Existing System

**Agent Updates Required:**

1. Register `search_knowledge_base` tool in `agents/graph.py`
2. Update agent prompts to mention knowledge base availability
3. Example agent prompt addition:
   ```
   You have access to a knowledge base via search_knowledge_base(query, domain).
   Use it when you need specific procedures, policies, or technical information
   beyond your training data.
   ```

**No Changes Required:**
- Embeddings service (already running)
- Qdrant (already running)
- Agent orchestration (LangGraph)
- Frontend (agents automatically use new tool)

## Future Enhancements

**Post-MVP Improvements:**
1. **Document Upload UI** - Allow users to upload their own documents
2. **Incremental Updates** - Add/remove documents without full re-indexing
3. **Query Expansion** - Use LLM to expand queries before retrieval
4. **Hybrid Reranker** - Combine BGE-reranker with LLM-based reranking
5. **Multi-hop Retrieval** - Iterative retrieval for complex queries
6. **Answer Extraction** - Extract specific answers from chunks (not just context)
7. **Metadata Filtering** - Filter by date, author, document type
8. **Analytics Dashboard** - Track popular queries, retrieval quality metrics

## Success Metrics

**Technical Metrics:**
- Retrieval latency P95 < 400ms
- Precision@5 > 80% on test queries
- Zero ingestion errors on demo documents
- 100% agent tool integration success

**Quality Metrics:**
- Agents use RAG for knowledge-intensive queries
- User satisfaction with retrieved information
- Reduction in "I don't know" responses from agents

## References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [BGE-M3 Model Card](https://huggingface.co/BAAI/bge-m3)
- [Docling GitHub](https://github.com/DS4SD/docling)
- [LangChain RAG Guide](https://python.langchain.com/docs/use_cases/question_answering/)
