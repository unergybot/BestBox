# LLM Server Scripts - Dual Model Architecture

## Overview

BestBox uses **two models** for optimal performance:
- **Heavy model** (14B): Agent reasoning, tool calling, complex queries
- **Light model** (7B): Router classification, quick responses, ASR cleanup

## Quick Start

### Start Both Models (Recommended)

```bash
# Terminal 1: Heavy model (native Vulkan)
./scripts/start-llm.sh

# Terminal 2: Light model (Docker ROCm)
./scripts/start-llm-docker.sh

# Verify both running
curl http://localhost:8080/health  # Heavy
curl http://localhost:8081/health  # Light
```

### Single Model Testing

```bash
# Just heavy model (backward compatible)
./scripts/start-llm.sh
```

## Available Scripts

### 1. start-llm.sh - Heavy Model (Native Vulkan)
- **Model**: Qwen2.5-14B-Instruct Q4_K_M
- **Port**: 8080
- **Backend**: Vulkan
- **Performance**: 527 tok/s prompt, 24 tok/s generation ✅
- **VRAM**: ~8-10GB
- **Use for**: Agent reasoning, tool calling, complex queries

### 2. start-llm-docker.sh - Light Model (Docker ROCm)
- **Model**: Qwen2.5-7B-Instruct Q5_K_M
- **Port**: 8081
- **Backend**: HIP/ROCm
- **Performance**: ~15-20 tok/s (estimated)
- **VRAM**: ~6GB
- **Use for**: Router classification, quick Q&A, ASR cleanup

## Model Comparison

| Feature | Heavy (8080) | Light (8081) |
|---------|--------------|--------------|
| Model | 14B Q4_K_M | 7B Q5_K_M |
| Backend | Native Vulkan | Docker ROCm |
| Speed | 24 tok/s | ~18 tok/s |
| Quality | Highest | Good |
| Latency | Higher | Lower |
| Use case | Reasoning | Classification |

## Resource Usage

```
Total VRAM available: 96GB
Heavy model:          ~8-10GB
Light model:          ~6GB
Total used:           ~14-16GB (16% utilization)
Headroom:             ~80GB
```

## Setup Instructions

### Prerequisites

1. Heavy model already exists at: `~/models/14b/Qwen2.5-14B-Instruct-Q4_K_M.gguf`

2. Download light model:
```bash
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF \
  qwen2.5-7b-instruct-q5_k_m.gguf \
  --local-dir ~/models/7b \
  --local-dir-use-symlinks False
```

### Start Services

```bash
# Terminal 1: Heavy model
./scripts/start-llm.sh

# Terminal 2: Light model
./scripts/start-llm-docker.sh
```

## Routing Logic

### Use Light Model (8081) For:
- ✅ Router classification (agents/router.py)
- ✅ Intent detection
- ✅ Quick yes/no questions
- ✅ ASR text cleanup
- ✅ Simple summaries

### Use Heavy Model (8080) For:
- ✅ ERP/CRM/IT Ops/OA agent reasoning
- ✅ Tool calling
- ✅ Multi-step planning
- ✅ Long-form generation
- ✅ RAG synthesis

## Performance Benefits

### Before (Single 14B Model)
```
Query → Router (14B) → Agent (14B)
Latency: 2-3s + 5-10s = 7-13s
```

### After (Dual Models)
```
Query → Router (7B) → Agent (14B)
Latency: 0.5-1s + 5-10s = 5.5-11s
Improvement: ~15-20% faster, router 3x faster
```

## Stopping Services

```bash
# Heavy model (native)
pkill -f "llama-server.*8080"

# Light model (Docker)
docker stop llm-server-light

# Both
pkill -f llama-server && docker stop llm-server-light
```

## Troubleshooting

### Port Conflicts
```bash
# Check what's using ports
sudo lsof -i :8080
sudo lsof -i :8081

# Kill processes if needed
```

### VRAM Issues
```bash
# Check VRAM usage
rocm-smi --showmeminfo vram

# If needed, reduce GPU layers in scripts
```

## Documentation

- [docs/dual_model_setup.md](../docs/dual_model_setup.md) - Complete dual model guide
- [docs/llm_backend_comparison.md](../docs/llm_backend_comparison.md) - Backend comparison

## Migration Path

1. **Phase 1** (Current): Test both models in parallel
2. **Phase 2**: Update router to use light model
3. **Phase 3**: Expand light model usage (ASR, quick Q&A)
4. **Phase 4**: Benchmark and optimize
