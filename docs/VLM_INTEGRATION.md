# VLM Service Integration

**Version:** 1.0.0
**Date:** 2025-02-01
**Status:** Production Ready

This document describes the integration of the external Qwen3-VL 8B Vision-Language Model service into the BestBox mold troubleshooting system.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Components](#components)
5. [API Endpoints](#api-endpoints)
6. [Tools](#tools)
7. [Usage Examples](#usage-examples)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The VLM integration enhances the mold troubleshooting system with rich visual analysis capabilities:

- **Real-time Image Analysis**: Analyze defect images during chat conversations
- **Document Processing**: Extract insights from PDFs and Excel files
- **Defect Comparison**: Compare new defects with historical cases
- **Knowledge Base Enrichment**: Enrich indexed cases with VLM-extracted metadata

### Key Features

| Feature | Description |
|---------|-------------|
| Async Processing | Non-blocking job submission with webhook/polling |
| Multipart Upload | Direct file upload to VLM service |
| Redis Job Store | Webhook result caching for fast retrieval |
| VLM-aware Search | Boosted ranking based on VLM metadata |
| Mold-specific Analysis | Custom prompt template for defect detection |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     BestBox Agent API (:8000)                   │
├─────────────────────────────────────────────────────────────────┤
│  /api/v1/webhooks/vlm-results  ←── Webhook callbacks            │
│  /api/v1/upload                ←── File upload                  │
│  /api/v1/vlm/jobs/{job_id}     ←── Job status                   │
│  /health/vlm                   ←── VLM health check             │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   VLM Service Client                            │
│  services/vlm/client.py                                         │
├─────────────────────────────────────────────────────────────────┤
│  • Multipart file upload                                        │
│  • Async job submission                                         │
│  • Webhook + polling callbacks                                  │
│  • Retry with exponential backoff                               │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              External VLM Service (192.168.1.196:8081)          │
│                        Qwen3-VL-8B                              │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/v1/jobs/upload     ←── Submit analysis job           │
│  GET  /api/v1/jobs/{job_id}   ←── Check job status              │
│  GET  /api/v1/health          ←── Health check                  │
└─────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Redis Job Store                             │
│  services/vlm/job_store.py                                      │
├─────────────────────────────────────────────────────────────────┤
│  • Store webhook-delivered results                              │
│  • Fast result retrieval                                        │
│  • 1-hour TTL for results                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Image/Document Upload** → Agent API receives file
2. **Job Submission** → VLM client uploads to VLM service
3. **Async Processing** → VLM service processes with Qwen3-VL-8B
4. **Result Delivery** → Webhook callback or polling
5. **Result Storage** → Redis job store caches result
6. **Response** → Analysis returned to user/agent

---

## Configuration

### Environment Variables

```bash
# Enable VLM features
VLM_ENABLED=true

# VLM Service URL
VLM_SERVICE_URL=http://192.168.1.196:8081

# Webhook secret for signature verification (optional)
VLM_WEBHOOK_SECRET=your-shared-secret

# Redis URL for job store
VLM_REDIS_URL=redis://localhost:6379/1

# Default timeout for job completion (seconds)
VLM_DEFAULT_TIMEOUT=600
```

### Enabling VLM in Mold Agent

When `VLM_ENABLED=true`, the mold agent automatically includes VLM tools:

```python
# agents/mold_agent.py
MOLD_TOOLS = [
    search_troubleshooting_kb,
    get_troubleshooting_case_details,
    # VLM tools (when enabled)
    analyze_image_realtime,
    analyze_document_realtime,
    compare_images
]
```

---

## Components

### 1. VLM Service Client

**File:** `services/vlm/client.py`

```python
from services.vlm import VLMServiceClient

async with VLMServiceClient() as client:
    # Check health
    health = await client.check_health()

    # Analyze file
    result = await client.analyze_file(
        "path/to/image.jpg",
        prompt_template="mold_defect_analysis",
        timeout=120
    )
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `check_health()` | Check VLM service availability |
| `submit_file(path)` | Submit file for async processing |
| `wait_for_result(job_id)` | Wait for job completion |
| `analyze_file(path)` | Submit and wait (convenience) |
| `compare_images(ref, comparisons)` | Compare multiple images |

### 2. VLM Models

**File:** `services/vlm/models.py`

```python
class VLMResult(BaseModel):
    job_id: Optional[str]
    document_summary: str
    key_insights: List[str]
    analysis: VLMAnalysis
    extracted_images: List[ExtractedImage]
    tags: List[str]
    defect_type: Optional[str]
    severity: Optional[str]
    suggested_actions: List[str]
    metadata: VLMMetadata
```

### 3. Job Store

**File:** `services/vlm/job_store.py`

```python
from services.vlm import VLMJobStore

store = VLMJobStore()

# Store result (from webhook)
await store.store_result(job_id, result)

# Retrieve result
result = await store.get_result(job_id)

# Wait for result with timeout
result = await store.wait_for_result(job_id, timeout=60)
```

### 4. VL Processor

**File:** `services/troubleshooting/vl_processor.py`

Updated to use VLM service for batch processing:

```python
from services.troubleshooting.vl_processor import VLProcessor

processor = VLProcessor(enabled=True, use_vlm_service=True)

# Enrich case with VLM analysis
enriched_case = await processor.enrich_case_async(case_data)
```

---

## API Endpoints

### POST /api/v1/webhooks/vlm-results

Receives VLM job completion callbacks.

**Headers:**
- `X-VLM-Signature`: HMAC-SHA256 signature (optional)
- `X-VLM-Job-ID`: Job identifier

**Request Body:**
```json
{
  "event": "job.completed",
  "job_id": "vlm-20250201-abc123",
  "status": "completed",
  "result": { ... }
}
```

**Response:**
```json
{
  "status": "ok",
  "job_id": "vlm-20250201-abc123"
}
```

### POST /api/v1/upload

Upload file for VLM analysis.

**Request:** Multipart form data with `file` field

**Response:**
```json
{
  "status": "ok",
  "filename": "defect.jpg",
  "file_path": "/path/to/saved/file",
  "size_bytes": 123456
}
```

### GET /api/v1/vlm/jobs/{job_id}

Get VLM job status and result.

**Response (completed):**
```json
{
  "job_id": "vlm-20250201-abc123",
  "status": "completed",
  "result": {
    "document_summary": "...",
    "key_insights": [...],
    "defect_type": "披锋",
    "severity": "high"
  }
}
```

### GET /health/vlm

Check VLM service health.

**Response:**
```json
{
  "status": "healthy",
  "vlm_status": "healthy",
  "model": "Qwen3-VL-8B",
  "queue_depth": 0
}
```

---

## Tools

### analyze_image_realtime

Analyze image in real-time for chat conversations.

```python
from tools.document_tools import analyze_image_realtime

result = analyze_image_realtime.invoke({
    "image_path": "/path/to/image.jpg",
    "analysis_prompt": "分析此图像中的缺陷"
})
```

**Output:**
```json
{
  "status": "success",
  "analysis": {
    "defect_type": "披锋",
    "defect_details": "产品边缘存在明显披锋...",
    "severity": "medium",
    "key_insights": ["...", "..."],
    "suggested_actions": ["调整锁模力", "检查分型面"],
    "confidence": 0.95
  }
}
```

### analyze_document_realtime

Analyze PDF/Excel documents in real-time.

```python
from tools.document_tools import analyze_document_realtime

result = analyze_document_realtime.invoke({
    "file_path": "/path/to/report.pdf",
    "focus_areas": "模具问题,缺陷分析"
})
```

### compare_images

Compare defect images to find similar patterns.

```python
from tools.document_tools import compare_images

result = compare_images.invoke({
    "reference_image": "/path/to/new_defect.jpg",
    "comparison_images": "/path/to/case1.jpg,/path/to/case2.jpg",
    "comparison_type": "defect_similarity"
})
```

---

## Usage Examples

### Example 1: Mold Agent with VLM

User uploads an image of a defect, and the mold agent analyzes it:

```
User: 请分析这张图片中的问题 [uploads defect.jpg]

Mold Agent:
1. Calls analyze_image_realtime with uploaded image
2. Gets VLM analysis: defect_type="披锋", severity="high"
3. Searches KB: search_troubleshooting_kb("披锋")
4. Returns combined insights with historical solutions
```

### Example 2: Batch KB Enrichment

Enrich existing cases with VLM metadata during indexing:

```python
from services.troubleshooting.vl_processor import VLProcessor
from services.troubleshooting.indexer import TroubleshootingIndexer

# Process case with VLM
processor = VLProcessor(enabled=True, use_vlm_service=True)
enriched_case = await processor.enrich_case_async(case_data)

# Index with VLM metadata
indexer = TroubleshootingIndexer()
indexer.index_case(enriched_case)
```

### Example 3: VLM-aware Search

Search results are boosted by VLM metadata:

```python
from services.troubleshooting.searcher import TroubleshootingSearcher

searcher = TroubleshootingSearcher()
results = searcher.search("披锋问题", top_k=5)

# Results include VLM fields:
# - vlm_processed: True
# - vlm_confidence: 0.95
# - severity: "high"
# - tags: ["披锋", "分型线"]
# - key_insights: [...]
```

---

## Testing

### Run Integration Tests

```bash
source ~/BestBox/activate-cuda.sh
python scripts/test_vlm_integration.py
```

**Expected Output:**
```
======================================================================
Test Summary
======================================================================
   ✅ PASS: VLM client import
   ✅ PASS: VLM client health
   ✅ PASS: Job store
   ✅ PASS: Document tools import
   ✅ PASS: Mold agent tools
   ✅ PASS: VL processor
   ✅ PASS: Embedder/indexer
   ✅ PASS: Searcher VLM boost
   ✅ PASS: Agent API endpoints

Passed: 9/9
✅ All tests passed!
```

### Test Image Analysis

```bash
python -c "
from tools.document_tools import analyze_image_realtime
import json

result = analyze_image_realtime.invoke({
    'image_path': 'data/troubleshooting/processed/images/sample.jpg'
})
print(json.dumps(json.loads(result), indent=2, ensure_ascii=False))
"
```

### Test VLM Health

```bash
curl http://192.168.1.196:8081/api/v1/health
```

---

## Troubleshooting

### VLM Service Not Available

**Symptom:** `VLM service not available` in health check

**Solutions:**
1. Verify VLM service is running: `curl http://192.168.1.196:8081/api/v1/health`
2. Check network connectivity to VLM server
3. Verify `VLM_SERVICE_URL` environment variable

### Redis Connection Failed

**Symptom:** `redis package not installed` or connection errors

**Solutions:**
1. Install redis: `pip install redis`
2. Start Redis: `docker compose up -d redis`
3. Check `VLM_REDIS_URL` configuration

### Model Validation Errors

**Symptom:** Pydantic validation errors on VLM response

**Solutions:**
1. Check VLM API response format matches models
2. Update `services/vlm/models.py` if API changed
3. Add `extra="allow"` to models for flexibility

### Slow Analysis

**Symptom:** Image analysis takes > 60 seconds

**Solutions:**
1. Check VLM server GPU utilization
2. Reduce image size before upload
3. Use `analysis_depth="quick"` for faster results

---

## Files Changed

| File | Description |
|------|-------------|
| `services/vlm/__init__.py` | Package initialization |
| `services/vlm/client.py` | Async VLM service client |
| `services/vlm/models.py` | Pydantic models for VLM API |
| `services/vlm/job_store.py` | Redis job result storage |
| `services/agent_api.py` | Webhook and upload endpoints |
| `services/troubleshooting/vl_processor.py` | VLM service integration |
| `services/troubleshooting/embedder.py` | VLM metadata in embeddings |
| `services/troubleshooting/indexer.py` | VLM fields in Qdrant payloads |
| `services/troubleshooting/searcher.py` | VLM-aware ranking |
| `tools/document_tools.py` | Real-time analysis tools |
| `agents/mold_agent.py` | VLM tools integration |
| `requirements.txt` | Added httpx, redis |

---

## References

- [VLM API Requirements](design/vlm-api-requirements.md) - API specification for VLM server
- [System Design](system_design.md) - Overall system architecture
- [Plugin System](PLUGIN_SYSTEM.md) - Plugin integration guide
