# Docker/ROCm llama.cpp Test Results

**Date**: 2026-01-24
**Hardware**: AMD Ryzen AI Max+ 395 (Strix Halo, gfx1151)
**Model**: Qwen2.5-14B-Instruct-Q4_K_M.gguf (8.4GB)
**Docker Image**: llama-strix (llama.cpp with HIP/ROCm)

## Executive Summary

✅ **Docker/ROCm backend is FUNCTIONAL** with correct HSA override
⚠️ **Native Vulkan is 2x faster** for prompt processing
📊 **Generation speed is identical** (~24 tok/s)

## Critical Configuration

### What Works
```bash
HSA_OVERRIDE_GFX_VERSION=11.0.0
```

### What Crashes
```bash
HSA_OVERRIDE_GFX_VERSION=11.5.0
# Error: "ROCm error: invalid device function"
# Exit code: 139 (segmentation fault)
```

## Performance Comparison

| Metric | Native Vulkan | Docker/ROCm | Winner |
|--------|---------------|-------------|--------|
| Prompt processing | 527 tok/s | 216-295 tok/s | **Vulkan (2x faster)** |
| Generation | 24 tok/s | 23-36 tok/s | Tie |
| GPU offload | 49/49 layers | 49/49 layers | Same |
| VRAM usage | - | 8.1 GB | - |
| KV cache | - | 768 MB | - |

## Test Commands

### Successful Docker Launch
```bash
docker run -d --name llm-server-test \
  --device /dev/kfd \
  --device /dev/dri \
  --group-add video \
  -e HSA_OVERRIDE_GFX_VERSION=11.0.0 \
  -v ~/models/14b:/app/models \
  -p 8080:8080 \
  llama-strix \
  --model /app/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  --n-gpu-layers 99 \
  --ctx-size 4096 \
  --no-direct-io \
  --mmap
```

### Verification
```bash
# Health check
curl http://localhost:8080/health
# Expected: {"status":"ok"}

# Inference test
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "max_tokens": 10
  }'
```

## Sample Output

### Test 1: Simple Math
- **Prompt**: "What is 2+2? Answer in one word."
- **Response**: "Four"
- **Time**: 0.203s
- **Metrics**: 295 tok/s prompt, 36 tok/s generation

### Test 2: Longer Generation
- **Prompt**: "Explain why the sky is blue in exactly 50 words."
- **Response**: Correct 64-token scientific explanation
- **Metrics**: 216 tok/s prompt, 23 tok/s generation

## Detailed Logs

### Successful Startup (HSA 11.0.0)
```
load_tensors: offloaded 49/49 layers to GPU
load_tensors:   CPU_Mapped model buffer size =   417.66 MiB
load_tensors:        ROCm0 model buffer size =  8148.38 MiB
llama_kv_cache:      ROCm0 KV buffer size =   768.00 MiB
llama_context: Flash Attention was auto, set to enabled
common_init_from_params: warming up the model with an empty run
[warmup completes successfully]
main: model loaded
main: server is listening on http://0.0.0.0:8080
```

### Failed Startup (HSA 11.5.0)
```
load_tensors: offloaded 49/49 layers to GPU
[initialization succeeds...]
common_init_from_params: warming up the model with an empty run
/app/ggml/src/ggml-cuda/ggml-cuda.cu:96: ROCm error
ggml_cuda_compute_forward: MUL_MAT failed
ROCm error: invalid device function
[container crashes with exit code 139]
```

## Recommendations

### For BestBox Production
**Continue using native Vulkan**:
- 2x faster prompt processing (527 vs 216-295 tok/s)
- Already proven stable
- No container overhead
- Simpler deployment

### When to Use Docker/ROCm
- Containerization is mandatory (K8s deployments)
- Development/testing isolation
- Future fallback if Vulkan has issues
- Acceptable trade-off: 2x slower prompts, same generation speed

## Next Steps (If Pursuing Dual-Model)

If you decide to implement the dual-model architecture:

1. Download 7B model (5.5GB): `Qwen2.5-7B-Instruct-Q4_K_M.gguf`
2. Run 7B in Docker/ROCm on port 8081 for fast routing
3. Keep 14B in native Vulkan on port 8080 for complex tasks
4. Implement router logic in `agents/utils.py`

**Estimated complexity**: Medium (router code + orchestration)
**Estimated benefit**: Faster routing responses (2-3x speedup for simple queries)

## Files Referenced
- `/home/unergy/models/14b/Qwen2.5-14B-Instruct-Q4_K_M.gguf`
- Docker image: `llama-strix`
- Native Vulkan startup: `scripts/start-llm.sh`

## Environment
- ROCm: 7.2.0
- llama.cpp: Built with `-DGGML_HIP=ON`
- Kernel: Linux 6.14.0-37-generic
- Driver: amdgpu (gfx1151 architecture)
