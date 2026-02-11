# GLM-OCR Bbox Precision Improvement Design

**Date:** 2026-02-11
**Goal:** Improve image extraction accuracy by producing tighter, more precise bounding boxes that crop to actual image content without extra whitespace or adjacent text/headers.

**Priority:** Precision over recall - prefer clean, accurate extractions even if it means missing ~5-10% of marginal detections.

---

## Background

### Current State

BestBox uses the GLM-OCR SDK with PP-DocLayoutV3 for two-stage document processing:
1. **Layout Analysis:** PP-DocLayoutV3 detects document regions (text, images, tables, formulas)
2. **Recognition:** GLM-OCR processes each region for text extraction

Recent improvements:
- ✅ Fixed bbox merging: Changed `layout_merge_bboxes_mode` from `large` → `small` for images/charts
- ✅ Frontend rendering: Updated KB viewer to display inline images with new format

### Problem

Current bbox extraction includes extra content:
- Image bboxes span multiple elements (product photo + heading + partial text)
- Text blocks with image-like layouts get extracted as images
- Average bbox height: ~330pt (too large for individual product images)

**Example:** Page 3 of ppd407.pdf extracts:
- `p3_img0`: [45, 108, 272, 422] (314pt tall) - includes Black specks image + Brittleness heading + partial second image
- Should be: Two separate extractions, each ~180-200pt tall

### Current Configuration

```yaml
# docker/config.glm-sdk.yaml
layout:
  threshold: 0.3           # Low confidence threshold
  pdf_dpi: 200            # Standard resolution
  layout_unclip_ratio: [1.0, 1.0]  # No bbox expansion
```

---

## Design Approach

### Recommended Solution: Threshold + Stricter Element Filtering

Combine higher detection confidence with semantic label filtering to extract only true images/charts.

**Why this approach:**
- Leverages PP-DocLayoutV3's semantic understanding (knows what's an image vs. text)
- Surgical precision without complex post-processing
- Maintainable through configuration
- Fast - no additional processing overhead

**Trade-offs:**
- May miss ~5-10% of borderline detections (small icons, decorative graphics)
- Requires threshold tuning for different document types

### Alternative Approaches Considered

**Alternative 1: Conservative Threshold Only**
- Change: `threshold: 0.6`
- Pros: Simplest, one parameter
- Cons: Less granular control, may still extract headers with high confidence

**Alternative 2: Moderate Threshold + Bbox Shrinking**
- Change: `threshold: 0.45`, `layout_unclip_ratio: [0.95, 0.95]`
- Pros: Automatically trims edges
- Cons: Fixed shrink ratio may over/under-trim

---

## Implementation

### 1. Configuration Changes

**File:** `docker/config.glm-sdk.yaml`

```yaml
layout:
  threshold: 0.55  # Increased from 0.3 for higher precision

  label_task_mapping:
    text: [abstract, algorithm, content, doc_title, figure_title, paragraph_title, reference_content, text, vertical_text, vision_footnote, seal, formula_number]
    table: [table]
    formula: [display_formula, inline_formula]
    skip: [chart, image]  # Keep these skipped from OCR
    abandon: [header, footer, number, footnote, aside_text, reference, footer_image, header_image]
```

**Key changes:**
- `threshold: 0.3 → 0.55` (83% increase) - requires higher confidence
- Explicit semantic label mapping preserved from current config

### 2. Code Changes

**File:** `services/admin_endpoints.py` (~line 308)

Update `_is_glm_image_element()` to filter by semantic labels:

```python
def _is_glm_image_element(elem: Dict[str, Any]) -> bool:
    """Check if element is a true image/chart (not text or header).

    Uses PP-DocLayoutV3 semantic labels for precise filtering.
    """
    elem_type = elem.get("type", "").lower()
    label = elem.get("label", "").lower()

    # Accept explicit image/chart types
    if elem_type in ("image", "chart"):
        return True

    # Filter by PP-DocLayoutV3 label IDs
    # ID 3 = chart, ID 14 = image
    if label in ("chart", "image"):
        return True

    # Reject headers, footers, text blocks
    reject_labels = ["header", "footer", "figure_title", "doc_title",
                     "paragraph_title", "text", "content", "abstract",
                     "reference_content"]
    if label in reject_labels:
        return False

    # Fallback: check if bbox_2d exists
    return "bbox_2d" in elem
```

**Logic:**
1. Check explicit `type` field (image/chart)
2. Check PP-DocLayoutV3 `label` field (semantic classification)
3. Reject text-related labels
4. Fallback to bbox presence

### 3. Deployment Steps

```bash
# 1. Backup current config
cp docker/config.glm-sdk.yaml docker/config.glm-sdk.yaml.backup

# 2. Apply configuration changes (edit file)
vim docker/config.glm-sdk.yaml

# 3. Update extraction filter (edit file)
vim services/admin_endpoints.py

# 4. Restart services
docker restart bestbox-glm-sdk
pkill -f agent_api && venv/bin/python services/agent_api.py > agent_api.log 2>&1 &

# 5. Run validation test
venv/bin/python scripts/test_bbox_precision.py
```

---

## Testing Strategy

### Baseline Test

Create `scripts/test_bbox_precision.py`:

```python
#!/usr/bin/env python3
"""Compare bbox precision before/after config changes."""

import json
import fitz
from pathlib import Path

def analyze_extraction_quality(pdf_path: Path, metadata_path: Path):
    """Calculate precision metrics for extracted images."""

    doc = fitz.open(str(pdf_path))
    with open(metadata_path) as f:
        manifest = json.load(f)

    images = manifest.get("images", {})

    metrics = {
        "total_extractions": len(images),
        "oversized_boxes": 0,      # Boxes >400pt tall
        "avg_box_height": 0,
        "avg_box_width": 0
    }

    heights = []
    widths = []

    for img_id, img_data in images.items():
        bbox = img_data["bbox"]
        height = bbox[3] - bbox[1]
        width = bbox[2] - bbox[0]

        heights.append(height)
        widths.append(width)

        # Flag oversized (likely merged text+image)
        if height > 400:
            metrics["oversized_boxes"] += 1

    if heights:
        metrics["avg_box_height"] = sum(heights) / len(heights)
        metrics["avg_box_width"] = sum(widths) / len(widths)

    doc.close()
    return metrics

# Usage
if __name__ == "__main__":
    pdf = Path("docs/ppd407.pdf")
    metadata = Path("data/uploads/images/mold_reference_kb/<doc-id>/metadata.json")

    results = analyze_extraction_quality(pdf, metadata)
    print(f"Total extractions: {results['total_extractions']}")
    print(f"Oversized boxes: {results['oversized_boxes']}")
    print(f"Avg height: {results['avg_box_height']:.0f}pt")
    print(f"Avg width: {results['avg_box_width']:.0f}pt")
```

### Test Process

1. **Baseline:** Upload ppd407.pdf with current config (threshold=0.3)
   - Record: total images, avg height, oversized count

2. **Apply changes:** Update config, restart GLM-SDK

3. **Test:** Upload same PDF with new config (threshold=0.55)
   - Compare metrics

### Success Criteria

**Target improvements:**
- ✅ Reduce oversized boxes (>400pt) by **50%+**
- ✅ Reduce average box height by **15-25%**
- ✅ Maintain **90%+ recall** on actual product images (manual spot check)

**Example expected results:**
```
Before: 6 detections, avg height 330pt, 2 oversized
After:  4 detections, avg height 250pt, 0 oversized
```

---

## Monitoring & Observability

### Logging Enhancements

Add to `_extract_images_from_pdf()`:

```python
logger.info(
    f"Image extraction stats for {pdf_path.name}: "
    f"detected={len(manifest)} images, "
    f"avg_height={sum(img['bbox'][3]-img['bbox'][1] for img in manifest.values())/len(manifest) if manifest else 0:.0f}pt, "
    f"rejected_text_blocks={rejected_count}"
)
```

### Monitoring Metrics

**Watch for:**
- Sudden drop in detection count (threshold too high)
- User complaints about missing images
- Extraction time (shouldn't change significantly)

**Dashboard:** Track over time:
- Images per document (avg)
- Bbox height distribution
- Rejected element count by label type

---

## Edge Cases & Limitations

### Works Well For

- Standard technical documentation (mold defect guides, product specs)
- Product photos with clear boundaries
- Charts and diagrams with distinct layouts
- High-contrast images

### May Struggle With

- **Images with text overlays:** May get rejected as "text" if text dominates
  - Mitigation: Manual review, consider threshold adjustment per collection

- **Very small icons (<50pt):** Below confidence threshold
  - Mitigation: Lower threshold to 0.45 for icon-heavy documents

- **Hand-drawn sketches:** Low contrast, irregular boundaries
  - Mitigation: Pre-process with contrast enhancement, or use pdf_dpi: 300

- **Complex layouts:** Images embedded within tables
  - Current behavior: Should detect correctly with PP-DocLayoutV3
  - Monitor: Test with sample complex documents

### Rollback Plan

If precision degrades or too many images are missed:

1. **Moderate rollback:** `threshold: 0.55 → 0.4` (middle ground)
2. **Keep label filtering:** Maintain semantic filtering code
3. **Alternative approach:** Try Alternative 2 (threshold + bbox shrinking)
4. **Full rollback:** Restore `config.glm-sdk.yaml.backup`

---

## Future Enhancements (Optional)

If precision needs further improvement:

### 1. DPI Increase
```yaml
page_loader:
  pdf_dpi: 300  # Up from 200
```
- Better small detail detection
- Trade-off: 50% increase in processing time

### 2. Collection-Specific Thresholds
```python
THRESHOLD_BY_COLLECTION = {
    "mold_reference_kb": 0.55,     # High precision
    "general_docs": 0.40,           # More recall
    "product_manuals": 0.50         # Balanced
}
```

### 3. Lightweight Post-Processing
```python
# Trim 5-10px whitespace using PIL
def trim_whitespace(image_path: Path):
    from PIL import Image, ImageChops

    img = Image.open(image_path)
    bg = Image.new(img.mode, img.size, img.getpixel((0,0)))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        return img.crop(bbox)
    return img
```

---

## References

**GLM-OCR Documentation:**
- [GLM-OCR GitHub Repository](https://github.com/zai-org/GLM-OCR)
- [GLM-OCR on Hugging Face](https://huggingface.co/zai-org/GLM-OCR)
- [GLM-OCR Official Documentation](https://docs.z.ai/guides/vlm/glm-ocr)
- [StableLearn GLM-OCR Introduction](https://stable-learn.com/en/glm-ocr-introduction/)

**PP-DocLayoutV3:**
- Two-stage pipeline: Layout analysis → Parallel recognition
- 25 semantic labels (IDs 0-24) for document elements
- Confidence threshold controls detection sensitivity

**Related Design Documents:**
- `2026-02-10-glm-ocr-image-extraction-design.md` - Initial image extraction feature
- `2026-02-11-glm-ocr-bbox-merge-fix.md` - Fixed bbox merging (large → small)

---

## Success Metrics Summary

**Technical Metrics:**
- Oversized boxes: 2 → 0 (100% reduction)
- Avg bbox height: 330pt → 250pt (24% reduction)
- Detection count: 6 → 4 (33% reduction, within acceptable range)

**Quality Metrics:**
- No text contamination in extracted images
- All product images clearly visible without cropping
- No excessive whitespace around image content

**User Experience:**
- KB viewer displays clean, professional-looking images
- No user complaints about missing critical images
- Faster visual scanning of technical documentation

---

## Approval & Next Steps

**Design Status:** ✅ Complete and ready for implementation

**Next Actions:**
1. Review and approve design
2. Create worktree: `git worktree add .worktrees/bbox-precision -b feature/bbox-precision`
3. Implement configuration changes
4. Update extraction filter function
5. Run baseline and validation tests
6. Deploy to production
7. Monitor metrics for 1 week

**Estimated Effort:** 2-3 hours (config + code + testing)

**Risk Assessment:** Low - Changes are reversible, non-breaking, config-driven
