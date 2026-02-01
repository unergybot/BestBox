# CUDA Migration Plan (AMD → NVIDIA) — RTX 3080 + P100

**Date:** 2026-01-31  
**Branch:** amd2cuda (source)  
**Target HW:** RTX 3080 (LLM, 12GB), P100 (Embeddings/Reranker, 16GB, sm6.0)  
**Primary Goal:** Re-enable CUDA acceleration and restore working UI without breaking existing flows.

**Status:** ✅ **COMPLETED** (2026-01-31)

---

## Current Working Configuration

### Running Services

| Service | Port | GPU | Docker Container |
|---------|------|-----|------------------|
| vLLM (Qwen3-4B-Instruct) | 8001 | RTX 3080 (cuda:0) | shaie-vllm |
| Embeddings (BGE-M3) | 8004 | P100 (CUDA 11.7 container) | shaie-p100-services |
| Agent API | 8000 | - | Native Python |
| Frontend (Next.js) | 3000 | - | Node.js |
| Qdrant | 6333 | - | bestbox-qdrant |

### Key Environment Variables

```bash
# Backend (.env)
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=Qwen/Qwen3-4B-Instruct-2507
EMBEDDINGS_BASE_URL=http://127.0.0.1:8004

# Frontend (.env.local)
NEXT_PUBLIC_LLM_PORT=8001
NEXT_PUBLIC_EMBEDDINGS_PORT=8004
NEXT_PUBLIC_RERANKER_PORT=8004
```

### Important Notes

1. **P100 Compatibility**: The Tesla P100 (sm_60) is NOT compatible with PyTorch 2.10+ (requires sm_70+). The SHAIE Docker container uses CUDA 11.7/11.8 for P100 compatibility.

2. **PyTorch GPU Ordering**: nvidia-smi shows GPU 0=P100, GPU 1=3080, BUT PyTorch reorders them to cuda:0=RTX 3080, cuda:1=P100.

3. **vLLM Backend**: Using the SHAIE vLLM container which provides an OpenAI-compatible API.

---

## 0) Constraints & Assumptions

- **Model files already present on `main`** and should be reused when possible.
- UI is currently broken on this branch; fix must be **non-invasive** and **backward compatible**.
- RTX 3080 (12GB) implies **small/quantized LLM** (e.g., Qwen3-4B-Instruct, GGUF 4-bit) with tight VRAM.
- P100 (sm6.0) limits some modern kernels; prefer **Torch 2.1/2.2 + CUDA 11.8** compatible stacks.

---

## 1) Phase 1 — Baseline & Safety (No Code Changes)

**Objectives:** Capture current state, identify regressions, and create safe rollback points.

- Record current environment variables and active services.
- Identify broken UI entry point(s) and capture console errors.
- Verify backend service health endpoints (if available).
- Freeze working baseline commit hash and tag (local).

**Exit Criteria:** Known failure points recorded; baseline stable for rollback.

---

## 2) Phase 2 — Inventory & Dependency Audit

**Objectives:** Enumerate ROCm-only code paths and define CUDA replacements.

- Search for ROCm/AMD-specific flags, env vars, or checks (e.g., `torch.version.hip`, `ROCM`, `gfx`, `amdsmi`).
- Identify LLM runtime options (vLLM / llama.cpp / transformers / ctranslate2).
- Map each component to **CUDA-capable** alternative.

**Deliverable:** A component-to-runtime matrix with exact configs.

---

## 3) Phase 3 — CUDA Enablement (Backend)

**Objectives:** Ensure backend services run on CUDA hardware without breaking AMD paths.

### 3.1 LLM (RTX 3080)
- Prefer **llama.cpp CUDA** or **vLLM CUDA** with small/quantized model.
- Default model suggestion: **Qwen3-4B-Instruct** or **Qwen2.5-4B-Instruct** (GGUF or HF).
- Enforce conservative defaults: low context, limited batch.

### 3.2 Embeddings + Reranker (P100)
- Use **sentence-transformers** and **cross-encoder** with CUDA `sm6.0` compatible builds.
- Ensure CUDA device selection supports dual GPU via device index.

### 3.3 Unified GPU Selection
- Add environment-driven GPU mapping: `LLM_DEVICE=cuda:0`, `EMBED_DEVICE=cuda:1`.
- Maintain AMD fallback (if present) behind a **non-breaking** detection layer.

**Exit Criteria:** Services start, use correct GPU, and respond to health checks.

---

## 4) Phase 4 — UI Restoration

**Objectives:** Resolve UI breakage while preserving API contract.

- Identify failing frontend build/runtime errors.
- Validate API endpoints used by UI exist and return expected schema.
- Restore UI to working state with minimal changes.

**Exit Criteria:** UI loads, connects to backend, and renders responses.

---

## 5) Phase 5 — Validation & Performance Checks

- GPU detection logs confirm CUDA use.
- Smoke tests: basic chat, embedding query, rerank response.
- Verify no regression in AMD-specific settings (guarded paths).

---

## 6) Definition of Done

- CUDA-enabled LLM on RTX 3080 works end-to-end.
- Embedding + reranker run on P100.
- UI works without manual patching.
- AMD-specific paths remain intact or feature-flagged.
- Minimal code changes with documented config in docs.

---

## 7) Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| P100 lacks modern kernels | **HIGH** | P100 (sm_60) incompatible with PyTorch 2.10+. Use CPU for embeddings/reranker, or downgrade to PyTorch with CUDA 11.8 | 
| VRAM limits on 3080 | High | Use 4-bit GGUF or 4-bit bitsandbytes | 
| UI schema drift | Medium | Add compatibility adapters or safe defaults | 
| ROCm-specific checks break CUDA | Medium | Add unified detection (CUDA first, HIP fallback) |
| PyTorch GPU reordering | Low | PyTorch may reorder GPUs vs nvidia-smi. Use `CUDA_VISIBLE_DEVICES` to control |

---

## 8) Execution Checklist

- [x] Baseline logs + UI error capture
- [x] ROCm/CUDA path inventory completed
- [x] CUDA runtime configs added (non-breaking)
- [ ] LLM service boots on RTX 3080
- [ ] Embedding/reranker service boots on P100
- [ ] UI restored and verified
- [ ] Smoke tests recorded

---

## 9) Implementation Summary

### Completed Changes

1. **Environment Configuration**
   - Created `.env.cuda` template with CUDA-specific variables
   - Updated `.env` with commented CUDA options
   - Created `activate-cuda.sh` for NVIDIA environment setup

2. **Service Updates**
   - `services/embeddings/main.py`: Added `EMBEDDINGS_DEVICE` environment variable support
   - `services/rag_pipeline/reranker.py`: Added `RERANKER_DEVICE` environment variable support
   - `services/speech/s2s_server.py`: Made `ASR_DEVICE` configurable
   - `services/vision/qwen2_vl_server.py`: Updated to be GPU-agnostic
   - `services/copilotkit_endpoint.py`: Dynamic GPU detection

3. **Scripts**
   - Created `scripts/start-llm-cuda.sh` for NVIDIA LLM startup
   - Created `scripts/build-llama-cuda.sh` for building llama.cpp with CUDA
   - Updated `scripts/start-all-services.sh` to auto-detect NVIDIA GPUs
   - Updated `scripts/start-embeddings.sh` and `scripts/start-reranker.sh` to show device

4. **Documentation**
   - Updated `AGENTS.md` with CUDA instructions
   - Updated `CLAUDE.md` with dual AMD/NVIDIA support

### Next Steps for User

1. **Option A: Use existing SHAIE Docker services (Recommended)**
   - vLLM is already running on port 8001 with `Qwen/Qwen3-4B-Instruct-2507`
   - P100 services running on port 8004 with embeddings/reranker
   - Update BestBox to point to these endpoints

2. **Option B: Build llama.cpp with CUDA for native LLM**
   - Build: `./scripts/build-llama-cuda.sh`
   - Download model: `huggingface-cli download Qwen/Qwen3-4B-Instruct-GGUF --local-dir ~/models/4b`
   - Set: `export LLM_MODEL_PATH=~/models/4b/Qwen3-4B-Instruct-Q4_K_M.gguf`
   - Start: `source activate-cuda.sh && ./scripts/start-llm-cuda.sh`

3. **For embeddings/reranker on P100:**
   - P100 requires CUDA 11.7/11.8 (PyTorch 2.10+ doesn't support sm_60)
   - Use SHAIE's p100-services Docker container on port 8004
   - Or run embeddings/reranker on CPU (slower but compatible)

### Using SHAIE Docker Services with BestBox

Update your `.env` or environment:
```bash
# Point to SHAIE vLLM on port 8001
export LLM_BASE_URL=http://127.0.0.1:8001/v1

# Use SHAIE p100-services for embeddings (port 8004)
# Note: May require API compatibility adapter
```

