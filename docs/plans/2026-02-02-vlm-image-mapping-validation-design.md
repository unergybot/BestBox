# VLM Image-to-Issue Mapping Validation Design

**Date:** 2026-02-02
**Status:** Draft
**Author:** Claude + User collaboration

## Problem Statement

The current `ExcelTroubleshootingExtractor` maps floating images to issue rows using anchor-based position matching with ±15 row tolerance. This approach is fragile because:

- Hardcoded row offset (`idx + 22`) assumes fixed header size
- Tolerance window may incorrectly assign images when rows are close together
- No semantic validation that image content matches the issue
- Floating images in Excel have visual relationships with rows but no programmatic link

### Current Implementation

```python
# In _build_issues()
excel_row = idx + 22  # Hardcoded offset

# Find images within ±15 rows of this issue
for img_idx, img_data in image_map.items():
    if abs(img_data['row'] - excel_row) <= 15:
        issue['images'].append({...})
```

### Excel File Characteristics

- Files span ~7 A4 pages (formatted for printing)
- Each page has repeated column headers (NO, type, item, problem, solution, etc.)
- Issues can span multiple pages when images are large
- One issue (NO + type + item) can have multiple problem rows
- Each problem row is uniquely identified by its **problem description text**
- Images are floating objects positioned visually near their related rows

## Proposed Solution: VLM Validation Layer

Add a validation step after extraction that uses Qwen3-VL to visually verify image-to-row mappings.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Mode | Validation (not full extraction) | Preserves existing logic, VLM only corrects |
| Rendering | Page-by-page | Aligns with Excel print layout, each page self-contained |
| Row identifier | Problem description text | Uniquely identifies rows, works across pages |
| Correction threshold | 90% confidence | Auto-correct above, human review below |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Excel Troubleshooting File                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Phase 1: Extraction (Existing)                      │
│  ExcelTroubleshootingExtractor                                   │
│  • Extract metadata, rows, images                                │
│  • Anchor-based image mapping (±15 rows)                         │
│  • Output: case JSON + extracted images                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Phase 2: Page Rendering (New)                       │
│  PageRenderer                                                    │
│  • LibreOffice headless → PDF → page images                      │
│  • 150-200 DPI, one PNG per A4 page                              │
│  • Build page context map for cross-page tracking                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Phase 3: VLM Validation (New)                       │
│  VLMMappingValidator                                             │
│  • Per page: send page image + extracted images + mapping matrix │
│  • Qwen3-VL validates visual alignment + semantic match          │
│  • Returns corrections with confidence scores                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Phase 4: Correction Engine (New)                    │
│  CorrectionEngine                                                │
│  • confidence > 90%: auto-correct                                │
│  • confidence ≤ 90%: flag for review                             │
│  • Update case JSON with validated mappings                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Phase 5: Review Queue (New)                         │
│  ReviewQueue                                                     │
│  • UI for manual review of low-confidence corrections            │
│  • Accept/Reject/Reassign actions                                │
│  • Audit trail for all corrections                               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Phase 6: Indexing (Existing)                        │
│  Indexer + VLProcessor                                           │
│  • Index validated case to Qdrant                                │
│  • VLM enrichment for image content analysis                     │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### Phase 2: Page Rendering

**Rendering Pipeline:**

```
Excel File
    ↓
[LibreOffice headless] → PDF (preserves print layout, page breaks)
    ↓
[pdf2image] → Page images (one PNG per A4 page)
    ↓
{page_1.png, page_2.png, ..., page_7.png}
```

**Command:**

```bash
libreoffice --headless --convert-to pdf --outdir /tmp excel_file.xlsx
```

**Resolution:** 150-200 DPI (A4 at 150 DPI ≈ 1240 x 1754 pixels)

**Cross-Page Context Map:**

```python
page_context = {
    "page_1": {
        "rows": ["r1", "r2", "r3"],
        "images": ["img_001", "img_002"],
        "continued_from_previous": False,
        "continues_to_next": True
    },
    "page_2": {
        "rows": ["r3", "r4", "r5"],
        "images": ["img_003", "img_004", "img_005"],
        "continued_from_previous": True,
        "continues_to_next": False
    }
}
```

### Phase 3: VLM Validation

**Input Package to VLM (per page):**

1. Page render image (A4 page screenshot)
2. Extracted images for this page (as separate image inputs)
3. Structured mapping matrix (JSON)

**Mapping Matrix Structure:**

```json
{
  "page_number": 1,
  "rows": [
    {
      "row_id": "r1",
      "issue_no": "1",
      "type": "T0",
      "item": "外观",
      "problem": "披锋问题，产品边缘有毛刺"
    },
    {
      "row_id": "r2",
      "issue_no": "1",
      "type": "T0",
      "item": "外观",
      "problem": "表面有划痕，影响外观"
    }
  ],
  "images": [
    {
      "image_id": "img_001",
      "anchor_row": 22,
      "anchor_col": 8,
      "current_mapping": "r1"
    },
    {
      "image_id": "img_002",
      "anchor_row": 25,
      "anchor_col": 8,
      "current_mapping": "r1"
    }
  ]
}
```

**VLM Task:**

1. View page render to understand visual layout
2. Match each extracted image to its visual position on page
3. Identify which row each image is visually aligned with
4. Compare with current mappings
5. Return corrections with confidence

**VLM Output Format:**

```json
{
  "validations": [
    {
      "image_id": "img_001",
      "current_mapping": "r1",
      "validated_mapping": "r1",
      "status": "confirmed",
      "confidence": 96,
      "reason": "Image shows edge burrs (毛刺), matches problem description"
    },
    {
      "image_id": "img_002",
      "current_mapping": "r1",
      "validated_mapping": "r2",
      "status": "corrected",
      "confidence": 91,
      "reason": "Image shows scratches (划痕), visually aligned with row 2"
    }
  ]
}
```

**Qwen3-VL Capabilities Leveraged:**

- Multi-image input (256K token context)
- Strong OCR (32 languages including Chinese)
- Visual grounding (bounding boxes, positions)
- Structured JSON output

### Phase 4: Correction Engine

**Decision Flow:**

| Status | Confidence | Action |
|--------|------------|--------|
| `confirmed` | Any | No change, mark as validated |
| `corrected` | > 90% | Auto-update mapping |
| `corrected` | ≤ 90% | Add to review queue |
| `unmatched` | Any | Flag for review |
| `ambiguous` | Any | Flag for review |

**Correction Record:**

```python
@dataclass
class MappingCorrection:
    image_id: str
    page_number: int

    # Original mapping
    original_row_id: str
    original_problem: str

    # VLM result
    validated_row_id: str
    validated_problem: str
    confidence: float
    reason: str

    # Action taken
    status: str  # "auto_corrected", "flagged", "confirmed"
    corrected_at: datetime
    reviewed_by: Optional[str] = None
```

### Phase 5: Review Queue

**Review UI Requirements:**

```
┌─────────────────────────────────────────────────────────────┐
│ Case: TS-ABC123-001          Pending Reviews: 2             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Image: img_002                    Confidence: 88%           │
│ ┌─────────────┐                                             │
│ │             │  Current mapping:                           │
│ │  [image]    │  Row r1: "披锋问题，产品边缘有毛刺"          │
│ │             │                                             │
│ └─────────────┘  VLM suggests:                              │
│                  Row r2: "表面有划痕，影响外观"              │
│                                                             │
│  VLM reason: "Image shows scratches (划痕), visually        │
│              aligned with row 2 on page"                    │
│                                                             │
│  [ Accept VLM ] [ Keep Original ] [ Assign to: ▼ ]         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Audit Trail:**

```python
{
    "correction_id": "corr_001",
    "case_id": "TS-ABC123-001",
    "image_id": "img_002",
    "action": "vlm_accepted",
    "original_row": "r1",
    "final_row": "r2",
    "vlm_confidence": 88,
    "reviewed_by": "operator_zhang",
    "reviewed_at": "2026-02-02T11:00:00Z"
}
```

## Data Model Changes

### Enhanced Image Structure

```python
{
    "image_id": "case_img001",
    "file_path": "/output/images/case_img001.jpg",

    # Anchor-based extraction (existing)
    "anchor": {
        "row": 22,
        "col": 8,
        "page": 1
    },

    # VLM validation (new)
    "mapping_validation": {
        "status": "validated",  # "pending", "validated", "review_required"
        "method": "vlm_corrected",  # "anchor_based", "vlm_confirmed", "vlm_corrected", "manual"
        "confidence": 92.5,
        "vlm_reason": "Image shows scratches, visually aligned with row 2",
        "validated_at": "2026-02-02T10:30:00Z",
        "reviewed_by": None
    },

    # VLM content analysis (existing, enriched)
    "vl_description": "产品表面有明显划痕，长度约3cm",
    "defect_type": "scratches",
    "severity": "medium",
    "text_in_image": "T1-003"
}
```

### Issue Row Structure

```python
{
    "issue_number": 1,
    "type": "T0",
    "item": "外观",
    "problem": "表面有划痕，影响外观",
    "solution": "调整顶出速度，检查模具表面",

    # Row identifier for cross-page tracking (new)
    "row_id": "r2",

    "images": [ ... ],

    # Validation summary (new)
    "image_mapping_status": {
        "total": 2,
        "validated": 2,
        "pending_review": 0
    }
}
```

### Case-Level Validation Metadata

```python
{
    "case_id": "TS-ABC123-001",
    "metadata": { ... },
    "issues": [ ... ],

    # VLM validation summary (new)
    "vlm_validation": {
        "status": "completed",
        "validated_at": "2026-02-02T10:35:00Z",
        "pages_processed": 7,
        "total_images": 15,
        "auto_corrected": 3,
        "pending_review": 2,
        "average_confidence": 91.3
    }
}
```

## Error Handling

| Error Type | Cause | Handling |
|------------|-------|----------|
| `render_failed` | LibreOffice/PDF conversion error | Retry once, fall back to anchor-only |
| `vlm_timeout` | VLM service slow/unavailable | Keep anchor-based, mark `validation_pending` |
| `vlm_parse_error` | VLM returned invalid JSON | Retry with simplified prompt, then flag |
| `no_images_found` | VLM can't locate images on page | Log warning, keep anchor-based |
| `row_not_found` | VLM references unknown row | Flag for manual review |

**Graceful Degradation:**

```
VLM Validation Attempt
    ↓
Success? ──Yes──→ Apply corrections
    │
    No
    ↓
Retry (max 2) ──Success──→ Apply corrections
    │
    Fail
    ↓
Keep anchor-based mapping
Mark: vlm_validation.status = "failed"
Add to retry queue
```

## Implementation

### New Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `PageRenderer` | `services/troubleshooting/page_renderer.py` | Excel → PDF → page images |
| `VLMMappingValidator` | `services/troubleshooting/vlm_validator.py` | Build matrix, call VLM, parse results |
| `CorrectionEngine` | `services/troubleshooting/correction_engine.py` | Apply/flag corrections by confidence |
| `ReviewQueue` | `services/troubleshooting/review_queue.py` | Manage pending reviews, audit trail |
| `ValidationPipeline` | `services/troubleshooting/validation_pipeline.py` | Orchestrate phases 2-5 |

### API Changes

```python
async def extract_and_validate(
    excel_path: Path,
    validate_mappings: bool = True,
    auto_correct_threshold: float = 0.90,
    skip_review_queue: bool = False
) -> ValidatedCase:
    """Extract case with optional VLM mapping validation"""
```

### Configuration

```python
# Environment variables
VLM_VALIDATION_ENABLED=true
VLM_AUTO_CORRECT_THRESHOLD=0.90
VLM_PAGE_RENDER_DPI=150
LIBREOFFICE_PATH=/usr/bin/libreoffice
```

### Dependencies

```
pdf2image>=1.16.0
Pillow>=10.0.0
# LibreOffice installed on system
```

## Performance

**Processing Time Estimate (per case):**

| Phase | Time |
|-------|------|
| Extraction | ~2s |
| Page rendering (7 pages) | ~5s |
| VLM validation (7 calls) | ~30-60s |
| Correction processing | <1s |
| **Total** | ~40-70s per case |

**Batch Processing (1000+ cases):**

- Sequential: ~11-19 hours
- With concurrency (4 workers): ~3-5 hours
- Consider off-peak processing for large batches

## Future Improvements

1. **Confidence threshold tuning** - Analyze audit trail to optimize 90% threshold
2. **VLM fine-tuning** - Use corrected mappings as training data
3. **Caching** - Cache page renders for re-validation scenarios
4. **Batch VLM calls** - Send multiple pages in single request where possible

## References

- [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL)
- [Qwen3-VL Technical Report](https://arxiv.org/abs/2511.21631)
- Existing: `services/troubleshooting/excel_extractor.py`
- Existing: `services/vlm/client.py`
