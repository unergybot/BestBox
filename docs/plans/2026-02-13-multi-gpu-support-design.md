# Multi-GPU Support Design (AMD ROCm + NVIDIA CUDA)

**Date:** 2026-02-13
**Status:** Approved
**Approach:** Shell Script Detection + Static Configs with Unified Activation

## Goal

Enable BestBox to seamlessly run on both AMD ROCm and NVIDIA CUDA GPUs with automatic detection, supporting development, production, and CI/CD workflows.

## Requirements

**Use Cases:**
1. **Development flexibility** - Same codebase works on AMD and NVIDIA dev machines
2. **Production deployment** - Deploy on different customer hardware without modification
3. **Testing/CI** - Automated tests on both GPU types

**Key Features:**
- Automatic GPU detection with manual override capability
- Single activation script that configures appropriately
- Unified service startup script
- Backward compatible with existing ROCm setup

## Architecture

### Detection Priority Chain

```
Priority 1: Environment Variable ($BESTBOX_GPU_BACKEND)
  ↓
Priority 2: Config File (.bestbox/config)
  ↓
Priority 3: Auto-Detection (nvidia-smi → rocm-smi → CPU fallback)
  ↓
Export: BESTBOX_GPU_BACKEND=cuda|rocm|cpu
```

### Component Overview

```
BestBox Multi-GPU Architecture

┌─────────────────────────────────────────────────────────┐
│ User Entry Points                                       │
├─────────────────────────────────────────────────────────┤
│  source activate.sh                                     │
│  ./start-all-services.sh                                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ GPU Detection (scripts/detect-gpu.sh)                   │
├─────────────────────────────────────────────────────────┤
│  • Check BESTBOX_GPU_BACKEND env var                    │
│  • Check .bestbox/config file                           │
│  • Test nvidia-smi (CUDA)                               │
│  • Test rocm-smi/rocminfo (ROCm)                        │
│  • Fallback to CPU                                      │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ CUDA Mode    │  │ ROCm Mode    │
├──────────────┤  ├──────────────┤
│ Environment: │  │ Environment: │
│ • CUDA_HOME  │  │ • ROCM_PATH  │
│ • CUDA vars  │  │ • HIP vars   │
│              │  │ • HSA vars   │
│ Docker:      │  │ Docker:      │
│ • compose.yml│  │ • compose.yml│
│ • .cuda.yml  │  │ • .rocm.yml  │
└──────────────┘  └──────────────┘
```

## Components

### 1. GPU Detection Script

**File:** `scripts/detect-gpu.sh`

**Purpose:** Detect GPU backend using priority chain

**Logic:**
```bash
detect_gpu() {
  # Priority 1: Environment variable
  if [ -n "$BESTBOX_GPU_BACKEND" ]; then
    validate_backend "$BESTBOX_GPU_BACKEND"
    echo "$BESTBOX_GPU_BACKEND"
    return
  fi

  # Priority 2: Config file
  if [ -f ".bestbox/config" ]; then
    gpu=$(grep "^gpu_backend=" .bestbox/config | cut -d= -f2 | tr -d ' ')
    if [ -n "$gpu" ]; then
      validate_backend "$gpu"
      echo "$gpu"
      return
    fi
  fi

  # Priority 3: Auto-detect
  if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "cuda"
  elif command -v rocm-smi &> /dev/null || command -v rocminfo &> /dev/null; then
    echo "rocm"
  else
    echo "cpu"
  fi
}

validate_backend() {
  case "$1" in
    cuda|rocm|cpu) return 0 ;;
    *)
      echo "Error: Invalid GPU backend '$1'. Must be: cuda, rocm, or cpu" >&2
      exit 1
      ;;
  esac
}
```

**Outputs:**
- `BESTBOX_GPU_BACKEND` environment variable
- `BESTBOX_COMPOSE_FILES` for Docker Compose

### 2. Unified Activation Script

**File:** `activate.sh`

**Purpose:** Single entry point for environment activation

**Key Features:**
- Auto-detects GPU type
- Sets GPU-specific environment variables
- Unsets conflicting variables (CUDA vs ROCm)
- Exports Docker Compose file selection
- Displays GPU info

**Structure:**
```bash
#!/bin/bash

# Activate venv
source ~/BestBox/venv/bin/activate

# Detect GPU
source scripts/detect-gpu.sh
GPU_BACKEND=$(detect_gpu)
export BESTBOX_GPU_BACKEND="$GPU_BACKEND"

# Configure environment based on GPU
case "$GPU_BACKEND" in
  cuda)
    # CUDA-specific environment
    export CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
    export PATH=$CUDA_HOME/bin:$PATH
    export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
    export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

    # Unset ROCm variables
    unset HSA_OVERRIDE_GFX_VERSION PYTORCH_ROCM_ARCH
    unset ROCM_PATH ROCM_HOME HIP_PATH HIP_PLATFORM
    ;;

  rocm)
    # ROCm-specific environment
    export ROCM_PATH=/opt/rocm-7.2.0
    export ROCM_HOME=/opt/rocm-7.2.0
    export PATH=$ROCM_PATH/bin:$PATH
    export LD_LIBRARY_PATH=$ROCM_PATH/lib:$LD_LIBRARY_PATH
    export HIP_PATH=$ROCM_PATH/hip
    export HIP_PLATFORM=amd
    export HSA_OVERRIDE_GFX_VERSION=11.0.0
    export PYTORCH_ROCM_ARCH=gfx1100

    # Unset CUDA variables
    unset CUDA_HOME CUDA_VISIBLE_DEVICES
    ;;

  cpu)
    # CPU mode
    unset CUDA_HOME ROCM_PATH HSA_OVERRIDE_GFX_VERSION
    echo "⚠️  Running in CPU mode (no GPU detected)"
    ;;
esac

# Common environment (all backends)
export LLM_BASE_URL="http://localhost:8001/v1"
export HF_HOME="$HOME/.cache/modelscope/hub/models"
export TRANSFORMERS_CACHE="$HOME/.cache/modelscope/hub/models"
export SENTENCE_TRANSFORMERS_HOME="$HOME/.cache/modelscope/hub/models"

# Docker Compose file selection
export BESTBOX_COMPOSE_FILES="-f docker-compose.yml -f docker-compose.$GPU_BACKEND.yml"

echo "✅ BestBox environment activated ($GPU_BACKEND mode)"
```

### 3. Docker Compose Structure

**Three-file approach:**

**`docker-compose.yml` (Base services - GPU-independent):**
- PostgreSQL
- Redis
- Qdrant
- MariaDB (ERPNext)
- LiveKit

**`docker-compose.rocm.yml` (ROCm GPU services overlay):**
```yaml
services:
  vllm:
    image: rocm/vllm-dev:rocm7.2_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.14.0rc0
    container_name: vllm-server
    devices:
      - /dev/kfd
      - /dev/dri
    environment:
      - PYTORCH_ROCM_ARCH=gfx1151
      - HSA_OVERRIDE_GFX_VERSION=11.0.0
      - FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
      - HIP_VISIBLE_DEVICES=0
    # ... rest of config

  embeddings:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    devices:
      - /dev/kfd
      - /dev/dri
    # ... ROCm config

  reranker:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    devices:
      - /dev/kfd
      - /dev/dri
    # ... ROCm config

  qwen3-asr:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    devices:
      - /dev/kfd
      - /dev/dri
    # ... ROCm config

  qwen3-tts:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    devices:
      - /dev/kfd
      - /dev/dri
    # ... ROCm config
```

**`docker-compose.cuda.yml` (CUDA GPU services overlay):**
```yaml
services:
  vllm:
    image: vllm/vllm-openai:latest
    container_name: vllm-server
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    # ... CUDA config

  embeddings:
    image: pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
    # ... CUDA config

  # Same pattern for reranker, asr, tts
```

**Usage:**
```bash
# Automatic (uses detected GPU):
docker compose $BESTBOX_COMPOSE_FILES up -d

# Expands to:
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d
# or
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up -d
```

### 4. Unified Start Script

**File:** `start-all-services.sh`

**Purpose:** Single command to start all BestBox services

**Features:**
- Detects GPU automatically
- Starts infrastructure services (postgres, redis, qdrant)
- Starts GPU services with appropriate backend
- Starts Agent API (Python)
- Starts Frontend (Next.js)
- Creates log files and PID tracking

**Structure:**
```bash
#!/bin/bash
set -e

# Detect GPU backend
source scripts/detect-gpu.sh
GPU_BACKEND=$(detect_gpu)
export BESTBOX_GPU_BACKEND="$GPU_BACKEND"

echo "🚀 Starting BestBox services ($GPU_BACKEND mode)"

# Compose file selection
BASE_COMPOSE="-f docker-compose.yml"
GPU_COMPOSE="-f docker-compose.$GPU_BACKEND.yml"

# Create logs directory
mkdir -p logs

# Start infrastructure
echo "📦 Starting infrastructure services..."
docker compose $BASE_COMPOSE up -d postgres redis qdrant

# Wait for infrastructure to be ready
sleep 5

# Start GPU services
echo "🎮 Starting GPU services ($GPU_BACKEND)..."
docker compose $BASE_COMPOSE $GPU_COMPOSE up -d vllm embeddings reranker

# Optional: Start speech services
if [ "${BESTBOX_ENABLE_SPEECH:-false}" = "true" ]; then
  echo "🎤 Starting speech services..."
  docker compose $BASE_COMPOSE $GPU_COMPOSE up -d qwen3-asr qwen3-tts s2s-gateway
fi

# Start Agent API (native Python)
echo "🤖 Starting Agent API..."
source activate.sh
nohup python services/agent_api.py > logs/agent_api.log 2>&1 &
echo $! > logs/agent_api.pid

# Start Frontend (optional)
if [ "${BESTBOX_ENABLE_FRONTEND:-true}" = "true" ]; then
  echo "🌐 Starting frontend..."
  cd frontend/copilot-demo
  npm run dev > ../../logs/frontend.log 2>&1 &
  echo $! > ../../logs/frontend.pid
  cd ../..
fi

echo ""
echo "✅ All services started successfully!"
echo ""
echo "Service URLs:"
echo "  Frontend:    http://localhost:3000"
echo "  Agent API:   http://localhost:8000"
echo "  LLM (vLLM):  http://localhost:8001"
echo "  Embeddings:  http://localhost:8081"
echo "  Reranker:    http://localhost:8004"
if [ "${BESTBOX_ENABLE_SPEECH:-false}" = "true" ]; then
  echo "  S2S Gateway: ws://localhost:8765"
fi
echo ""
echo "Logs: ./logs/"
echo "Stop services: ./stop-all-services.sh"
```

### 5. Configuration File

**File:** `.bestbox/config`

**Format:**
```ini
# BestBox Configuration
# Override GPU backend detection
gpu_backend=cuda  # Options: cuda, rocm, cpu

# Service toggles
enable_speech=false
enable_frontend=true

# Future configs...
```

**Priority:** Lower than environment variable, higher than auto-detection

## Testing Strategy

### 1. Unit Tests

**Test GPU Detection:**
```bash
# tests/test_gpu_detection.sh

test_env_var_priority() {
  BESTBOX_GPU_BACKEND=cuda source scripts/detect-gpu.sh
  result=$(detect_gpu)
  [ "$result" = "cuda" ] || fail "Expected cuda, got $result"
}

test_config_file_priority() {
  echo "gpu_backend=rocm" > .bestbox/config
  unset BESTBOX_GPU_BACKEND
  source scripts/detect-gpu.sh
  result=$(detect_gpu)
  [ "$result" = "rocm" ] || fail "Expected rocm, got $result"
  rm .bestbox/config
}

test_auto_detection() {
  unset BESTBOX_GPU_BACKEND
  rm -f .bestbox/config
  source scripts/detect-gpu.sh
  result=$(detect_gpu)
  [[ "$result" =~ ^(cuda|rocm|cpu)$ ]] || fail "Invalid backend: $result"
}
```

### 2. Integration Tests

**Test Docker Compose Configs:**
```bash
# Validate compose file syntax
docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --quiet

# Test service startup (dry run)
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up --dry-run
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up --dry-run
```

### 3. CI/CD Tests

**GitHub Actions:**
```yaml
name: Multi-GPU Tests

on: [push, pull_request]

jobs:
  test-rocm-config:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set ROCm backend
        run: echo "BESTBOX_GPU_BACKEND=rocm" >> $GITHUB_ENV
      - name: Test activation
        run: |
          source activate.sh
          [ "$BESTBOX_GPU_BACKEND" = "rocm" ]
      - name: Validate compose files
        run: docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --quiet

  test-cuda-config:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set CUDA backend
        run: echo "BESTBOX_GPU_BACKEND=cuda" >> $GITHUB_ENV
      - name: Test activation
        run: |
          source activate.sh
          [ "$BESTBOX_GPU_BACKEND" = "cuda" ]
      - name: Validate compose files
        run: docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --quiet

  test-auto-detection:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Test auto-detection (no GPU = CPU)
        run: |
          source activate.sh
          [ "$BESTBOX_GPU_BACKEND" = "cpu" ]
```

### 4. Manual Testing Checklist

```markdown
## Multi-GPU Support Manual Tests

### ROCm Mode:
- [ ] Fresh clone: `source activate.sh` detects ROCm
- [ ] Env var override: `BESTBOX_GPU_BACKEND=rocm source activate.sh` works
- [ ] Config file: Create `.bestbox/config` with `gpu_backend=rocm`
- [ ] Docker services start: `start-all-services.sh` launches ROCm containers
- [ ] vLLM health: `curl http://localhost:8001/health`
- [ ] Embeddings health: `curl http://localhost:8081/health`

### CUDA Mode:
- [ ] Env var override: `BESTBOX_GPU_BACKEND=cuda source activate.sh` works
- [ ] Config file: `.bestbox/config` with `gpu_backend=cuda`
- [ ] Docker services start: `start-all-services.sh` launches CUDA containers
- [ ] vLLM uses NVIDIA runtime
- [ ] Services accessible at expected ports

### CPU Fallback:
- [ ] No GPU detected: Falls back to CPU mode
- [ ] Warning displayed
- [ ] Services start without GPU dependencies
```

## Migration Path

### Phase 1: Add New Files (Non-Breaking)

**New files:**
- `scripts/detect-gpu.sh` - GPU detection logic
- `docker-compose.cuda.yml` - CUDA overlay (new)
- `start-all-services.sh` - Unified startup script
- `.bestbox/config.example` - Example config file
- `tests/test_gpu_detection.sh` - Unit tests

**Modified files:**
- `activate.sh` - Becomes unified (adds detection logic)
- `docker-compose.yml` - Extract GPU services to overlays
- `docker-compose.rocm.yml` - ROCm overlay (extracted from current docker-compose.yml)

**Deprecated (kept for compatibility):**
- `activate-cuda.sh` - Add deprecation notice, keep functional
- Individual service scripts - Add notice to use `start-all-services.sh`

### Phase 2: Documentation Updates

**Update CLAUDE.md:**
```markdown
## Environment Activation

### Automatic (Recommended):
```bash
source activate.sh              # Auto-detects GPU type
./start-all-services.sh         # Starts all services
```

### Manual GPU Selection:
```bash
# Force CUDA:
BESTBOX_GPU_BACKEND=cuda source activate.sh
BESTBOX_GPU_BACKEND=cuda ./start-all-services.sh

# Force ROCm:
BESTBOX_GPU_BACKEND=rocm source activate.sh

# Config file (persistent):
mkdir -p .bestbox
echo "gpu_backend=cuda" > .bestbox/config
source activate.sh
```

### Legacy (Deprecated):
```bash
source activate-cuda.sh         # Use 'source activate.sh' instead
```
```

### Phase 3: Gradual Adoption

**Timeline:**
- **Week 1-2:** Add new files, both old and new ways work
- **Week 3-4:** Update documentation, announce new unified approach
- **Month 2:** Add deprecation warnings to old scripts
- **Month 3+:** Consider removing deprecated files (team decision)

### Backward Compatibility Guarantees

**For existing ROCm users:**
- ✅ `source activate.sh` continues to work (auto-detects ROCm)
- ✅ Existing environment variables work
- ✅ No breaking changes to workflow

**For existing CUDA users:**
- ✅ `source activate-cuda.sh` still works (with deprecation notice)
- ✅ Can switch to unified `activate.sh` anytime
- ✅ Explicit override: `BESTBOX_GPU_BACKEND=cuda`

## File Structure Summary

```
BestBox/
├── activate.sh                        # Unified activation (NEW: adds detection)
├── activate-cuda.sh                   # DEPRECATED (keep for compatibility)
├── start-all-services.sh              # NEW: Unified startup script
├── stop-all-services.sh               # NEW: Stops all services
│
├── docker-compose.yml                 # MODIFIED: Base services only
├── docker-compose.rocm.yml            # NEW: ROCm GPU services overlay
├── docker-compose.cuda.yml            # NEW: CUDA GPU services overlay
│
├── scripts/
│   ├── detect-gpu.sh                  # NEW: GPU detection logic
│   ├── health-check.sh                # NEW: Service health checks
│   ├── start-vllm.sh                  # DEPRECATED (individual service)
│   └── start-embeddings.sh            # DEPRECATED (individual service)
│
├── .bestbox/
│   └── config.example                 # NEW: Example config file
│
├── tests/
│   ├── test_gpu_detection.sh          # NEW: Detection tests
│   └── test_services.sh               # NEW: Service integration tests
│
└── docs/
    └── plans/
        └── 2026-02-13-multi-gpu-support-design.md  # This document
```

## Success Criteria

### Functional Requirements:
- ✅ Auto-detects AMD ROCm, NVIDIA CUDA, or CPU mode
- ✅ Single activation script works on both GPU types
- ✅ Single start script launches all services
- ✅ Environment variable override works
- ✅ Config file override works
- ✅ Docker Compose selects correct images/runtime
- ✅ Backward compatible with existing ROCm setup

### Non-Functional Requirements:
- ✅ Detection completes in < 2 seconds
- ✅ Clear error messages for invalid configurations
- ✅ Comprehensive logging for troubleshooting
- ✅ CI/CD tests pass for both backends
- ✅ Documentation covers all use cases

## Implementation Plan

See separate implementation plan document: `2026-02-13-multi-gpu-support-plan.md`

## References

- Current ROCm setup: `activate.sh`, `docker-compose.yml`
- CUDA setup: `activate-cuda.sh`
- Docker Compose multi-file: https://docs.docker.com/compose/multiple-compose-files/
- NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/
- ROCm Docker: https://rocm.docs.amd.com/projects/install-on-linux/en/latest/how-to/docker.html

## Future Enhancements

**Potential improvements (out of scope for initial implementation):**
1. Support for multi-GPU setups (multiple GPUs of same/different types)
2. GPU selection by device ID
3. Automatic CPU fallback if GPU service fails
4. Performance benchmarking tool for both backends
5. Cloud deployment guides (AWS, Azure, GCP)
6. Kubernetes manifests with GPU node selectors
