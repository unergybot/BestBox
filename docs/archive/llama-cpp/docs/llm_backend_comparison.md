# LLM Backend Comparison: Native Vulkan vs Docker ROCm

## Quick Start

### Default: Native Vulkan (Recommended)
```bash
./scripts/start-llm.sh
```

### Alternative: Docker ROCm
```bash
./scripts/start-llm-docker.sh
```

## Comparison

| Feature | Native Vulkan | Docker ROCm |
|---------|---------------|-------------|
| **Script** | `start-llm.sh` | `start-llm-docker.sh` |
| **Backend** | Vulkan graphics API | HIP/ROCm compute |
| **Build time** | One-time compilation | 9min Docker build |
| **Startup time** | ~2-5 seconds | ~10-20 seconds |
| **Performance** | ✅ 527 tok/s prompt, 24 tok/s gen | ⚠️ Not benchmarked yet |
| **gfx1151 support** | ✅ Excellent | ✅ Good (with HSA_OVERRIDE) |
| **GPU layers** | 999 (unlimited) | 99 |
| **Flags** | `--no-direct-io --mmap` | `--no-direct-io --mmap` |
| **Port** | 8080 | 8080 |
| **Isolation** | ❌ Native process | ✅ Docker container |
| **Resource access** | Direct GPU | Device passthrough |

## When to Use Each

### Use Native Vulkan (start-llm.sh) if:
- ✅ You need maximum performance
- ✅ You want fast startup times
- ✅ Your system is stable
- ✅ You prefer simple deployment
- ✅ **RECOMMENDED FOR TESTING**

### Use Docker ROCm (start-llm-docker.sh) if:
- You need process isolation
- You're deploying to multiple machines
- You want reproducible environments
- You're debugging ROCm-specific issues

## Technical Details

### Native Vulkan Build
Located at: `third_party/llama.cpp/build/bin/llama-server`

Built with:
```cmake
-DGGML_VULKAN=1
```

### Docker ROCm Build
Image: `llama-strix`
Dockerfile: `third_party/llama.cpp/.devops/rocm.Dockerfile`

Built with:
```cmake
-DGGML_HIP=ON
-DAMDGPU_TARGETS="gfx1151;..."
```

## Troubleshooting

### Native Vulkan Issues
```bash
# Rebuild llama.cpp
cd third_party/llama.cpp
mkdir -p build && cd build
cmake .. -DGGML_VULKAN=1
cmake --build . --config Release
```

### Docker ROCm Issues
```bash
# Force rebuild image
docker rmi llama-strix
./scripts/start-llm-docker.sh

# Check logs
docker logs llm-server

# Check GPU access
docker exec llm-server rocm-smi
```

## Port Configuration

Both versions use **port 8080** to match service architecture:

```
LLM Server:    :8080  ← llama.cpp (both versions)
Embeddings:    :8081
Reranker:      :8082
Agent API:     :8000  ← Different service!
Frontend:      :3000
```

## Performance Benchmarking

To benchmark after switching backends:

```bash
# Start your chosen backend
./scripts/start-llm.sh  # or start-llm-docker.sh

# Wait for startup
sleep 10

# Run benchmark
cd third_party/llama.cpp
./build/bin/llama-bench \
  -m ~/models/14b/Qwen2.5-14B-Instruct-Q4_K_M.gguf \
  -p 512 -n 128

# Compare results
```

## Current Status

- ✅ Native Vulkan: Proven stable (527/24 tok/s)
- ⚠️ Docker ROCm: Built successfully, needs testing
- 📝 Both scripts available in `scripts/`
