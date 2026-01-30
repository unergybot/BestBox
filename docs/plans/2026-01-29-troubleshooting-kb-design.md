# Troubleshooting Knowledge Base Design

**Date**: 2026-01-29
**Version**: 1.0
**Status**: Design Complete - Ready for Implementation

---

## Executive Summary

This document outlines the complete design for integrating a multimodal troubleshooting knowledge base into BestBox. The system will ingest 1000+ Excel files containing equipment troubleshooting cases with embedded images, process them with Vision-Language models, and provide semantic search capabilities through the existing agent system.

### Key Features

- **Multimodal Understanding**: Qwen2-VL-7B processes equipment photos to extract defect descriptions
- **Dual-Level Search**: Adaptive routing between case-level and issue-level search
- **On-Premise Deployment**: All processing runs locally on AMD hardware (ROCm)
- **Existing Infrastructure Reuse**: Leverages BGE-M3 embeddings, Qdrant, and reranker

### Resource Footprint

- **GPU Memory**: 58GB / 98GB (59% utilization)
- **Disk Space**: ~98GB total
- **Processing Time**: ~40-50 hours for 1000 files (parallel processing)
- **Search Latency**: <500ms target

---

## 1. Data Structure Analysis

### Sample File: 1947688(ED736A0501)-case.xlsx

**Structure**:
- **5 sheets**: 修正资料 (correction data), 统计表, 不良项目, 作成方法, 高精度尺寸
- **Header (rows 1-19)**: Case metadata (part number, material, dates, etc.)
- **Data table (row 20+)**: 20-26 troubleshooting entries per file
- **Images**: 38 embedded images (1 logo + 37 equipment photos)

**Key Columns**:
- NO: Issue number
- 型试: Trial version (T0, T1, T2)
- 项目: Category code
- 問題点: Problem description (产品披锋, 火花纹, etc.)
- 原因，对策: Cause and countermeasure
- 修正結果T1/T2: Correction results (OK/NG)
- Images: Equipment photos showing defects/solutions

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                         │
├──────────────────────────────────────────────────────────────┤
│  Excel File → ExcelExtractor → JSON + Images                 │
│           ↓                                                   │
│  Images → Qwen2-VL-7B → Defect Descriptions                  │
│           ↓                                                   │
│  Text + VL → BGE-M3 → Embeddings (1024-dim)                  │
│           ↓                                                   │
│  Qdrant Indexer → Dual Collections                           │
│    - troubleshooting_cases (case-level)                      │
│    - troubleshooting_issues (issue-level)                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                     SEARCH PIPELINE                           │
├──────────────────────────────────────────────────────────────┤
│  User Query → LLM Classifier → Search Mode                   │
│    (CASE_LEVEL | ISSUE_LEVEL | HYBRID)                       │
│           ↓                                                   │
│  Vector Search (BGE-M3) → Candidates (3x)                    │
│           ↓                                                   │
│  BGE-Reranker-v2-m3 → Top Results                            │
│           ↓                                                   │
│  Metadata Boosting → Final Ranking                           │
│           ↓                                                   │
│  Agent Tools → Frontend Display                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Component Design

### 3.1 Vision-Language Service

**Model**: Qwen3-VL-8B-Instruct (Latest generation, Oct 2025)
**Port**: 8083
**Memory**: ~16GB GPU

**Capabilities**:
- Equipment defect recognition (flash, whitening, scratches)
- Part identification (mold surface, product edge)
- Visual annotation detection (red circles, arrows)
- OCR for Chinese text in images

**API**:
```
POST /analyze-image
- Input: Equipment photo (JPEG)
- Output: {defect_type, equipment_part, visual_annotations, text_in_image}
```

### 3.2 Excel Extraction Pipeline

**Component**: `ExcelTroubleshootingExtractor`

**Process**:
1. Extract metadata (rows 1-19): part number, material, dates
2. Parse data table (row 20+): problem, solution, results
3. Extract embedded images to files
4. Map images to related rows (spatial proximity)

**Output**: JSON structure with case metadata + issue array + image references

### 3.3 Dual-Level Indexing

**Case-Level Collection** (`troubleshooting_cases`):
- One vector per Excel file
- Embedding from aggregated issue summaries
- Payload: case_id, part_number, material, issue_ids, file_path

**Issue-Level Collection** (`troubleshooting_issues`):
- One vector per table row (~20 per file)
- Embedding from: problem + solution + VL image descriptions
- Payload: issue details, images, trial_version, results

**Embedding Strategy**:
```python
text = f"问题: {problem} 解决方案: {solution} "
for img in images:
    text += f"图像显示: {img.vl_description} "
text += f"试模阶段: {trial_version} 结果: {result}"

embedding = BGE_M3.embed(text)  # 1024-dim
```

### 3.4 Adaptive Search

**Query Classification** (via Qwen3-30B LLM):
- CASE_LEVEL: "零件1947688的所有问题", "HIPS材料案例"
- ISSUE_LEVEL: "产品披锋的解决方法", "模具表面污染"
- HYBRID: "披锋问题的案例有哪些"

**Multi-Stage Retrieval**:
1. Vector search (BGE-M3) → 3x candidates
2. Reranking (BGE-reranker-v2-m3) → top_k
3. Metadata boosting:
   - Successful solutions (OK result) → +15%
   - Part number match → +30%

---

## 4. Implementation Plan

### Week 1: VL Model & Excel Extraction
- Deploy Qwen2-VL-7B on ROCm
- Implement ExcelTroubleshootingExtractor
- Test with sample file

### Week 2: Embedding & Indexing
- Implement TroubleshootingEmbedder
- Create Qdrant dual collections
- Batch ingestion script with checkpoints

### Week 3: Search & Agent Integration
- Implement AdaptiveSearchRouter
- Create agent tools (search_troubleshooting_kb, get_case_details)
- Integrate with IT Ops agent

### Week 4: Frontend & Deployment
- TroubleshootingViewer React component
- Image serving API endpoint
- Process all 1000 files
- End-to-end testing

---

## 5. File Structure

```
BestBox/
├── data/
│   └── troubleshooting/
│       ├── raw/                    # Original 1000 Excel files
│       ├── processed/              # JSON + extracted images
│       │   ├── images/             # All extracted images
│       │   ├── TS-*.json           # Enriched case data
│       │   └── ingestion_checkpoint.json
│       └── archive/
│
├── services/
│   ├── troubleshooting/
│   │   ├── excel_extractor.py      # Excel → JSON + images
│   │   ├── vl_processor.py         # VL image enrichment
│   │   ├── embedder.py             # Text + VL → embeddings
│   │   ├── indexer.py              # Qdrant dual-level indexing
│   │   └── searcher.py             # Adaptive search router
│   │
│   └── vision/
│       ├── qwen2_vl_server.py      # VL model API (port 8083)
│       └── image_preprocessor.py
│
├── scripts/
│   ├── start-vl.sh
│   ├── seed_troubleshooting_kb.py  # Batch ingestion
│   └── start-all-troubleshooting.sh
│
├── tools/
│   └── troubleshooting_tools.py    # Agent tools
│
└── frontend/copilot-demo/
    └── components/
        └── TroubleshootingViewer.tsx
```

---

## 6. Service Configuration

### Updated Service Ports

| Service              | Port | Memory | Purpose                    |
|----------------------|------|--------|----------------------------|
| LLM (Qwen3-30B)      | 8080 | ~35GB  | Main reasoning             |
| Embeddings (BGE-M3)  | 8081 | ~2GB   | Text embeddings            |
| Reranker (BGE-v2-m3) | 8082 | ~2GB   | Result reranking           |
| **VL (Qwen3-VL-8B)** | **8083** | **~16GB** | **Image understanding** |
| Agent API            | 8000 | ~1GB   | FastAPI backend            |
| Frontend             | 3000 | -      | Next.js UI                 |

**Total GPU Memory**: 60GB / 98GB (62% utilization) ✅

---

## 7. Agent Tools

### Tool 1: search_troubleshooting_kb

```python
@tool
def search_troubleshooting_kb(
    query: str,
    top_k: int = 5,
    part_number: Optional[str] = None,
    trial_version: Optional[str] = None,
    only_successful: bool = False
) -> str:
    """Search troubleshooting KB for equipment issues and solutions"""
```

**Returns**: JSON with results including:
- Problem description
- Solution steps
- Trial version & success status
- Image URLs with VL descriptions
- Defect types

### Tool 2: get_troubleshooting_case_details

```python
@tool
def get_troubleshooting_case_details(case_id: str) -> str:
    """Get complete case details including all issues and images"""
```

---

## 8. Performance Targets

### Processing Performance
- Excel extraction: ~30 seconds per file
- VL image analysis: ~30-45 seconds per image
- Embedding generation: <5 seconds per issue
- Indexing: <10 seconds per case

### Search Performance
- Query classification: <200ms
- Vector search: <100ms
- Reranking: <200ms
- **Total search latency: <500ms (P95)**

### Throughput
- Parallel VL processing: 4 concurrent workers
- Batch ingestion: ~40-50 hours for 1000 files
- Search: 20+ queries/second

---

## 9. Testing Strategy

### Unit Tests
- Excel extraction (metadata, issues, images)
- VL description quality
- Embedding generation
- Qdrant indexing

### Integration Tests
- End-to-end pipeline (Excel → Search)
- Service health checks
- Agent tool functionality

### Performance Tests
- Search latency benchmarks
- Concurrent user simulation
- Memory usage monitoring

### Quality Tests
- Search relevance evaluation
- VL description accuracy
- Result ranking quality

---

## 10. Deployment Checklist

### Prerequisites
- [ ] Qwen2-VL-7B model downloaded (~14GB)
- [ ] 1000 Excel files in `data/troubleshooting/raw/`
- [ ] Sufficient disk space (~98GB)
- [ ] All existing services running (LLM, embeddings, Qdrant)

### Deployment Steps
1. [ ] Start VL service: `./scripts/start-vl.sh`
2. [ ] Test VL health: `curl http://localhost:8083/health`
3. [ ] Create Qdrant collections (auto-created on first run)
4. [ ] Run sample file ingestion for testing
5. [ ] Run full batch ingestion (overnight/weekend)
6. [ ] Validate search quality with test queries
7. [ ] Deploy frontend components
8. [ ] Update IT Ops agent with troubleshooting tools

### Monitoring
- [ ] GPU memory usage (should stay under 70GB)
- [ ] Search latency (target <500ms P95)
- [ ] VL service health
- [ ] Qdrant collection sizes
- [ ] Failed file count during ingestion

---

## 11. Future Enhancements

### Phase 2 Improvements
- **Multi-language support**: Extend beyond Chinese
- **Active learning**: User feedback to improve VL descriptions
- **Similar case detection**: Find structurally similar issues
- **Temporal analysis**: Track problem evolution across trials
- **Cross-case insights**: Aggregate solutions across all cases

### Advanced Features
- **Visual similarity search**: Find images similar to query image
- **Automated report generation**: Create troubleshooting reports
- **Predictive maintenance**: Identify recurring patterns
- **Integration with ERPNext**: Link to production records

---

## 12. Risk Mitigation

### Technical Risks

**Risk**: VL model hallucinations in image descriptions
**Mitigation**:
- Use temperature=0.3 for consistent outputs
- Human review of random samples
- Fallback to basic OCR when VL confidence is low

**Risk**: GPU memory overflow with concurrent processing
**Mitigation**:
- Limit VL workers to 4 concurrent
- Monitor memory usage during batch ingestion
- Implement graceful degradation

**Risk**: Search quality issues with Chinese text
**Mitigation**:
- BGE-M3 is specifically trained for Chinese
- Use reranker for final quality boost
- A/B test different embedding strategies

### Operational Risks

**Risk**: Long ingestion time (40-50 hours)
**Mitigation**:
- Checkpoint system for resumability
- Run during off-hours
- Parallel processing where possible

**Risk**: Excel format variations across 1000 files
**Mitigation**:
- Robust error handling in extractor
- Log failed files for manual review
- Support multiple header row positions

---

## Conclusion

This design provides a complete, production-ready solution for multimodal troubleshooting knowledge base integration into BestBox. The system leverages existing infrastructure while adding Vision-Language capabilities for equipment image understanding. All processing remains on-premise, maintaining data sovereignty while delivering semantic search over 1000+ real-world troubleshooting cases.

**Next Steps**: Begin Week 1 implementation - Deploy Qwen2-VL and test with sample file.
