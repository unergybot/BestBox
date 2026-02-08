# GLM-OCR Deployment and Testing Report

**Date:** 2026-02-07
**System:** BestBox (NVIDIA RTX 3080 + Tesla P100)
**Status:** ✅ Production Ready (Ollama), ⚠️ Advanced Features Blocked

---

## Executive Summary

Successfully deployed GLM-OCR vision-language model on RTX 3080 with full GPU acceleration. Resolved critical GPU configuration issues and validated performance across multiple document types. Advanced deployment methods (vLLM, transformers) blocked by bleeding-edge model requirements.

**Recommended Solution:** Ollama deployment (port 11434) for production use.

---

## Part 1: GPU Configuration Investigation

### Initial Problem
GLM-OCR service was loading 0 of 17 model layers to GPU, resulting in CPU-only inference and 120+ second timeouts.

### Root Cause Analysis
**Issue:** Docker container GPU device mapping conflict
```yaml
# Problem configuration in docker-compose.ocr.yml
glm-ocr-service:
  environment:
    - NVIDIA_VISIBLE_DEVICES=1      # Maps host GPU 1 → container GPU 0
    - CUDA_VISIBLE_DEVICES=1        # Override: tries to use container GPU 1 (doesn't exist!)
```

**Effect:** Ollama saw CUDA_VISIBLE_DEVICES=1 but container only has GPU 0, causing fallback to CPU.

### Solution Implemented
1. **Removed CUDA_VISIBLE_DEVICES override** from docker-compose.ocr.yml
2. **Cleaned up Dockerfile** - removed hardcoded GPU variables
3. **Added persistent volume mount** for model storage

```yaml
# Fixed configuration
glm-ocr-service:
  environment:
    - OLLAMA_HOST=0.0.0.0:11434
    - NVIDIA_VISIBLE_DEVICES=1      # Maps host GPU 1 → container GPU 0
    # CUDA_VISIBLE_DEVICES removed - auto-detects GPU 0 in container
  volumes:
    - ollama:/root/.ollama           # Persist model (2.2 GB)
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['1']        # RTX 3080 on host
            capabilities: [gpu]
```

### GPU Validation Results

**Model Loading:**
```
GPULayers: 17 [Layers: 17(0..16)] ✅
CUDA Device: NVIDIA GeForce RTX 3080 (compute 8.6) ✅
GPU Memory: 8.9 GB in use ✅
Backend: CUDA (Ollama version 0.15.5)
```

**Performance Improvement:**
- Before (CPU): 120+ seconds (timeout)
- After (GPU): 1.5-2 seconds per page
- **Improvement: ~60-80x faster**

---

## Part 2: Document Processing Tests

### Test Environment
- Model: glm-ocr:latest (2.2 GB, Ollama format)
- Device: RTX 3080 (12GB VRAM)
- Service: bestbox-glm-ocr (port 11434)
- Volume: /pixdata/docker-root/volumes/ollama/_data (persistent)

### Test Results

#### Test 1: StarRapid.pdf (Technical Diagram)
- **Type:** Technical CAD drawing with annotations
- **Time:** 27 seconds
- **Result:** ❌ Poor quality
- **Output:** "The text in the image is blurry and cannot be clearly visible."
- **Analysis:** Model not optimized for technical diagrams

#### Test 2: ppd407.pdf Page 1 (Cover Page)
- **Type:** Cover page with title text
- **Time:** 87 seconds (first load with model initialization)
- **Result:** ✅ Accurate
- **Output:**
  ```
  Injection molding
  Troubleshooting guide
  Eastman™ copolyesters
  ```
- **Analysis:** Correctly extracted minimal text

#### Test 3: ppd407.pdf Page 3 (Troubleshooting Table)
- **Type:** Two-column table with defect causes and solutions
- **Time:** 1.8 seconds
- **Result:** ✅ Excellent
- **Extracted:** 1,287 characters, 189 words, 39 lines
- **Quality:** Good structure preservation, all table content captured
- **Sample Output:**
  ```
  Black specks

  Possible cause
  Previous material(s) in the screw, check ring, hot runner, etc.

  Corrective action
  Purge machine with Eastman™ copolyesters or commercial purge compounds.
  If necessary, remove screw and manually clean the screw and barrel.
  ...
  ```

#### Test 4: ppd407.pdf Page 7 (Markdown Tables)
- **Type:** Multiple tables with headers and formatted cells
- **Time:** 1.6 seconds
- **Result:** ✅ Excellent
- **Extracted:** 910 characters, 160 words
- **Quality:** Perfect markdown table formatting with column alignment
- **Sample Output:**
  ```
  Gate blush

  | Possible cause | Corrective action |
  | :--- | :--- |
  | Fast injection speed | Use slower injection speed, especially at beginning of the shot. |
  | Gate design | Increase gate size. Change gate geometry... |
  ```

### Critical Finding: Image Detection Gap

**Pages 3 and 7 contained defect photographs** that GLM-OCR completely ignored:
- Page 3: Two defect images (black specks, brittleness)
- Page 7: Two defect images (gate blush, haziness)

**Impact:** For documents where images are essential to understanding, GLM-OCR alone is insufficient.

### Performance Summary

| Document Type | Speed | Text Quality | Image Detection |
|---------------|-------|--------------|-----------------|
| Technical diagrams | 27s | ❌ Poor | ❌ None |
| Cover pages | 87s* | ✅ Good | N/A |
| Tables | 1.5-2s | ✅ Excellent | ❌ None |
| Structured text | 1.5-2s | ✅ Good | ❌ None |

*First load includes 75.6s model initialization (one-time)

---

## Part 3: Advanced Deployment Attempts

### Objective
Deploy GLM-OCR with transformers/vLLM for:
1. Layout detection (PP-DocLayout-V3) - identify and extract image regions
2. Direct PDF input (2.8x faster: 1.86 pages/sec vs 0.67 for images)
3. Structured output with region metadata

### Attempt 1: vLLM Deployment

**Configuration:**
```yaml
glm-vllm-service:
  image: vllm/vllm-openai:v0.11.0
  command:
    - --model=zai-org/GLM-OCR
    - --trust-remote-code
```

**Result:** ❌ Failed

**Error:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ModelConfig
Value error, The checkpoint you are trying to load has model type `glm_ocr`
but Transformers does not recognize this architecture.
```

**Root Cause:** vLLM v0.11.0 uses transformers version that predates GLM-OCR support.

### Attempt 2: Transformers from Git

**Configuration:**
```dockerfile
RUN pip3 install git+https://github.com/huggingface/transformers.git
```

**Code:**
```python
from transformers import AutoProcessor, AutoModelForImageTextToText

processor = AutoProcessor.from_pretrained("zai-org/GLM-OCR", trust_remote_code=True)
model = AutoModelForImageTextToText.from_pretrained("zai-org/GLM-OCR", ...)
```

**Result:** ❌ Failed

**Error:**
```
ValueError: Unrecognized processing class in zai-org/GLM-OCR.
Can't instantiate a processor, a tokenizer, an image processor or
a feature extractor for this model.
```

**Root Cause:** GLM-OCR's custom processor not yet integrated into transformers main branch, even from git.

### Analysis

**GLM-OCR Model Status:**
- Released: Very recent (2026)
- Architecture: Custom CogViT encoder + GLM-0.5B decoder
- SDK: Separate `glmocr` package (not yet in transformers)
- Maturity: Bleeding-edge, not production-ready via standard tools

**Deployment Ecosystem Maturity:**
```
Ollama:        ✅ Works (simplified, limited features)
vLLM:          ❌ Transformers too old
Transformers:  ❌ Custom processor not integrated
Native SDK:    ⚠️  Requires custom installation (not tested)
```

---

## Part 4: Production Deployment Recommendation

### Deployed Solution: Ollama GLM-OCR

**Service Details:**
```
Container: bestbox-glm-ocr
Port: 11434
API: Ollama-compatible (generate, chat)
Model: glm-ocr:latest (2.2 GB)
Storage: ollama volume (persistent)
GPU: RTX 3080 (NVIDIA_VISIBLE_DEVICES=1 → container GPU 0)
```

**Capabilities:**
- ✅ Text extraction (excellent)
- ✅ Table recognition (excellent with structure)
- ✅ Markdown formatting
- ✅ GPU acceleration (all 17 layers)
- ✅ Fast inference (1.5-2s)
- ⚠️ Image detection (not exposed)
- ⚠️ Layout analysis (not available)
- ❌ Direct PDF input (requires conversion)

**Integration with Existing Pipeline:**

```
Document Input
    ↓
Docling Service (port 8085)
    ↓
Quality Gate Decision
    ↓
    ├─→ Text/Tables → GLM-OCR (port 11434) [RTX 3080]
    ├─→ Images/Complex → GOT-OCR2 (port 8084) [P100]
    └─→ Hybrid → Both services
```

### Multi-GPU OCR Strategy

**P100 (GPU 0): GOT-OCR2.0**
- Always-on classical OCR
- Strong for images, diagrams, complex layouts
- Port: 8084
- Use case: Technical documents, mixed content

**RTX 3080 (GPU 1): GLM-OCR**
- On-demand with GPU scheduling
- Excellent for tables, structured text
- Port: 11434
- Use case: Business documents, data extraction

**Mutual Exclusion:** GPU scheduler (port 8087) manages RTX 3080 contention between LLM and GLM-OCR.

---

## Part 5: Lessons Learned

### Technical Insights

1. **GPU Device Mapping in Docker:**
   - `NVIDIA_VISIBLE_DEVICES` controls which host GPUs are visible
   - `CUDA_VISIBLE_DEVICES` override can break container GPU numbering
   - Let CUDA auto-detect within container for simplicity

2. **Model Maturity Spectrum:**
   ```
   Production Ready:  Ollama (simplified, stable)
   Experimental:      vLLM (needs model support)
   Bleeding-edge:     Direct transformers (needs SDK integration)
   ```

3. **Vision-Language Model Trade-offs:**
   - Ollama: Easy deployment, limited features
   - Transformers: Full features, complex setup, unstable for new models
   - Native SDK: Maximum control, highest maintenance

### Best Practices

**When to Use Ollama:**
- ✅ Model officially supported in Ollama library
- ✅ Basic inference needs (text generation, chat)
- ✅ Rapid deployment priority
- ✅ Simplified operations

**When to Use Transformers/vLLM:**
- ✅ Need advanced features (layout detection, structured output)
- ✅ Model well-established in transformers
- ✅ Custom fine-tuning requirements
- ✅ Multi-model orchestration

**Red Flags for Advanced Deployment:**
- ❌ "Very new" model (< 6 months old)
- ❌ Custom architecture not in transformers
- ❌ Requires bleeding-edge git install
- ❌ SDK-specific features

---

## Part 6: Future Considerations

### Short-term (1-3 months)
- ✅ **Deploy Ollama solution** for production
- Monitor GLM-OCR SDK maturity
- Evaluate document quality with GOT-OCR2 fallback
- Implement usage analytics (which service for which doc types)

### Medium-term (3-6 months)
- Track transformers integration progress
- Revisit vLLM support as versions update
- Consider contributing GLM-OCR processor to transformers
- Evaluate alternative models if layout detection critical

### Long-term (6+ months)
- Full transformers deployment when stable
- Layout detection integration
- PDF direct input pipeline
- Multi-modal document understanding

### Technical Debt Identified

1. **GLM-OCR transformers service** (8.23 GB Docker image)
   - Currently non-functional but built
   - Action: Remove or document as experimental
   - Location: `bestbox-glm-transformers` container

2. **vLLM service definition** removed from docker-compose
   - Clean orphan container: `bestbox-glm-vllm`
   - Command: `docker compose --remove-orphans`

3. **Deprecation warnings**
   - FastAPI `on_event` → use lifespan handlers
   - Minor, non-blocking

---

## Appendix A: Configuration Files

### docker-compose.ocr.yml (Working Configuration)

```yaml
services:
  # P100: Classical OCR Service (GOT-OCR2.0)
  ocr-service:
    container_name: bestbox-ocr
    ports: ["8084:8084"]
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
      - CUDA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']  # P100

  # RTX 3080: OCR-VL Service (GLM-OCR via Ollama)
  glm-ocr-service:
    container_name: bestbox-glm-ocr
    ports: ["11434:11434"]
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
      - NVIDIA_VISIBLE_DEVICES=1
      - GPU_SCHEDULER_URL=http://gpu-scheduler:8086
    volumes:
      - ollama:/root/.ollama  # Persistent model storage
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']  # RTX 3080

volumes:
  ollama:
    external: true
```

---

## Appendix B: Performance Benchmarks

### GLM-OCR (Ollama) - RTX 3080

| Metric | Value |
|--------|-------|
| Model Size | 2.2 GB (GGUF quantized) |
| GPU Layers | 17/17 (100%) |
| GPU Memory | 8.9 GB / 12 GB |
| Startup Time | 75.6s (one-time) |
| Inference Time | 1.5-2s per page |
| Max Context | 4096 tokens |
| Batch Size | 512 |

### Model Specifications

```
Name: glm-ocr:latest
Architecture: CogViT + GLM-0.5B
Parameters: 0.9B (0.3B active - MoE-like)
Precision: Q4_K_M quantization
Backend: CUDA (via Ollama llama.cpp)
Format: GGUF
```

---

## Appendix C: API Examples

### Ollama API (Working)

**Text Recognition:**
```bash
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-ocr",
    "prompt": "Extract all text from this image, including tables.",
    "images": ["'"$(base64 -w 0 image.png)"'"],
    "stream": false,
    "options": {"temperature": 0}
  }'
```

**Response:**
```json
{
  "model": "glm-ocr",
  "created_at": "2026-02-07T...",
  "response": "Black specks\n\nPossible cause...",
  "done": true,
  "context": [...],
  "total_duration": 1794524998,
  "load_duration": 123456789,
  "prompt_eval_count": 245,
  "eval_count": 328
}
```

### Transformers API (Not Working - Reference Only)

```python
# This code does NOT work yet - reference for future
from transformers import AutoProcessor, AutoModelForImageTextToText

processor = AutoProcessor.from_pretrained("zai-org/GLM-OCR")
model = AutoModelForImageTextToText.from_pretrained(
    "zai-org/GLM-OCR",
    torch_dtype="auto",
    device_map="cuda:0"
)

messages = [{
    "role": "user",
    "content": [
        {"type": "image", "image": image},
        {"type": "text", "text": "Text Recognition:"}
    ]
}]

inputs = processor.apply_chat_template(messages, ...)
outputs = model.generate(**inputs, max_new_tokens=8192)
text = processor.decode(outputs[0], skip_special_tokens=True)
```

---

## Conclusion

**GLM-OCR deployment on RTX 3080 is production-ready via Ollama** with excellent performance for tables and structured documents. Advanced features (layout detection, PDF input) require model maturity in transformers ecosystem, estimated 3-6 months.

**Recommendation: Deploy Ollama solution immediately** and revisit advanced deployment in Q2 2026.

**Contact:** For questions or updates on GLM-OCR integration, refer to:
- Hugging Face: https://huggingface.co/zai-org/GLM-OCR
- GitHub: https://github.com/zai-org/GLM-OCR
- This deployment: BestBox/docker/docker-compose.ocr.yml

---

**Report prepared by:** Claude Sonnet 4.5
**Date:** 2026-02-07
**Version:** 1.0
