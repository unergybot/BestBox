# Agentic RAG for Dummies — BestBox Integration Design & Implementation Plan

**Date:** 2026-02-04  
**Status:** Draft  
**Phase:** 3 - Demo Applications (RAG Track)

## Overview

This document reviews the **agentic-rag-for-dummies** repository and proposes a non‑RL integration path that fits BestBox’s current demo phase (sample data only). The focus is on **agentic workflow design**, **query clarification**, **parent–child chunking**, and **hybrid retrieval**, all of which are immediately useful without training data.

## Repository Review (agentic-rag-for-dummies)

**What it provides:**
- **LangGraph agent workflow** with query clarification, conversation summary, and human‑in‑the‑loop interrupt.
- **Parent–child chunking**: child chunks for precision, parent chunks for context.
- **Hybrid search** in Qdrant (dense + sparse/BM25).
- **Multi-agent map‑reduce** for multi‑question queries.
- **Gradio UI** for document ingestion and chat.

**Key modules:**
- `project/rag_agent/*`: graph, nodes, tools, prompts
- `project/document_chunker.py`: hierarchical chunking
- `project/db/vector_db_manager.py`: Qdrant hybrid retrieval
- `project/ui/gradio_app.py`: demo UI

## Value to BestBox (Demo Phase)

1. **Query clarification + HITL** improves demo robustness for ambiguous customer questions.
2. **Parent–child chunking** increases answer quality on doc-heavy demos without retraining.
3. **Hybrid dense + sparse retrieval** aligns with BestBox RAG architecture and can be implemented immediately.
4. **Map‑reduce agent fan‑out** handles multi‑part questions cleanly for demos.
5. **Ready-to-run UI** offers a fast demo surface if needed alongside the existing Copilot UI.

## Workability Assessment

**Feasible and useful for the current phase.**  
No RL or dataset is required. All features can run on sample documents with a single GPU/CPU setup.

**Gaps to adapt:**
- Replace generic prompts with BestBox domain prompts (ERP/CRM/IT Ops/OA).
- Swap local Qdrant path usage with BestBox’s service deployment if needed.
- Align chunking sizes with BestBox docs and demo data.

## Proposed Integration Design

### 1) Agentic Workflow Layer
Adopt LangGraph nodes for:
- Conversation summarization
- Query analysis + rewrite
- Optional human clarification interrupt
- Tool‑based retrieval + synthesis

### 2) Retrieval Stack
- Keep **parent–child chunking** with header‑aware parent segmentation.
- Use **Qdrant hybrid retrieval** (dense + BM25) for child chunks.
- Retrieve **parent chunks** for answer synthesis.

### 3) Multi‑Question Map‑Reduce
- Split multi‑question queries into parallel subgraphs.
- Aggregate answers into a final response.

## Implementation Plan (No RL)

### Phase 1 — Core Agentic RAG (2–3 days)
1. Port query clarification + summary nodes into BestBox’s agent graph.
2. Implement parent–child chunker and parent store persistence.
3. Add hybrid search for child chunks in Qdrant.

### Phase 2 — Demo Data & UI (2–3 days)
1. Convert sample PDFs → Markdown.
2. Ingest to parent/child storage and Qdrant.
3. Optional: wire a minimal UI tab for document upload + chat.

### Phase 3 — Domain Prompting & Tests (1–2 days)
1. Update prompts for ERP/CRM/IT Ops/OA.
2. Add test queries per domain and validate top‑k retrieval.

## BestBox Implementation Details

### New/Updated Components

**1) Parent–Child Chunker**
- File: `services/rag_pipeline/chunker.py`
- Add header‑aware parent splits + child splits

**2) Parent Store**
- File: `services/rag_pipeline/parent_store.py`
- Persist parent chunks with metadata

**3) Hybrid Search**
- File: `services/rag_pipeline/vector_store.py`
- Add dense + BM25 retrieval for child chunks

**4) Agentic Nodes (LangGraph)**
- File: `agents/graph.py` or `agents/rag_agent.py`
- Add: summarize → rewrite → HITL → retrieve → synthesize

**5) Tools**
- File: `tools/rag_tools.py`
- Add: `search_child_chunks(query, k)` and `retrieve_parent_chunks(ids)`

## Configuration

Add to BestBox config:
- `RAG_PARENT_MIN_SIZE`
- `RAG_PARENT_MAX_SIZE`
- `RAG_CHILD_CHUNK_SIZE`
- `RAG_CHILD_OVERLAP`
- `RAG_HYBRID_DENSE_WEIGHT`
- `RAG_HYBRID_SPARSE_WEIGHT`

## Demo Success Criteria

- Ambiguous queries trigger clarification or rewrite.
- Multi‑question queries return distinct answers.
- Top‑5 retrieval includes relevant parent context in each domain.
- End‑to‑end response latency < 2s on demo data.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Over‑chunking docs | Medium | Tune parent/child sizes per domain |
| Query rewrite regressions | Medium | Add allowlist of safe rewrite patterns |
| Hybrid weights off | Low | Start with 0.7 dense / 0.3 sparse |

## Next Actions

1. Approve parent–child chunking + hybrid retrieval for demo.
2. Create 5–10 sample docs per domain and ingest.
3. Wire query clarification + map‑reduce into BestBox agent graph.

---

This approach provides immediate demo value without RL, while keeping a clear upgrade path for later training.
