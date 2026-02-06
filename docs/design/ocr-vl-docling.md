Perfect — this is a **clean, production-grade split**. Below is a **step-by-step execution guide** you can drop straight into OpenCode / ops docs and start wiring today. I’ll keep it **actionable**, **GPU-aware**, and **failure-safe**.

---

# 🧭 OCR Execution Guidance (P100 + RTX 3080)

## 🎯 Objective

* **P100**: stable, always-on document ingestion (classical OCR)
* **RTX 3080**: high-accuracy OCR-VL (GLM-OCR), on-demand
* **Zero GPU contention**
* **No model eviction surprises**

---

## 🧩 Current GPU State (Baseline)

### 🟢 Tesla P100 (16GB)

```
Used: 11627 MiB / 16384 MiB
Running:
- Embedding
- Reranker
- ASR / TTS
OCR model: ❓ unknown
```

### 🟢 RTX 3080 (12GB)

```
Used: 4487 MiB / 12288 MiB
Running:
- Qwen2.5-14B-Q4 (resident LLM)
Free: ~7.8 GB
```

---

## 🧠 Strategy Summary (Final Decision)

| Task               | GPU      | Model                                    |
| ------------------ | -------- | ---------------------------------------- |
| Default OCR        | P100     | Docling + EasyOCR (or PaddleOCR classic) |
| Hard pages OCR     | RTX 3080 | **GLM-OCR (OCR-VL)**                     |
| LLM / RAG          | RTX 3080 | Qwen2.5-14B-Q4                           |
| Audio / embeddings | P100     | unchanged                                |

Key rule:

> **OCR-VL never runs concurrently with LLM inference**

---

## 🔄 Execution Flow (High Level)

```
PDF / Image
   ↓
[P100] Docling + Classical OCR
   ↓
Quality Check
   ├─ OK → store + embed
   └─ FAIL → escalate page
                ↓
           [RTX3080] GLM-OCR
                ↓
          replace page result
```

---

## 1️⃣ P100: Classical OCR Worker (Always On)

### ✅ What runs on P100

* Docling
* EasyOCR **OR** PaddleOCR (classic det+rec)
* PDF rasterization
* Layout normalization
* Chunking

### ⚠️ What must NOT run on P100

* OCR-VL
* VLMs
* Anything requiring Triton / BF16 / FlashAttention

---

### 📦 Environment (P100)

**CUDA / Torch**

* PyTorch 2.1.x
* CUDA 11.8
* FP32 only (no autocast)

**OCR Stack**

```bash
pip install docling easyocr
# or paddleocr (classic)
```

---

### 🧠 Docling Configuration (P100-Safe)

```python
opts.ocr.engine = "easyocr"
opts.ocr.use_gpu = True
opts.ocr.batch_size = 1
opts.ocr.lang = ["en", "ch_sim"]
```

**Important flags**

* ❌ no fp16
* ❌ no quantization
* DPI: **200–300 max**

---

### 🔍 Quality Gate (Critical)

After Docling output, compute **cheap signals**:

* empty text blocks?
* > 30% non-ASCII garbage?
* table rows collapsed?
* low OCR confidence (if available)

If **any fail → escalate page to OCR-VL**.

---

## 2️⃣ RTX 3080: OCR-VL Worker (On Demand)

### ✅ OCR-VL Choice

**zai-org / GLM-OCR**

Why:

* ~2.6 GB model size
* ~4–6 GB VRAM runtime
* Excellent doc layout + tables
* No FP8 / BF16 dependency
* Fits alongside Qwen *if serialized*

---

## 3️⃣ GPU Scheduling Rule (Very Important)

### 🚦 Mutual Exclusion

On RTX 3080:

* **Either** Qwen inference
* **Or** GLM-OCR
* **Never both at once**

Implement via:

* file lock
* Redis semaphore
* asyncio queue
* simple “one-job-at-a-time” worker

---

### 🧠 VRAM Math (Safe)

```
Qwen2.5-14B-Q4   ~4.5 GB
GLM-OCR          ~5.0 GB
------------------------
Peak             ~9.5 GB  ✅
```

---

## 4️⃣ GLM-OCR Execution (3080)

### Option A — **Ollama (Strongly Recommended)**

Easiest + safest VRAM handling.

```bash
ollama run glm-ocr "Text Recognition: ./page.png"
```

Benefits:

* automatic load / unload
* no CUDA code
* clean isolation from Qwen

---

### Option B — Python (Manual Control)

```python
from transformers import AutoProcessor, AutoModelForImageTextToText
import torch

processor = AutoProcessor.from_pretrained("zai-org/GLM-OCR")
model = AutoModelForImageTextToText.from_pretrained(
    "zai-org/GLM-OCR",
    torch_dtype=torch.float16
).to("cuda")

# run inference
# ...

del model
torch.cuda.empty_cache()
```

⚠️ **Always** delete model + clear cache after page batch.

---

## 5️⃣ Output Normalization

GLM-OCR output → normalize into same schema as Docling:

* Markdown
* block-level text
* table sections

Then:

* replace failed page result
* continue embedding / indexing

---

## 6️⃣ What About P100 OCR Models Already Loaded?

Since P100 is already at **~11.6 GB used**, assume:

* EasyOCR / PaddleOCR may already be in memory
* That’s OK

Just ensure:

* no OCR-VL
* no FP16 kernels
* no surprise PaddleOCR-VL auto-load

If unsure:

```bash
nvidia-smi -q -d PIDS
```

---

## 🧠 Final Recommended Defaults

### Default OCR Path (80–90% pages)

```
P100 → Docling + EasyOCR
```

### Escalation OCR Path (10–20% pages)

```
RTX 3080 → GLM-OCR
```

### Never Do

* OCR-VL on P100 ❌
* Run GLM-OCR + Qwen concurrently ❌
* Let OCR-VL stay resident ❌

---

## 🧾 TL;DR (Ops Cheat Sheet)

* P100 = **boring, stable ingestion**
* 3080 = **smart OCR-VL, on demand**
* GLM-OCR = best OCR-VL fit for your VRAM
* Serialize GPU jobs
* Escalate only hard pages

---

If you want next:

* 🔧 **sample code for OCR escalation logic**
* 📊 **confidence heuristics that actually work**
* 🧱 **Docker + GPU pinning layout**
* ⚡ **throughput benchmarks (pages/sec)**

Just tell me what to generate.
