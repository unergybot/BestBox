# VLM Mapping Validation API Documentation

**Version:** 1.0.0
**Date:** 2026-02-02
**Base URL:** `http://192.168.1.196:8081`

---

## Overview

The VLM Mapping Validation API validates image-to-row mappings in Excel troubleshooting documents using Qwen3-VL vision language model. It supports both single-page and batch processing with async webhook callbacks.

---

## Endpoints

### 1. Validate Single Page

**POST** `/api/v1/validate-mappings`

Validates image-to-row mappings for a single page.

#### Request

**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page_image` | File | Yes | Page render image (PNG/JPEG) |
| `extracted_images[]` | File[] | Yes | Array of extracted images |
| `mapping_context` | String (JSON) | Yes | Structured mapping context |
| `options` | String (JSON) | No | Processing options |
| `webhook_url` | String | No | URL for async callback |

#### Example Request (cURL)

```bash
curl -X POST http://192.168.1.196:8081/api/v1/validate-mappings \
  -F "page_image=@page_1.png" \
  -F "extracted_images[]=@img_001.jpg" \
  -F "extracted_images[]=@img_002.jpg" \
  -F 'mapping_context={
    "case_id": "TS-ABC123-001",
    "page_number": 1,
    "total_pages": 3,
    "columns": [
      {"id": "no", "label": "NO", "description": "Issue number"},
      {"id": "type", "label": "型试", "description": "Trial version"},
      {"id": "item", "label": "项目", "description": "Category"},
      {"id": "problem", "label": "問題點", "description": "Problem description"},
      {"id": "solution", "label": "原因，对策", "description": "Cause and solution"}
    ],
    "rows": [
      {
        "row_id": "r1",
        "values": {
          "no": "1",
          "type": "T0",
          "item": "外观",
          "problem": "披锋问题，产品边缘有毛刺",
          "solution": "调整注塑压力，修整模具分型面"
        }
      }
    ],
    "images": [
      {
        "image_id": "img_001",
        "filename": "case_img001.jpg",
        "anchor": {"row": 23, "col": 8},
        "current_mapping": {
          "row_id": "r1",
          "problem": "披锋问题，产品边缘有毛刺"
        }
      }
    ]
  }' \
  -F 'options={"analysis_depth": "detailed", "output_language": "zh"}'
```

#### Response (202 Accepted)

```json
{
  "job_id": "val_abc123def",
  "status": "pending",
  "estimated_duration": "10-30s",
  "status_url": "/api/v1/validate-mappings/val_abc123def"
}
```

---

### 2. Validate Batch (Multiple Pages)

**POST** `/api/v1/validate-mappings/batch`

Validates image-to-row mappings for multiple pages (max 10 pages).

#### Request

**Content-Type:** `application/json`

```json
{
  "case_id": "TS-ABC123-001",
  "webhook_url": "https://your-callback.com/webhook",
  "options": {
    "analysis_depth": "detailed",
    "output_language": "zh",
    "include_visual_reasoning": true,
    "include_ocr": true,
    "confidence_threshold": 0.90,
    "max_tokens": 2048
  },
  "pages": [
    {
      "page_image_path": "page_1.png",
      "extracted_images": ["img_001.jpg", "img_002.jpg"],
      "mapping_context": {
        "case_id": "TS-ABC123-001",
        "page_number": 1,
        "total_pages": 3,
        "columns": [...],
        "rows": [...],
        "images": [...]
      }
    },
    {
      "page_image_path": "page_2.png",
      "extracted_images": ["img_003.jpg"],
      "mapping_context": {
        "case_id": "TS-ABC123-001",
        "page_number": 2,
        "total_pages": 3,
        "columns": [...],
        "rows": [...],
        "images": [...]
      }
    }
  ]
}
```

#### Example Request (cURL)

```bash
curl -X POST http://192.168.1.196:8081/api/v1/validate-mappings/batch \
  -H "Content-Type: application/json" \
  -d @batch_request.json
```

#### Response (202 Accepted)

```json
{
  "job_id": "batch_abc123def",
  "status": "pending",
  "total_pages": 2,
  "estimated_duration": "20-60s",
  "status_url": "/api/v1/validate-mappings/batch_abc123def"
}
```

---

### 3. Check Job Status

**GET** `/api/v1/validate-mappings/{job_id}

Gets job status and result (if completed).

#### Example Response (Completed)

```json
{
  "job_id": "val_abc123def",
  "status": "completed",
  "case_id": "TS-ABC123-001",
  "job_type": "single",
  "created_at": "2026-02-02T19:00:00",
  "completed_at": "2026-02-02T19:00:25",
  "result": {
    "job_id": "val_abc123def",
    "status": "completed",
    "case_id": "TS-ABC123-001",
    "page_number": 1,
    "summary": {
      "total_images": 2,
      "confirmed": 1,
      "corrected": 1,
      "unmatched": 0,
      "ambiguous": 0,
      "average_confidence": 0.935
    },
    "validations": [
      {
        "image_id": "img_001",
        "filename": "case_img001.jpg",
        "current_mapping": {
          "row_id": "r1",
          "problem": "披锋问题，产品边缘有毛刺"
        },
        "validated_mapping": {
          "row_id": "r1",
          "problem": "披锋问题，产品边缘有毛刺"
        },
        "validation_result": {
          "status": "confirmed",
          "confidence": 0.96,
          "reasoning": "Image shows edge burrs on product edge, consistent with problem description."
        }
      }
    ]
  }
}
```

---

### 4. List All Jobs

**GET** `/api/v1/validate-mappings`

Lists all validation jobs with optional filtering.

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | String | Filter by status (pending/processing/completed/failed) |
| `case_id` | String | Filter by case ID |
| `limit` | Integer | Max results (default: 50, max: 100) |
| `offset` | Integer | Pagination offset |

#### Example Response

```json
{
  "jobs": [
    {
      "job_id": "val_abc123def",
      "case_id": "TS-ABC123-001",
      "status": "completed",
      "job_type": "single",
      "created_at": "2026-02-02T19:00:00",
      "progress": 100
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

---

### 5. Delete Job

**DELETE** `/api/v1/validate-mappings/{job_id}

Deletes a validation job.

#### Response (200 OK)

```json
{
  "message": "Job val_abc123def deleted successfully"
}
```

---

## Mapping Context Structure

```json
{
  "case_id": "TS-ABC123-001",
  "page_number": 1,
  "total_pages": 3,
  "page_context": {
    "continued_from_previous": false,
    "continues_to_next": true,
    "header_row_repeated": true
  },
  "columns": [
    {"id": "no", "label": "NO", "description": "Issue number"},
    {"id": "type", "label": "型试", "description": "Trial version"},
    {"id": "item", "label": "项目", "description": "Category"},
    {"id": "problem", "label": "問題點", "description": "Problem description"},
    {"id": "solution", "label": "原因，对策", "description": "Cause and solution"}
  ],
  "rows": [
    {
      "row_id": "r1",
      "values": {
        "no": "1",
        "type": "T0",
        "item": "外观",
        "problem": "披锋问题，产品边缘有毛刺",
        "solution": "调整注塑压力，修整模具分型面"
      },
      "row_range": {"start": 22, "end": 25},
      "spans_to_next_page": false
    }
  ],
  "images": [
    {
      "image_id": "img_001",
      "filename": "case_img001.jpg",
      "anchor": {"row": 23, "col": 8},
      "current_mapping": {
        "row_id": "r1",
        "problem": "披锋问题，产品边缘有毛刺"
      },
      "mapping_method": "anchor_based",
      "mapping_confidence": null
    }
  ]
}
```

---

## Processing Options

```json
{
  "analysis_depth": "detailed",      // "basic" or "detailed"
  "output_language": "zh",           // "zh", "en", or "both"
  "include_visual_reasoning": true,  // Include visual position analysis
  "include_ocr": true,               // Extract text from images
  "confidence_threshold": 0.90,      // Flag images below this confidence
  "max_tokens": 2048                 // VLM response token limit
}
```

---

## Validation Result Types

| Status | Description | Confidence Range |
|--------|-------------|------------------|
| `confirmed` | Current mapping is correct | Usually > 90% |
| `corrected` | VLM suggests different mapping | Varies |
| `unmatched` | Image couldn't match any row | Usually < 50% |
| `ambiguous` | Multiple possible rows | Usually 50-70% |

---

## Webhook Callback

When `webhook_url` is provided, the server will send a POST callback when processing completes:

```json
{
  "job_id": "val_abc123def",
  "status": "completed",
  "timestamp": "2026-02-02T19:00:25",
  "result": {
    // Full validation result
  }
}
```

---

## Status Codes

| Code | Description |
|------|-------------|
| 200 | Success (GET requests) |
| 202 | Job accepted (async processing started) |
| 400 | Invalid request (missing fields, malformed JSON) |
| 404 | Job not found |
| 413 | Payload too large (images exceed limit) |
| 500 | Server error |

---

## Error Response Format

```json
{
  "error": {
    "code": "MISSING_PAGE_IMAGE",
    "message": "page_image is required",
    "details": {
      "field": "page_image",
      "received": null
    }
  }
}
```

---

## Python Client Example

```python
import asyncio
from services.vlm.client import VLMServiceClient

async def validate_single_page():
    client = VLMServiceClient(base_url="http://192.168.1.196:8081")

    # Submit validation job
    response = await client.validate_mappings(
        page_image_path="page_1.png",
        extracted_image_paths=["img_001.jpg", "img_002.jpg"],
        mapping_context=mapping_context,
        options={"analysis_depth": "detailed", "output_language": "zh"}
    )

    print(f"Job submitted: {response.job_id}")
    print(f"Status URL: {response.status_url}")

    # Wait for completion
    result = await client.wait_for_completion(
        job_id=response.job_id,
        poll_interval=2
    )

    print(f"Status: {result.get('status')}")
    print(f"Summary: {result.get('result', {}).get('summary')}")

asyncio.run(validate_single_page())
```

---

## CLI Tool Usage

```bash
# Single page validation
python scripts/validate-mappings.py single \
  --page page_1.png \
  --images img_001.jpg img_002.jpg \
  --context mapping_context.json \
  --wait

# Batch validation
python scripts/validate-mappings.py batch \
  --batch batch_config.yaml \
  --wait

# Check job status
python scripts/validate-mappings.py status val_abc123def

# List all jobs
python scripts/validate-mappings.py list --status completed

# Generate sample config files
python scripts/validate-mappings.py sample
```

---

## Sample Files

Sample configuration files are available:

- `sample-mapping-context.json` - Example mapping context
- `sample-batch.yaml` - Example batch configuration  
- `sample-options.json` - Example processing options

---

## Quick Start Checklist

1. [ ] Server running at `http://192.168.1.196:8081`
2. [ ] Health check: `GET /api/v1/health`
3. [ ] Prepare mapping context JSON
4. [ ] Submit validation job via POST
5. [ ] Poll status or use webhook callback
6. [ ] Process validation results

---

## Support