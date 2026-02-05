# Mold Knowledge Base Strategy

**Date**: 2026-02-05  
**Version**: 1.0  
**Status**: Design Proposal

---

## Executive Summary

This document outlines a comprehensive strategy for enhancing the BestBox mold troubleshooting knowledge base by:
1. Leveraging public injection molding knowledge resources
2. Optimizing document organization for bulk uploads
3. Creating a unified, multi-source knowledge system

---

## Current State

### Existing Customer KB (`TROUBLESHOOTING_KB_COMPLETE.md`)
- ✅ Excel extraction pipeline (1000+ customer files)
- ✅ Dual-level Qdrant indexing (cases + issues)
- ✅ Semantic search with BGE-M3 embeddings
- ✅ Mold Service Agent integrated
- ⚠️ Vision-Language processing disabled (ROCm issues)

### Current Data Model
| Collection | Description | Vector Dim |
|------------|-------------|------------|
| `troubleshooting_cases` | Case-level search | 1024 |
| `troubleshooting_issues` | Issue-level search | 1024 |

---

## Phase 1: Public Knowledge Integration

### Recommended Public Sources

| Category | Source | Format | Value |
|----------|--------|--------|-------|
| **Defect Reference** | ICOMold KB | Web/PDF | Design guides, common mistakes |
| **Troubleshooting** | RJG Inc Guides | PDF | 9+ defect solutions |
| **Materials** | Basilius Guide | PDF | Material properties database |
| **Process Optimization** | Eastman Troubleshooting | PDF | Scientific root cause analysis |
| **Knowledge Graph** | MDPI Research | Paper | Defect-cause-solution relationships |

### New Collection: `mold_reference_kb`
```
Purpose: Store curated public knowledge as baseline reference
Schema:
  - source: str (e.g., "icomold", "rjg", "mdpi")
  - category: enum [defect, material, process, design, equipment]
  - topic: str (e.g., "short_shot", "warping", "flash")
  - content: str (main knowledge content)
  - causes: list[str]
  - solutions: list[str]
  - related_defects: list[str]
  - confidence: float (0-1, sourced vs inferred)
```

### Integration Architecture
```
┌────────────────────────────────────────────────────────────────┐
│                    HYBRID KNOWLEDGE BASE                        │
├─────────────────────┬──────────────────────────────────────────┤
│  PUBLIC REFERENCE   │         CUSTOMER EXPERIENCE               │
│  (mold_reference_kb)│  (troubleshooting_cases/issues)           │
├─────────────────────┼──────────────────────────────────────────┤
│ - Defect definitions│ - Real production cases                   │
│ - Standard causes   │ - Trial results (T1/T2 outcomes)          │
│ - Best practices    │ - Equipment-specific solutions            │
│ - Material guides   │ - Image evidence                          │
│ - Process params    │ - Part/material mappings                  │
└─────────────────────┴──────────────────────────────────────────┘
                              ↓
              ┌───────────────────────────────────┐
              │       Unified Search Router        │
              │  (Merges results with confidence)  │
              └───────────────────────────────────┘
```

---

## Phase 2: Document Organization Strategy

### Directory Structure
```
data/mold_knowledge/
├── raw/
│   ├── customer_excel/         # Original 1000+ Excel files
│   ├── public_pdfs/            # Downloaded public guides
│   ├── public_web/             # Scraped web content (JSON)
│   └── internal_docs/          # Other internal documents
│
├── processed/
│   ├── troubleshooting/        # Existing: customer case JSONs
│   ├── reference/              # NEW: public knowledge chunks
│   │   ├── defects/
│   │   ├── materials/
│   │   ├── processes/
│   │   └── equipment/
│   └── images/                 # All extracted images
│
├── staging/                    # For bulk upload queue
│   ├── pending/
│   ├── in_progress/
│   └── failed/
│
└── metadata/
    ├── sources.json            # Track all source origins
    ├── ingestion_log.jsonl     # Processing history
    └── quality_scores.json     # Content quality metrics
```

### Document Upload Workflow
```
┌──────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────┐
│  Upload  │ -> │  Validate   │ -> │   Process   │ -> │  Index  │
│  (API)   │    │  & Classify │    │  & Chunk    │    │ (Qdrant)│
└──────────┘    └─────────────┘    └─────────────┘    └─────────┘
      ↓                ↓                  ↓                ↓
   staging/        Detect type:       Chunking:         Store in:
   pending/        - Excel→Customer   - 512-1024 tokens - cases
                   - PDF→Reference    - 100-200 overlap - issues
                   - Web→Reference    - Semantic split  - reference
```

### Chunking Strategy (RAG Best Practices)
| Document Type | Chunk Size | Overlap | Strategy |
|---------------|------------|---------|----------|
| Customer Excel | Row-based | N/A | One issue per chunk |
| Public PDFs | 512 tokens | 128 | Semantic paragraph split |
| Web scraped | 400 tokens | 100 | Section-based split |
| Technical tables | Row+context | N/A | Table-aware parsing |

---

## Phase 2.5: Document Processing Tools (Docling + OCR + VL)

### Recommendation: Docling CUDA on P100 ✅

**Docling is already integrated** in `services/rag_pipeline/ingest.py`. We recommend enhancing it with:

| Feature | Current State | Recommended Enhancement |
|---------|---------------|-------------------------|
| Document Parsing | ✅ Basic PDF/DOCX | Add PPTX, images, table extraction |
| CUDA Acceleration | ❌ Not enabled | Enable for P100 (16GB VRAM) |
| OCR | ❌ Not enabled | Add EasyOCR for Chinese text |
| Image Extraction | ❌ Not enabled | Extract + VL description |

### Docling CUDA Setup for P100

```bash
# Install Docling with CUDA support
pip install 'docling[cuda]'

# Verify CUDA detection
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0)}')"
```

**P100 GPU Memory Allocation:**
```
┌───────────────────────────────────────────────────────────────┐
│ P100 GPU (16GB VRAM)                                          │
├───────────────────────────────────────────────────────────────┤
│ Docling Layout Model:     ~2GB                                │
│ EasyOCR (Chinese):        ~3GB                                │
│ Reserved for processing:  ~6GB                                │
│ Available:                ~5GB buffer                         │
└───────────────────────────────────────────────────────────────┘
```

### OCR Strategy for Mold Documents (P100 GPU / CUDA 11.8)

We evaluated Hugging Face models (`GLM-OCR`, `GOT-OCR2.0`, `DeepSeek-VL`) for P100 compatibility (Pascal architecture).

#### 1. Primary Recommendation: GOT-OCR2.0 (stepfun-ai/GOT-OCR2_0) ✅
- **Why**: "General OCR Theory" model designed for unified OCR.
- **Size**: ~580M parameters (Very lightweight).
- **VRAM**: <2GB (Excellent for P100 16GB).
- **Compatibility**: Supports CUDA 11.8. No hard Flash Attention 2 requirement (runs on Pascal).
- **Capabilities**: Strong Chinese/English, formatting preservation, markdown output.

```bash
pip install transformers verovio
```

#### 2. Alternative: PaddleOCR v4 (Robust)
- **Why**: Industry standard, battle-tested for complex manufacturing tables.
- **Compatibility**: Excellent CUDA 11.8 support.
- **Size**: Lightweight (~200MB).

#### 3. Note on GLM-OCR (zai-org/GLM-OCR)
- **Status**: ⚠️ **Caution**
- **Risk**: While small (0.9B), many modern VLM implementations require **Flash Attention 2**, which is NOT supported on P100 (Pascal). Requires verifying if a non-Flash Attention fallback exists in `vllm`.

**Selected Pipeline for P100:**
1. **Docling** (Parse structure)
2. **GOT-OCR2.0** (Text/Table extraction)
3. **Qwen-VL** (Defect classification - *Future when ROCm/Pascal supported*)

### OCR Implementation Code (GOT-OCR2.0)

```python
from transformers import AutoModel, AutoTokenizer

class MoldOCR:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained('stepfun-ai/GOT-OCR2_0', trust_remote_code=True)
        self.model = AutoModel.from_pretrained(
            'stepfun-ai/GOT-OCR2_0', 
            trust_remote_code=True, 
            low_cpu_mem_usage=True, 
            device_map='cuda', 
            use_safetensors=True
        )
        self.model = self.model.eval().cuda()

    def extract(self, image_path):
        res = self.model.chat(self.tokenizer, image_path, ocr_type='ocr')
        return res
```

### Image Processing Pipeline for Mold Documents

```
┌─────────────────────────────────────────────────────────────────┐
│                 MOLD DOCUMENT IMAGE PIPELINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. EXTRACTION (Docling)                                         │
│     ├── PDF embedded images → extract to files                   │
│     ├── PowerPoint slides → slide images + embedded images       │
│     └── Excel embedded images → already handled by Excel extractor│
│                                                                  │
│  2. CLASSIFICATION                                               │
│     ├── Defect photo → Route to VL Model for defect description  │
│     ├── Diagram/flowchart → OCR + VL for process understanding   │
│     ├── Screenshot → OCR for text extraction                     │
│     └── Logo/header → Skip (no semantic value)                   │
│                                                                  │
│  3. PROCESSING                                                   │
│     ├── OCR: Extract text annotations (EasyOCR Chinese)          │
│     ├── VL: Generate defect description (Qwen-VL when available) │
│     └── Embedding: Add image description to issue embedding      │
│                                                                  │
│  4. STORAGE                                                      │
│     ├── Original image → data/mold_knowledge/processed/images/   │
│     ├── OCR text → Stored in issue metadata.text_in_image        │
│     └── VL description → Stored in issue metadata.vl_description │
└─────────────────────────────────────────────────────────────────┘
```

### Enhanced DocumentIngester for Mold KB

```python
# services/rag_pipeline/mold_ingest.py
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption
import easyocr

class MoldDocumentIngester:
    """Enhanced ingester with CUDA, OCR, and image extraction for mold documents."""
    
    def __init__(self, use_cuda: bool = True):
        # Configure Docling with CUDA acceleration
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True  # Preserve tables
        
        self.converter = DocumentConverter(
            format_options={
                PdfFormatOption.PIPELINE: pipeline_options
            }
        )
        
        # Initialize OCR for Chinese manufacturing annotations
        self.ocr_reader = easyocr.Reader(
            ['ch_sim', 'en'], 
            gpu=use_cuda,
            model_storage_directory='/home/apexai/BestBox/models/easyocr'
        )
        
        # VL processor (optional, when enabled)
        self.vl_enabled = os.environ.get('VL_ENABLED', 'false').lower() == 'true'
    
    async def ingest_with_images(self, doc_path: Path) -> dict:
        """Ingest document with full image processing."""
        result = self.converter.convert(str(doc_path))
        
        # Extract images
        images = self._extract_images(result, doc_path)
        
        # Process each image
        processed_images = []
        for img_info in images:
            img_result = {
                "path": img_info["path"],
                "page": img_info.get("page"),
            }
            
            # OCR for text annotations
            if img_info.get("has_text", False):
                ocr_result = self.ocr_reader.readtext(str(img_info["path"]))
                img_result["ocr_text"] = " ".join([text for _, text, _ in ocr_result])
            
            # VL description (if enabled)
            if self.vl_enabled:
                img_result["vl_description"] = await self._get_vl_description(img_info["path"])
            
            processed_images.append(img_result)
        
        return {
            "text": result.document.export_to_markdown(),
            "tables": self._extract_tables(result),
            "images": processed_images,
            "metadata": {...}
        }
```

### VL Integration for Mold Defect Images

When the VL service becomes available (Qwen-VL on ROCm or alternative):

```python
# Prompt for mold defect image analysis
VL_MOLD_PROMPT = """
Analyze this manufacturing mold/product image. Identify:
1. Defect type (披锋/flash, 缩水/sink mark, 熔接线/weld line, etc.)
2. Defect location (edge, surface, gate area, etc.)
3. Severity (minor, moderate, severe)
4. Visual annotations (circles, arrows, text markings)
5. Any Chinese text visible in the image

Output in JSON format:
{
    "defect_type": "...",
    "defect_type_en": "...",
    "location": "...",
    "severity": "...",
    "annotations": [...],
    "visible_text": "..."
}
"""
```

### Comparison: OCR vs VL for Mold Images

| Use Case | OCR (EasyOCR) | VL (Qwen-VL) |
|----------|---------------|--------------|
| Extract text annotations | ✅ Best choice | ❌ Overkill |
| Identify defect type | ❌ Not applicable | ✅ Required |
| Understand diagram | ⚠️ Text only | ✅ Full context |
| Process speed | ~1s/image | ~5-10s/image |
| GPU memory | ~3GB | ~8-16GB |

**Recommendation:** Use **OCR for all images** (fast, reliable text extraction) + **VL for defect classification** (when VL service is available). This hybrid approach maximizes accuracy while managing GPU resources.

---

## Phase 3: Bulk Upload System

### API Endpoints
```python
# New endpoints for document management
POST /api/kb/upload
  - Single file upload with auto-classification
  - Returns: {doc_id, status, processing_eta}

POST /api/kb/bulk-upload
  - Directory path or archive upload
  - Async processing with progress tracking
  - Returns: {batch_id, total_files, status}

GET /api/kb/upload-status/{batch_id}
  - Check batch processing status
  - Returns: {processed, failed, pending, errors[]}

POST /api/kb/ingest-public
  - Crawl and ingest public resources
  - Params: {sources: ["icomold", "rjg", ...], categories: [...]}
```

### Ingestion Pipeline Enhancement
```python
class UnifiedKBIngester:
    """Unified ingestion for all document types"""
    
    async def ingest(self, path: Path, source_type: str = "auto"):
        # 1. Auto-detect document type
        doc_type = await self.classify_document(path)
        
        # 2. Route to appropriate processor
        if doc_type == "customer_excel":
            return await self.excel_extractor.process(path)
        elif doc_type == "public_pdf":
            return await self.pdf_processor.process(path)
        elif doc_type == "web_content":
            return await self.web_processor.process(path)
        
        # 3. Generate embeddings
        embeddings = await self.embedder.embed(chunks)
        
        # 4. Index to appropriate collection
        await self.indexer.index(embeddings, collection=self.get_collection(doc_type))
        
        # 5. Log ingestion
        await self.logger.log(path, status="success", chunks=len(chunks))
```

---

## Phase 4: Search Enhancement

### Unified Search Tool
```python
@tool
def search_mold_knowledge(
    query: str,
    sources: list[str] = ["customer", "reference"],  # NEW: multi-source
    top_k: int = 5,
    defect_type: Optional[str] = None,
    material: Optional[str] = None,
    include_public: bool = True  # NEW: include reference KB
) -> str:
    """Search across customer cases AND public reference knowledge"""
```

### Search Result Merger
```
Customer Results (weight=0.7)     Reference Results (weight=0.3)
┌──────────────────────────┐     ┌──────────────────────────┐
│ Case: TS-1947688-001     │     │ Source: RJG Inc          │
│ Problem: 产品披锋         │     │ Defect: Flash            │
│ Solution: 调整锁模力      │     │ Cause: Low clamp force   │
│ Result: T2-OK ✓          │     │ Solution: Increase clamp │
│ Evidence: 2 images       │     │ Confidence: 0.95         │
└──────────────────────────┘     └──────────────────────────┘
                    ↓
           ┌────────────────────────────────────────┐
           │        Merged Response                  │
           │ 1. Customer proven solution (T2-OK)     │
           │ 2. Reference confirms: standard cause   │
           │ 3. Additional tips from best practices  │
           └────────────────────────────────────────┘
```

---

## Implementation Plan

### Week 1: Public Knowledge Ingestion
- [ ] Create web scraper for top 5 public sources
- [ ] Implement PDF text extraction with chunking
- [ ] Create `mold_reference_kb` Qdrant collection
- [ ] Index initial reference content

### Week 2: Upload System
- [ ] Implement staging directory workflow
- [ ] Create bulk upload API endpoints
- [ ] Add document classification logic
- [ ] Implement progress tracking

### Week 3: Search Enhancement
- [ ] Extend search tool for multi-source queries
- [ ] Implement result merger with confidence weighting
- [ ] Update Mold Agent prompts for hybrid responses
- [ ] Add source attribution to responses

### Week 4: Quality & Monitoring
- [ ] Implement content quality scoring
- [ ] Add duplicate detection
- [ ] Create ingestion dashboard
- [ ] Document API usage

---

## Verification Plan

### Automated Tests
```bash
# Existing tests
pytest services/troubleshooting/test_*.py

# New tests to add
pytest services/troubleshooting/test_reference_kb.py
pytest services/troubleshooting/test_bulk_upload.py
pytest services/troubleshooting/test_unified_search.py
```

### Manual Verification
1. **Public ingestion**: Verify 5 sources ingested correctly
2. **Bulk upload**: Test 100-file batch upload
3. **Search quality**: Compare results with/without reference KB
4. **Agent responses**: Verify hybrid answers include attribution

---

## Resource Estimates

| Component | GPU Memory | Disk Space | Processing Time |
|-----------|------------|------------|-----------------|
| Reference KB | +0 (shared embeddings) | ~2GB | 4 hours initial |
| Bulk Upload Queue | +0 | ~1GB staging | Real-time |
| Unified Search | +0 | +0 | <500ms P95 |

**Total Additional**: ~3GB disk, no GPU increase

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Public content licensing | Legal/compliance | Only use openly published guides |
| Quality variance in public data | Lower search accuracy | Confidence scoring + human review |
| Duplicate entries across sources | Index bloat | Deduplication pipeline |
| Bulk upload failures | Data loss | Checkpoint/resume + failed queue |

---

## Next Steps

1. **Approve design** - Review this document
2. **Phase 1 POC** - Ingest top 3 public sources as proof of concept
3. **Iterate** - Refine based on search quality metrics

---

*Contact*: BestBox Development Team  
*Last Updated*: 2026-02-05
