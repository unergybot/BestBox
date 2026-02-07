# URL Ingestion + LLM-Enhanced Knowledge Extraction

**Date**: 2026-02-06
**Status**: Design

## Summary

Add URL-based document import to the admin KB interface and enhance the indexing pipeline with LLM-powered knowledge extraction. Remote PDFs/DOCX/XLSX are downloaded, processed through the existing Docling pipeline, then enriched by the local Qwen3 LLM to produce structured Q&A pairs, summaries, and auto-tagged metadata.

## Goals

1. Import remote documents (PDF, DOCX, XLSX) via URL from the admin UI
2. Generate smarter searchable content (summaries, Q&A pairs, key concepts) per chunk using LLM prompts
3. Auto-tag metadata (defect_type, severity, root_cause, etc.) on indexed chunks for filtering and faceted browsing
4. Keep everything on-premise using the local Qwen3-30B-A3B on :8001

## Architecture

### Pipeline Flow

```
URL → Download → Docling Conversion → Standard Chunking (1000 chars)
  → LLM Enrichment (single call per chunk)
    → Enriched text (summary, Q&A, key concepts)
    → Metadata tags (defect_type, severity, root_cause, etc.)
  → Embedding (BGE-M3)
  → Qdrant Indexing (2 points per chunk: original + enriched)
  → Payload update (metadata tags via set_payload)
```

### What Gets Indexed Per Source Chunk

Each chunk produces **2 Qdrant points**:

1. **Original point** (`chunk_type: "original"`) — raw text from Docling, preserves exact wording for retrieval
2. **Enriched point** (`chunk_type: "enriched"`) — summary + Q&A pairs concatenated, matches semantic/question-style queries

Both points share the same `doc_id`, `source`, `chunk_index`, and `domain` so they group together in the admin UI.

Metadata tags are written to **both** points via `qdrant.set_payload()` after indexing.

## New Endpoint

### `POST /admin/documents/upload-url`

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | required | Direct link to PDF/DOCX/XLSX |
| `collection` | str | `mold_reference_kb` | Target Qdrant collection |
| `domain` | str | `mold` | Domain classification |
| `ocr_engine` | str | `easyocr` | OCR engine for Docling |
| `chunking` | str | `auto` | Chunking strategy |
| `enrich` | bool | `True` | Enable LLM extraction + enrichment |
| `force` | bool | `False` | Re-import even if URL already indexed |

**Response**: Job ID for async polling (same pattern as batch upload).

**Stages**: `downloading → converting → chunking → enriching → indexing → done`

## LLM Enrichment Module

### New File: `services/llm_enrichment.py`

**Single merged prompt** per chunk returns:

```json
{
  "summary": "2-3 sentence summary",
  "key_concepts": ["concept1", "concept2"],
  "qa_pairs": [
    {"question": "...", "answer": "..."}
  ],
  "domain_terms": ["term1", "term2"],
  "defect_type": "splay",
  "severity": "high",
  "root_cause_category": "material|process|mold|machine",
  "mold_components": ["gate", "hot runner"],
  "corrective_actions": ["reduce melt temp"],
  "applicable_materials": ["copolyester"]
}
```

**Key functions**:

- `enrich_chunk(text: str, domain: str) -> EnrichmentResult` — single LLM call via `POST http://localhost:8001/v1/chat/completions`
- `enrich_document(chunks: list, domain: str) -> list[EnrichmentResult]` — sequential processing with progress callback
- Domain-specific system prompts (mold domain gets defect-specific fields; other domains get generic extraction)

**Performance**: ~3-4 seconds per chunk at 85 tok/s. A 42-chunk PDF takes ~2.5 minutes.

## Error Handling

### URL Download
- Invalid URL or non-document Content-Type → 400 error before processing
- Timeout >60s or size >50MB → abort, clean up partial file
- SSL errors → fail with message suggesting manual download

### LLM Enrichment (best-effort, never blocks indexing)
- LLM unreachable → skip enrichment, index raw chunks only, return `"enrichment": "skipped"`
- Bad JSON from LLM → retry once with stricter prompt, then fall back to raw chunk
- Individual chunk failure → skip that chunk's enrichment, continue with rest
- **Principle: a document always gets indexed; enrichment is best-effort on top**

### Duplicate Detection
- Before downloading, check Qdrant for matching `source_url` in payload
- If found, return warning; require `force=true` to re-import

## Frontend Changes

### Documents Upload Page (`app/admin/documents/page.tsx`)

Add tabbed interface:
- **"Upload Files"** tab — existing drag-and-drop, unchanged
- **"Import from URL"** tab — URL text input + same options panel

URL tab includes:
- URL text input with validation
- Collection / Domain / OCR engine dropdowns (reuse existing)
- "LLM Enrichment" checkbox (default: on)
- Progress bar showing all stages including `"enriching chunk 12/42"`
- Completion summary: "Indexed 42 chunks + 42 enriched chunks. 6 defect types tagged."

### KB Browse Page (`app/admin/kb/page.tsx`)

Minor additions:
- Show `source_url` in document detail if present
- "AI enriched" badge on enriched chunks
- Metadata tags rendered as filterable chips (existing fields, now populated)

## Files Changed

| File | Change |
|------|--------|
| `services/llm_enrichment.py` | **NEW** — LLM enrichment module |
| `services/admin_endpoints.py` | Add `upload-url` endpoint; add `enrich` param to existing upload; call enrichment after chunking |
| `services/rag_pipeline/document_indexer.py` | Accept enriched chunks (index 2 points per chunk); support `set_payload()` for metadata |
| `frontend/.../app/admin/documents/page.tsx` | Add URL tab, enrichment toggle, progress stages |
| `frontend/.../app/admin/kb/page.tsx` | Show source_url, enrichment badges, metadata chips |

**No changes to**: Docling client, chunker, embeddings service, Qdrant config, agent tools, router, skills.

## Dependencies

- `httpx` (already in project) — URL download with streaming
- Local LLM on :8001 — Qwen3-30B-A3B via llama.cpp (already running)
- No new Python packages required
