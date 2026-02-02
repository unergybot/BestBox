# VLM Integration Improvement Plan

**Date:** 2026-02-01  
**Based on:** Review of [VLM_INTEGRATION.md](VLM_INTEGRATION.md) vs actual implementation  
**Test File:** `docs/1947688(ED736A0501)-case.xlsx` (20 issues, 37 images)

---

## Test Results Summary

### What's Working ✅
1. **VLM Service (192.168.1.196:8081)**: Healthy with Qwen3-VL-8B, 64GB GPU
2. **Excel Extraction**: 20 issues + 37 images extracted successfully
3. **VLM Image Analysis**: Returns defect analysis with 0.98 confidence
4. **VLM Client Code**: Full async support, webhook/polling, retry logic
5. **Searcher VLM Boost**: Score multiplier based on `vlm_confidence` implemented

### What's NOT Working ❌
1. **KB Enrichment**: All `vl_description` fields are `null` - pipeline not connected
2. **Document Analysis**: Returns "需转换为图像格式" - client-side check blocks files
3. **Frontend Upload**: No file upload UI component exists
4. **VLM Insights Display**: Cards don't show severity, insights, actions

---

## Executive Summary

The VLM integration is **partially implemented**. Core infrastructure works, but critical gaps exist:

| Component | Status | Gaps |
|-----------|--------|------|
| VLM Service Client | ✅ Working | - |
| Image Analysis | ✅ Working | Results not persisted to KB |
| Document (Excel/PDF) | ❌ NOT WORKING | VLM only accepts images |
| KB Enrichment Pipeline | ❌ Incomplete | `vl_description` fields are null |
| Frontend File Upload | ❌ Missing | No drag-drop or file picker |
| VLM Metadata Display | ⚠️ Partial | No severity/insights shown in cards |

---

## Gap Analysis

### 1. Document Processing Client-Side Bug

**Finding:** The `analyze_document_realtime` tool returns:
```json
{
  "summary": "文档分析需要转换为图像格式。当前版本仅支持图像文件",
  "confidence": 0.0
}
```

**Root Cause:** The BestBox client code (`tools/document_tools.py`) incorrectly returns early for non-image files. The external VLM service (Qwen3-VL-8B at 192.168.1.196:8081) **actually supports PDF natively** per user confirmation.

**Impact:** Users cannot analyze documents in chat — a major feature advertised in the docs.

**Fix Required:**
- Remove the early-return check in `analyze_document_realtime` that blocks PDF/Excel
- Allow the file to be submitted directly to VLM service
- For Excel: either submit directly (if VLM supports) or render sheets as images first

### 2. KB Enrichment Pipeline Not Connected

**Finding:** Excel extraction works perfectly (20 issues, 37 images extracted), but:
```python
"vl_description": null,
"defect_type": null,
"text_in_image": null
```

**Root Cause:** The `VLProcessor.enrich_case_async()` is not called after extraction.

**Impact:** Indexed cases have no VLM metadata → no VLM-boosted search ranking.

**Fix Required:**
- Create `scripts/enrich_and_index_case.py` that chains:
  1. `ExcelTroubleshootingExtractor.extract_case()`
  2. `VLProcessor.enrich_case_async()` 
  3. `TroubleshootingIndexer.index_case()`

### 3. No File Upload UI in Frontend

**Finding:** No file upload component in `frontend/copilot-demo/components/`.

**Impact:** Users cannot share images/documents via chat UI.

**Fix Required:**
- Add `FileUploadButton.tsx` with drag-drop support
- Add `/api/upload` handler that:
  1. Saves file to temp storage
  2. Calls `analyze_image_realtime` or `analyze_document_realtime`
  3. Returns results to chat

### 4. VLM Metadata Not Displayed in Cards

**Finding:** `TroubleshootingCard` shows problem/solution but NOT:
- `severity` (high/medium/low)
- `key_insights`
- `suggested_actions`
- `vlm_confidence`

**Impact:** Rich VLM analysis is computed but never shown to users.

**Fix Required:**
- Add `VLMInsights` component to `DetailedView.tsx`
- Show severity badge, insights list, action items

### 5. Missing Image-to-Text Description Display

**Finding:** Images in DetailedView show `alt={img.description}` but the field is often null.

**Impact:** No context for what the image shows.

**Fix Required:**
- Display `vl_description` as caption below each image
- Add OCR text tooltip if `text_in_image` is present

---

## Knowledge Base Optimization Gaps

### Current State
```
Excel → Extract → Index (text only, no VLM)
```

### Target State
```
Excel → Extract → VLM Enrich (all images) → Index (text + VLM metadata)
```

### Specific Improvements

| Area | Current | Target | Priority |
|------|---------|--------|----------|
| Image embeddings | Text only | Text + VL description | P1 |
| Defect type indexing | Manual category | VLM-detected defect_type | P1 |
| Severity in payloads | Empty | VLM severity | P2 |
| VLM confidence boost | Implemented but no data | Data populated | P1 |
| Multi-modal search | Text search only | Text + visual similarity | P3 |

### Recommended KB Enrichment Script

```python
# scripts/enrich_and_index_case.py
async def full_pipeline(excel_path: Path):
    # 1. Extract
    extractor = ExcelTroubleshootingExtractor(output_dir=OUTPUT_DIR)
    case = extractor.extract_case(excel_path)
    
    # 2. VLM Enrich (async)
    processor = VLProcessor(enabled=True, use_vlm_service=True)
    enriched = await processor.enrich_case_async(case)
    
    # 3. Index with VLM metadata
    indexer = TroubleshootingIndexer()
    stats = indexer.index_case(enriched)
    
    return stats
```

---

## User Experience Improvements

### P1: File Upload in Chat

**Current:** No way to share files  
**Target:** Drag-drop or click to upload images/documents

Implementation:
```
components/
  FileUploadButton.tsx      # Upload trigger
  FileUploadDropzone.tsx    # Drag-drop area
  
app/api/upload/route.ts     # Server-side handler
```

### P2: VLM Analysis Feedback

**Current:** No visual feedback during VLM processing  
**Target:** Progress indicator with estimated time

```tsx
// components/VLMProcessingIndicator.tsx
<div className="flex items-center gap-2">
  <Spinner />
  <span>Analyzing image... (~15-30s)</span>
</div>
```

### P3: Rich Result Display

**Current:** Plain problem/solution text  
**Target:** Add VLM-derived insights

```tsx
// In DetailedView.tsx
{data.key_insights?.length > 0 && (
  <div className="bg-blue-50 p-3 rounded">
    <h4>AI Insights</h4>
    <ul>
      {data.key_insights.map(i => <li>{i}</li>)}
    </ul>
  </div>
)}
```

### P4: Severity Badge

Add severity indicator to cards:
```tsx
{data.severity === 'high' && (
  <span className="bg-red-500 text-white px-2 py-1 rounded">
    ⚠️ High Severity
  </span>
)}
```

---

## Implementation Roadmap

### Phase 1: KB Enrichment (2-3 days)
- [ ] Create `scripts/enrich_and_index_case.py`
- [ ] Re-process all existing Excel files with VLM
- [ ] Verify VLM metadata in Qdrant payloads
- [ ] Test VLM-boosted search ranking

### Phase 2: Document Processing Fix (2-3 days)
- [ ] Add PDF/Excel → image conversion in `document_tools.py`
- [ ] Use `pdf2image` for PDFs
- [ ] Render Excel sheets as images via `openpyxl` + `pillow`
- [ ] Update `analyze_document_realtime` to handle conversion

### Phase 3: Frontend Enhancements (3-4 days)
- [ ] Add `FileUploadButton` component
- [ ] Create `/api/upload` endpoint
- [ ] Add VLM processing indicator
- [ ] Enhance `DetailedView` with VLM insights
- [ ] Add severity badges to cards

### Phase 4: Search Quality (2 days)
- [ ] A/B test VLM-boosted vs standard ranking
- [ ] Add visual similarity search option
- [ ] Implement "find similar defects" feature

---

## Test Commands

```bash
# Test VLM health
curl http://192.168.1.196:8081/api/v1/health

# Test image analysis
python -c "
from tools.document_tools import analyze_image_realtime
result = analyze_image_realtime.invoke({
    'image_path': '/tmp/vlm_test/images/1947688(ED736A0501)-case_img017.jpg'
})
print(result)
"

# Full enrichment pipeline test
python scripts/enrich_and_index_case.py docs/1947688\(ED736A0501\)-case.xlsx
```

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Cases with VLM metadata | 0% | 100% |
| Search relevance (MRR@5) | ~0.65 | ~0.80 |
| Image descriptions populated | 0% | 100% |
| User file upload success rate | N/A | >95% |
| VLM processing time (per image) | ~15s | ~10s |

---

## Files to Modify

| File | Changes |
|------|---------|
| `tools/document_tools.py` | Add PDF/Excel → image conversion |
| `scripts/enrich_and_index_case.py` | New: full pipeline script |
| `services/troubleshooting/vl_processor.py` | Call from extraction |
| `frontend/.../DetailedView.tsx` | Add VLM insights display |
| `frontend/.../FileUploadButton.tsx` | New: file upload component |
| `frontend/app/api/upload/route.ts` | New: upload API route |
| `docs/VLM_INTEGRATION.md` | Update to reflect actual capabilities |
