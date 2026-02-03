# VLM Mapping Validation API Specification

**Date:** 2026-02-02
**Status:** Draft
**Related:** `2026-02-02-vlm-image-mapping-validation-design.md`

## Overview

This document specifies the new VLM API endpoint required to support image-to-issue mapping validation. The endpoint enables Qwen3-VL to validate and correct image-row mappings by analyzing visual layout relationships.

## Current API Endpoints (Reference)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/jobs/upload` | POST | Single file analysis |
| `/api/v1/jobs/batch` | POST | Batch file processing |
| `/api/v1/jobs/{job_id}` | GET | Check job status |
| `/api/v1/compare` | POST | Image similarity comparison |
| `/api/v1/health` | GET | Service health check |

## New Endpoint: Validate Mappings

### `POST /api/v1/validate-mappings`

Validates image-to-row mappings by analyzing a page render alongside extracted images and their current mappings.

### Request

**Content-Type:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `page_image` | File | Yes | Rendered page image (PNG/JPEG, 150-200 DPI) |
| `extracted_images[]` | File[] | Yes | Array of extracted images to validate |
| `mapping_context` | JSON String | Yes | Structured mapping context (see below) |
| `options` | JSON String | No | Processing options |
| `webhook_url` | String | No | URL for async result callback |

**mapping_context Structure:**

```json
{
  "case_id": "TS-ABC123-001",
  "page_number": 1,
  "total_pages": 7,

  "page_context": {
    "continued_from_previous": false,
    "continues_to_next": true,
    "header_row_repeated": true
  },

  "columns": [
    {"id": "no", "label": "NO", "description": "Issue number"},
    {"id": "type", "label": "型试", "description": "Trial version (T0/T1/T2)"},
    {"id": "item", "label": "项目", "description": "Category"},
    {"id": "problem", "label": "問題点", "description": "Problem description"},
    {"id": "solution", "label": "原因，对策", "description": "Cause and solution"},
    {"id": "result_t1", "label": "修正結果T1", "description": "T1 trial result"},
    {"id": "result_t2", "label": "修正結果T2", "description": "T2 trial result"}
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
    },
    {
      "row_id": "r2",
      "values": {
        "no": "1",
        "type": "T0",
        "item": "外观",
        "problem": "表面有划痕，影响外观质量",
        "solution": "检查顶针，调整顶出速度"
      },
      "row_range": {"start": 26, "end": 30},
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
    },
    {
      "image_id": "img_002",
      "filename": "case_img002.jpg",
      "anchor": {"row": 27, "col": 8},
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

**options Structure:**

```json
{
  "analysis_depth": "detailed",
  "output_language": "zh",
  "include_visual_reasoning": true,
  "include_ocr": true,
  "confidence_threshold": 0.90,
  "max_tokens": 2048
}
```

### Response

**Success Response (Synchronous):**

```json
{
  "job_id": "val_abc123",
  "status": "completed",
  "case_id": "TS-ABC123-001",
  "page_number": 1,

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
        "reasoning": "Image shows edge burrs (毛刺) on product edge, consistent with problem description. Image is visually positioned adjacent to row 1."
      },

      "visual_analysis": {
        "detected_position": {"row_approx": 23, "col_approx": 8},
        "nearest_rows": ["r1"],
        "visual_alignment": "strong"
      },

      "content_analysis": {
        "defect_type": "flash/burr",
        "defect_description": "产品边缘有明显毛刺，约2-3mm突出",
        "text_in_image": null,
        "severity": "medium"
      }
    },
    {
      "image_id": "img_002",
      "filename": "case_img002.jpg",

      "current_mapping": {
        "row_id": "r1",
        "problem": "披锋问题，产品边缘有毛刺"
      },

      "validated_mapping": {
        "row_id": "r2",
        "problem": "表面有划痕，影响外观质量"
      },

      "validation_result": {
        "status": "corrected",
        "confidence": 0.91,
        "reasoning": "Image shows surface scratches (划痕), not burrs. Visually positioned closer to row 2. Content matches row 2 problem description."
      },

      "visual_analysis": {
        "detected_position": {"row_approx": 28, "col_approx": 8},
        "nearest_rows": ["r2", "r1"],
        "visual_alignment": "strong"
      },

      "content_analysis": {
        "defect_type": "scratches",
        "defect_description": "产品表面有多条划痕，长度约3-5cm",
        "text_in_image": "T1-003",
        "severity": "medium"
      }
    }
  ],

  "summary": {
    "total_images": 2,
    "confirmed": 1,
    "corrected": 1,
    "unmatched": 0,
    "ambiguous": 0,
    "average_confidence": 0.935
  },

  "cross_page_notes": [
    {
      "type": "row_continuation",
      "row_id": "r2",
      "note": "Row appears to continue on next page based on visual layout"
    }
  ],

  "metadata": {
    "processing_time_ms": 3420,
    "model": "Qwen3-VL-8B",
    "tokens_used": 1856
  }
}
```

**Async Response (when webhook_url provided):**

```json
{
  "job_id": "val_abc123",
  "status": "pending",
  "estimated_duration": "10-15s",
  "check_status_url": "/api/v1/validate-mappings/val_abc123"
}
```

### Status Codes

| Code | Description |
|------|-------------|
| 200 | Validation completed successfully |
| 202 | Job accepted (async processing) |
| 400 | Invalid request (missing fields, malformed JSON) |
| 413 | Payload too large (images exceed limit) |
| 422 | Unprocessable (invalid image format, corrupted file) |
| 500 | Server error |
| 503 | Service unavailable (model loading, GPU OOM) |

### Error Response

```json
{
  "error": {
    "code": "INVALID_MAPPING_CONTEXT",
    "message": "mapping_context.rows is required and must be non-empty",
    "details": {
      "field": "mapping_context.rows",
      "received": null
    }
  }
}
```

## Validation Result Types

| Status | Description | Confidence |
|--------|-------------|------------|
| `confirmed` | Current mapping is correct | Usually > 90% |
| `corrected` | VLM suggests different mapping | Varies |
| `unmatched` | Image couldn't be matched to any row | Usually < 50% |
| `ambiguous` | Multiple possible rows, unclear | Usually 50-70% |

## New Pydantic Models (Client-Side)

Add to `services/vlm/models.py`:

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ValidationStatus(str, Enum):
    """Mapping validation status"""
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    UNMATCHED = "unmatched"
    AMBIGUOUS = "ambiguous"


class RowMapping(BaseModel):
    """Row mapping reference"""
    row_id: str
    problem: str


class VisualAnalysis(BaseModel):
    """Visual position analysis"""
    detected_position: Dict[str, int]
    nearest_rows: List[str]
    visual_alignment: str  # "strong", "moderate", "weak"


class ContentAnalysis(BaseModel):
    """Image content analysis"""
    defect_type: Optional[str] = None
    defect_description: Optional[str] = None
    text_in_image: Optional[str] = None
    severity: Optional[str] = None


class ValidationResult(BaseModel):
    """Single validation result"""
    status: ValidationStatus
    confidence: float
    reasoning: str


class ImageValidation(BaseModel):
    """Complete validation for one image"""
    image_id: str
    filename: str
    current_mapping: RowMapping
    validated_mapping: RowMapping
    validation_result: ValidationResult
    visual_analysis: Optional[VisualAnalysis] = None
    content_analysis: Optional[ContentAnalysis] = None


class ValidationSummary(BaseModel):
    """Summary of validation results"""
    total_images: int
    confirmed: int
    corrected: int
    unmatched: int
    ambiguous: int
    average_confidence: float


class CrossPageNote(BaseModel):
    """Note about cross-page issues"""
    type: str
    row_id: Optional[str] = None
    note: str


class MappingValidationResult(BaseModel):
    """Complete mapping validation response"""
    job_id: str
    status: str
    case_id: str
    page_number: int
    validations: List[ImageValidation]
    summary: ValidationSummary
    cross_page_notes: List[CrossPageNote] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

## New Client Method

Add to `services/vlm/client.py`:

```python
async def validate_mappings(
    self,
    page_image_path: Union[str, Path],
    extracted_image_paths: List[Union[str, Path]],
    mapping_context: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
    timeout: int = 60
) -> MappingValidationResult:
    """
    Validate image-to-row mappings using VLM.

    Args:
        page_image_path: Path to rendered page image
        extracted_image_paths: Paths to extracted images
        mapping_context: Structured context with rows and current mappings
        options: Processing options
        timeout: Maximum wait time

    Returns:
        MappingValidationResult with validations for each image
    """
    page_path = Path(page_image_path)
    if not page_path.exists():
        raise FileNotFoundError(f"Page image not found: {page_path}")

    client = await self._get_client()

    # Build multipart form
    files = [
        ("page_image", (page_path.name, open(page_path, "rb"), self._guess_content_type(page_path)))
    ]

    for img_path in extracted_image_paths:
        img_path = Path(img_path)
        if not img_path.exists():
            raise FileNotFoundError(f"Extracted image not found: {img_path}")
        files.append(
            ("extracted_images[]", (img_path.name, open(img_path, "rb"), self._guess_content_type(img_path)))
        )

    data = {
        "mapping_context": json.dumps(mapping_context, ensure_ascii=False)
    }
    if options:
        data["options"] = json.dumps(options)

    response = await self._request_with_retry(
        "POST",
        "/api/v1/validate-mappings",
        files=files,
        data=data,
        timeout=timeout
    )

    return MappingValidationResult(**response)
```

## VLM Server Implementation Notes

### Prompt Engineering

The VLM server should construct a prompt like:

```
You are validating image-to-row mappings in an Excel troubleshooting document.

## Page Information
- Case ID: {case_id}
- Page: {page_number} of {total_pages}
- Continued from previous page: {continued_from_previous}

## Column Definitions
{columns formatted as table}

## Rows on This Page
{rows formatted with row_id, values}

## Images to Validate
{images with current mappings}

## Task
For each image:
1. Locate it on the page render
2. Identify which row it is visually aligned with
3. Analyze image content (defect type, description)
4. Compare with current mapping
5. Return validation with confidence score

## Output Format
Return JSON with validations array...
```

### Multi-Image Input

Qwen3-VL supports interleaved image-text input:

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "This is the page render:"},
            {"type": "image", "image": page_image_base64},
            {"type": "text", "text": "These are the extracted images to validate:"},
            {"type": "text", "text": "Image 1 (img_001):"},
            {"type": "image", "image": extracted_img_1_base64},
            {"type": "text", "text": "Image 2 (img_002):"},
            {"type": "image", "image": extracted_img_2_base64},
            {"type": "text", "text": prompt_with_context}
        ]
    }
]
```

### Performance Considerations

| Factor | Recommendation |
|--------|----------------|
| Max images per request | 10-15 (to stay within context limits) |
| Page image resolution | 150-200 DPI (balance quality vs. tokens) |
| Extracted image size | Resize to max 800px on longest edge |
| Timeout | 30-60s per page |
| Concurrent requests | Limit to 2-4 based on GPU memory |

### Caching

Consider caching:
- Page renders (by Excel file hash + page number)
- VLM results (by request hash, short TTL)

## Testing

### Test Cases

1. **All confirmed** - All mappings are correct
2. **Some corrected** - VLM identifies and corrects errors
3. **Cross-page row** - Row spans multiple pages
4. **Unmatched image** - Image can't be matched to any row
5. **Ambiguous mapping** - Multiple possible rows
6. **Large page** - Page with 15+ images
7. **Low quality image** - Blurry or low-resolution page render

### Example Test Request

```bash
curl -X POST http://localhost:8081/api/v1/validate-mappings \
  -F "page_image=@page_1.png" \
  -F "extracted_images[]=@img_001.jpg" \
  -F "extracted_images[]=@img_002.jpg" \
  -F 'mapping_context={"case_id":"test","page_number":1,...}' \
  -F 'options={"analysis_depth":"detailed"}'
```

## Migration Path

1. **Phase 1:** Deploy new endpoint on VLM server
2. **Phase 2:** Add client method to `VLMServiceClient`
3. **Phase 3:** Implement `VLMMappingValidator` using new endpoint
4. **Phase 4:** Integration testing with real Excel files
5. **Phase 5:** Production rollout with monitoring

## Appendix: Full mapping_context Example

```json
{
  "case_id": "TS-ABC123-001",
  "page_number": 2,
  "total_pages": 7,

  "page_context": {
    "continued_from_previous": true,
    "continues_to_next": true,
    "header_row_repeated": true
  },

  "columns": [
    {"id": "no", "label": "NO", "description": "Issue number"},
    {"id": "type", "label": "型试", "description": "Trial version"},
    {"id": "item", "label": "项目", "description": "Category"},
    {"id": "problem", "label": "問題点", "description": "Problem description"},
    {"id": "solution", "label": "原因，对策", "description": "Cause and solution"},
    {"id": "result_t1", "label": "修正結果T1", "description": "T1 result"},
    {"id": "result_t2", "label": "修正結果T2", "description": "T2 result"},
    {"id": "cause_class", "label": "原因分类", "description": "Cause classification"}
  ],

  "rows": [
    {
      "row_id": "r3",
      "values": {
        "no": "2",
        "type": "T0",
        "item": "尺寸",
        "problem": "产品尺寸超差，长度偏大0.5mm",
        "solution": "调整保压时间，检查冷却系统"
      },
      "row_range": {"start": 21, "end": 28},
      "spans_to_next_page": false
    },
    {
      "row_id": "r4",
      "values": {
        "no": "3",
        "type": "T0",
        "item": "外观",
        "problem": "注塑气泡，产品内部有空洞",
        "solution": "降低注塑速度，增加排气槽"
      },
      "row_range": {"start": 29, "end": 35},
      "spans_to_next_page": false
    },
    {
      "row_id": "r5",
      "values": {
        "no": "3",
        "type": "T0",
        "item": "外观",
        "problem": "表面缩水，产品局部凹陷",
        "solution": "增加保压压力，延长冷却时间"
      },
      "row_range": {"start": 36, "end": 42},
      "spans_to_next_page": true
    }
  ],

  "images": [
    {
      "image_id": "img_005",
      "filename": "case_img005.jpg",
      "anchor": {"row": 24, "col": 8},
      "current_mapping": {
        "row_id": "r3",
        "problem": "产品尺寸超差，长度偏大0.5mm"
      },
      "mapping_method": "anchor_based",
      "mapping_confidence": null
    },
    {
      "image_id": "img_006",
      "filename": "case_img006.jpg",
      "anchor": {"row": 31, "col": 8},
      "current_mapping": {
        "row_id": "r4",
        "problem": "注塑气泡，产品内部有空洞"
      },
      "mapping_method": "anchor_based",
      "mapping_confidence": null
    },
    {
      "image_id": "img_007",
      "filename": "case_img007.jpg",
      "anchor": {"row": 38, "col": 8},
      "current_mapping": {
        "row_id": "r5",
        "problem": "表面缩水，产品局部凹陷"
      },
      "mapping_method": "anchor_based",
      "mapping_confidence": null
    }
  ]
}
```
