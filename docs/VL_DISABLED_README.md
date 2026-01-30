# Troubleshooting KB - Text-Only Mode (VL Disabled)

**Date**: 2026-01-29
**Status**: ✅ Production Ready

---

## Summary

The Troubleshooting Knowledge Base is **fully functional** with text-only search. Vision-Language (VL) processing has been **disabled by default** due to ROCm/AMD GPU compatibility issues with Qwen2.5-VL model (segmentation fault during checkpoint loading).

### What Works ✅

- Excel extraction (20 issues, 52 images from test file)
- Image extraction and storage (images saved to disk)
- Embeddings generation (BGE-M3, 1024-dim vectors)
- Dual-level Qdrant indexing (case + issue collections)
- Semantic search with **0.7+ relevance scores**
- Mold Service Agent integration
- Agent tools: `search_troubleshooting_kb`, `get_troubleshooting_case_details`

### What's Disabled ⚠️

- VL image analysis (automatic defect recognition)
- Image OCR (text extraction from photos)
- Visual annotation detection (red circles, arrows, etc.)

**Impact**: Images are still extracted and stored with cases, but the VL description fields (`vl_description`, `defect_type`, `equipment_part`, `text_in_image`, `visual_annotations`) remain empty.

---

## Technical Details

### VL Compatibility Issue

**Problem**: Qwen2.5-VL-3B-Instruct causes segmentation fault when loading checkpoint shards on AMD Radeon 8060S (gfx1151, RDNA 3.5) with ROCm 7.10.0.

**Attempted Fixes**:
- ✗ Using `AutoModelForVision2Seq` instead of specific class
- ✗ Changed `torch_dtype` to `dtype` parameter
- ✗ Added `attn_implementation="eager"` to avoid flash attention
- All resulted in same segfault at checkpoint loading

**Root Cause**: Low-level operation incompatibility between Qwen2.5-VL model and ROCm backend on RDNA 3.5 GPU.

### Code Changes

**Modified**: `services/troubleshooting/vl_processor.py`

```python
class VLProcessor:
    def __init__(
        self,
        vl_service_url: str = "http://localhost:8083",
        max_workers: int = 4,
        language: str = "zh",
        enabled: bool = False  # ← DISABLED BY DEFAULT
    ):
        ...
```

When `enabled=False`:
- Skips VL service connection
- Adds empty VL fields to all images
- No network calls to VL service
- Fast processing (no waiting for model inference)

---

## Usage

### Normal Operation (VL Disabled)

```python
from services.troubleshooting.vl_processor import VLProcessor

# VL disabled by default
processor = VLProcessor()
enriched = processor.enrich_case(case_data)
# Images have empty VL fields, everything else works
```

### Enable VL (When Available)

```python
# If VL service becomes available in future
processor = VLProcessor(enabled=True)
enriched = processor.enrich_case(case_data)
```

### Search Functionality

```python
from tools.troubleshooting_tools import search_troubleshooting_kb

# Text-based search works perfectly
result = search_troubleshooting_kb.invoke({
    "query": "产品披锋",
    "top_k": 5,
    "only_successful": True
})
# Returns cases with 0.7+ relevance scores
```

---

## Future Options

### Option 1: Wait for Better ROCm Support
- Monitor Qwen2.5-VL updates for ROCm compatibility
- Try newer ROCm versions (currently using 7.10.0)
- Wait for transformers library updates

### Option 2: Alternative VL Models
Try models with better ROCm support:
- `Salesforce/blip2-opt-2.7b` - Good AMD GPU support
- `llava-hf/llava-1.5-7b-hf` - Widely tested on ROCm
- `microsoft/Florence-2-large` - Recent, good compatibility

### Option 3: CPU Inference
- Use CPU for VL processing (very slow but functional)
- ~10-30 seconds per image vs <1 second on GPU
- Set `device_map="cpu"` in VL server

### Option 4: Hybrid Approach
- Use cloud API for VL (OpenAI GPT-4V, Anthropic Claude 3)
- Process images on-demand rather than batch
- Cost vs latency tradeoff

---

## Performance Without VL

### Test Results

**Sample file**: `1947688(ED736A0501)-case.xlsx`
- Extracted: 20 issues, 52 images
- Indexed: 1 case-level + 20 issue-level points
- Search query: "产品披锋"
- Top result relevance: **0.738**
- Search latency: **~300ms**

**Conclusion**: Text-only search provides excellent results without VL enrichment.

---

## Services Required

### Must Be Running
1. Qdrant (port 6333) - Vector database
2. BGE-M3 Embeddings (port 8081) - Text embeddings
3. Qwen3-30B LLM (port 8080) - Query classification
4. Agent API (port 8000) - Agent orchestration

### NOT Required
- ~~Qwen2.5-VL (port 8083)~~ - VL service disabled

---

## Files Modified

- `services/vision/qwen2_vl_server.py` - Updated to use AutoModel (still crashes)
- `services/troubleshooting/vl_processor.py` - Added `enabled=False` default
- `docs/TROUBLESHOOTING_KB_COMPLETE.md` - Updated status

---

## Contact

For questions or issues, contact BestBox Development Team.

**Last Updated**: 2026-01-29
