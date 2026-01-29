# vLLM AMD Official Documentation Analysis

**Source:** https://rocm.docs.amd.com/en/latest/how-to/rocm-for-ai/inference/benchmark-docker/vllm.html

---

## 🚨 Critical Finding: Hardware Support Gap

### Officially Supported GPUs
AMD's vLLM documentation lists **only datacenter Instinct GPUs:**
- MI355X
- MI350X
- MI325X
- MI300X

### Your Hardware (NOT Listed)
- **Ryzen AI Max+ 395** (gfx1151, RDNA 3.5 architecture)
- **Radeon 8060S iGPU** (consumer/mobile GPU)

**Conclusion:** Your hardware is **NOT officially supported** by AMD's vLLM ROCm build. This explains the slow performance (6.4 tok/s vs expected 20-30+ tok/s).

---

## Configuration Differences

### AMD Official Recommendations vs Your Setup

| Parameter | AMD Official | Your Setup | Impact |
|-----------|-------------|------------|--------|
| **Supported GPU** | MI300X series | gfx1151 (RDNA 3.5) | ❌ Major - unsupported arch |
| **--shm-size** | 16G | Not set (64MB default) | ⚠️ High - limits IPC |
| **--gpu-memory-utilization** | 0.9 | 0.92 | ✅ Minor - similar |
| **--max-num-batched-tokens** | 131,072 | 8,192 | ⚠️ Medium - limits batching |
| **--swap-space** | 16 | 16 | ✅ Same |
| **kv_cache_dtype** | auto/fp8 | Not set (auto) | ✅ OK |
| **--max-num-seqs** | 1024 | Not set (256 default) | ⚠️ Limits concurrent requests |

---

## Missing Configuration

### 1. Shared Memory Size ⚠️
AMD docs specify `--shm-size 16G` but Docker default is only **64MB**.

**Impact:** Severe IPC bottleneck for multi-process inference

**Fix:**
```bash
docker run -d \
  --shm-size 16G \  # ADD THIS
  ...
```

### 2. Batching Configuration ⚠️
AMD uses much larger batch sizes for throughput:
- `--max-num-batched-tokens 131072` (vs our 8192)
- `--max-num-seqs 1024` (vs default 256)

**Impact:** Lower throughput on concurrent requests

### 3. Environment Variables
AMD recommends:
```bash
--env HUGGINGFACE_HUB_CACHE=/workspace
```

---

## Why Performance is Slow

### Root Cause Analysis

1. **Unsupported Architecture (PRIMARY)**
   - vLLM ROCm builds target **CDNA** (MI300X)
   - Your GPU is **RDNA 3.5** (gfx1151)
   - Different instruction sets, memory hierarchy, compute units
   - Kernels not optimized for consumer GPUs

2. **Missing Shared Memory (SECONDARY)**
   - 64MB default vs 16GB recommended
   - Causes memory thrashing for multi-process workers

3. **Conservative Batching (MINOR)**
   - Smaller batch sizes reduce parallel efficiency
   - Less important for single-user scenarios

---

## Performance Expectations by Hardware

### AMD Instinct MI300X (Official)
- **Architecture:** CDNA 3
- **VRAM:** 192GB HBM3
- **Compute:** 2.6 PFLOPS FP16
- **Expected:** 100-300+ tok/s for 70B models

### Your Ryzen AI Max+ 395 (Unsupported)
- **Architecture:** RDNA 3.5 (gfx1151)
- **VRAM:** 16GB shared
- **Compute:** ~50 TFLOPS FP16 (estimate)
- **Actual:** 6.4 tok/s (14B model)
- **Bottleneck:** Unsupported GPU + unoptimized kernels

---

## Recommendations

### 1. ✅ Stick with llama.cpp (RECOMMENDED)

**Why:**
- **24 tok/s** (3.8x faster than vLLM)
- Excellent Vulkan backend for RDNA GPUs
- Designed for consumer hardware
- Much better gfx1151 support

**Use case:** Development, single-user scenarios

### 2. ⚠️ Try Optimized vLLM Settings (Worth Testing)

Update your startup script with AMD's recommendations:

```bash
#!/usr/bin/env bash
MODEL="Qwen/Qwen2.5-14B-Instruct"
PORT=8000
IMAGE="vllm/vllm-openai-rocm:v0.14.1"

docker run -d \
  --name vllm-server \
  --network=host \
  --ipc=host \
  --shm-size 16G \                    # ADD THIS (AMD recommendation)
  --group-add video \
  --cap-add SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \  # ADD THIS (AMD recommendation)
  --device /dev/kfd \
  --device /dev/dri \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  -e HIP_VISIBLE_DEVICES=0 \
  -e HSA_ENABLE_SDMA=1 \
  -e HUGGINGFACE_HUB_CACHE=/root/.cache/huggingface \  # ADD THIS
  ${IMAGE} \
  --model "${MODEL}" \
  --dtype float16 \
  --gpu-memory-utilization 0.9 \        # Changed from 0.92
  --max-model-len 8192 \
  --max-num-batched-tokens 32768 \      # Increased from 8192
  --max-num-seqs 512 \                  # ADD THIS
  --swap-space 16 \
  --enable-chunked-prefill \
  --trust-remote-code \
  --disable-log-requests \              # ADD THIS (cleaner logs)
  --port ${PORT}
```

**Expected improvement:** 10-30% at best (still slower than llama.cpp)

### 3. 🔬 Try AWQ Quantization

```bash
MODEL="Qwen/Qwen2.5-14B-Instruct-AWQ"  # 4-bit quantized
```

**Expected:** 2-3x faster than FP16, but still likely slower than llama.cpp Q4_K_M

### 4. ❌ Don't Expect Datacenter Performance

Your consumer GPU will **never match** MI300X performance:
- Different architecture (RDNA vs CDNA)
- Different memory (shared vs HBM3)
- Different optimization targets

---

## The Real Problem

**vLLM is built for datacenter Instinct GPUs, not consumer RDNA GPUs.**

AMD's ROCm inference stack priorities:
1. ✅ **Instinct** (MI300X) - Fully optimized
2. ⚠️ **RDNA Pro** (W7900) - Basic support
3. ❌ **RDNA Consumer** (RX 7900, Ryzen AI) - Unsupported/untested

Your gfx1151 is in category #3 - it works, but it's not optimized.

---

## Validation Test

Let's verify the shared memory hypothesis:

```bash
# Stop current vLLM
docker stop vllm-server && docker rm vllm-server

# Restart with AMD's recommended settings
./scripts/start_vllm_daemon_optimized.sh  # (create this with settings above)

# Re-run benchmark
python scripts/benchmark_vllm.py
```

**If performance improves significantly (>20%):** Shared memory was a bottleneck
**If performance stays the same:** Architecture mismatch is the primary issue

---

## Conclusion

**For your hardware (Ryzen AI Max+ 395):**

| Solution | Speed | Quality | Recommendation |
|----------|-------|---------|----------------|
| **llama.cpp** | 24 tok/s | Q4 (good) | ✅ **Use this** |
| **vLLM (current)** | 6.4 tok/s | FP16 (excellent) | ❌ Too slow |
| **vLLM (optimized)** | 8-10 tok/s* | FP16 (excellent) | ⚠️ Test but likely still slow |
| **vLLM AWQ** | 12-18 tok/s* | Q4 (good) | ⚠️ Possible alternative |

*Estimates based on theoretical improvements

**Final recommendation:** Stay with llama.cpp unless you need OpenAI API compatibility or will deploy on supported hardware.
