# Vulkan Backend Validation Report

**Date**: January 23, 2026  
**Status**: ✅ VALIDATED

---

## Summary

The Vulkan backend for llama.cpp has been successfully validated on AMD Radeon 8060S (gfx1151). This resolves the ROCm/HIP crash issue documented in `LLM_BACKEND_STATUS.md`.

## Benchmark Results

| Metric | Vulkan | CPU | Improvement |
|--------|--------|-----|-------------|
| **pp512 (prompt)** | 526.66 tok/s | ~78 tok/s | **6.7x faster** |
| **tg128 (generation)** | 23.92 tok/s | ~9.6 tok/s | **2.5x faster** |

## Configuration

### Build Details
- **Source**: `/home/unergy/BestBox/third_party/llama.cpp`
- **Commit**: 3003c82f (build 7725)
- **CMake Config**: `GGML_VULKAN=ON`, `GGML_HIP=OFF`, `GGML_CUDA=OFF`

### GPU Detection
```
ggml_vulkan: Found 1 Vulkan devices:
ggml_vulkan: 0 = AMD Radeon 8060S (RADV GFX1151) (radv)
             | uma: 1 | fp16: 1 | bf16: 0
             | warp size: 64 | shared memory: 65536
             | int dot: 0 | matrix cores: KHR_coopmat
```

### Required Flags (Critical)
The gfx1151 architecture requires special loading flags to avoid "unexpectedly reached end of file" errors:

```bash
--no-direct-io --mmap
```

Without these flags, model loading fails despite the file being valid.

## Startup Command

```bash
./scripts/start-llm.sh
```

Or manually:

```bash
/home/unergy/BestBox/third_party/llama.cpp/build/bin/llama-server \
  -m ~/models/14b/Qwen2.5-14B-Instruct-Q4_K_M.gguf \
  --port 8080 \
  --host 127.0.0.1 \
  -c 4096 \
  --n-gpu-layers 999 \
  --no-direct-io \
  --mmap
```

## API Endpoints

| Endpoint | URL |
|----------|-----|
| Chat Completions | `http://127.0.0.1:8080/v1/chat/completions` |
| Health Check | `http://127.0.0.1:8080/health` |
| Models List | `http://127.0.0.1:8080/v1/models` |

## Test Command

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-14b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }' | jq .
```

## Performance Notes

- **pp512**: 526 tok/s is good for prompt processing
- **tg128**: 24 tok/s is acceptable for interactive chat
- The community benchmark of ~880 tok/s may have used different settings, larger batch sizes, or RADV driver optimizations

## Next Steps

1. ✅ Vulkan backend validated
2. ⏳ Update CopilotKit to use Vulkan endpoint
3. ⏳ Deploy embeddings service (BGE-M3)
4. ⏳ Set up Docker infrastructure (Qdrant, PostgreSQL, Redis)
5. ⏳ Implement LangGraph agent framework

---

**Files Created**:
- `scripts/start-llm.sh` - Startup script with correct flags
- `docs/VULKAN_VALIDATION_REPORT.md` - This report
