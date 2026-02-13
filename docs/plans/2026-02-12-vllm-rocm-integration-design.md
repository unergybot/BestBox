# vLLM ROCm Integration Design

**Date:** 2026-02-12
**Author:** Claude Code
**Status:** Approved
**Branch:** feature/amd-rocm

---

## Executive Summary

Replace llama.cpp (Vulkan backend) with vLLM (ROCm Docker) as the primary LLM backend for BestBox. This migration leverages the tested vllm-rocm setup from set-bestbox with Qwen3-30B-A3B-Instruct-2507, providing better multi-user support and OpenAI API compatibility while maintaining system stability on AMD Strix Halo (gfx1151).

**Key Changes:**
- LLM Backend: llama.cpp → vLLM
- Model: Qwen2.5-14B-Q4_K_M (8GB) → Qwen3-30B-A3B-Instruct-2507 FP16 (20GB)
- Port: 8080 → 8001
- Deployment: Native binary → Docker container
- Performance: 24 tok/s single-user → 16-76 tok/s multi-user batching

**Timeline:** ~55 minutes end-to-end migration

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Changes](#component-changes)
3. [Configuration & Environment](#configuration--environment)
4. [Model Paths & Cache](#model-paths--cache)
5. [Migration Steps](#migration-steps)
6. [Testing & Validation](#testing--validation)
7. [Error Handling & Rollback](#error-handling--rollback)
8. [Acceptance Criteria](#acceptance-criteria)

---

## Architecture Overview

### Current Architecture (llama.cpp)

```
┌─────────────────────────────────────────────────────┐
│ BestBox Agent System                                │
├─────────────────────────────────────────────────────┤
│ Frontend (Next.js) :3000                            │
│         ↓                                           │
│ Agent API (FastAPI) :8000                           │
│         ↓                                           │
│ LangGraph Agents (Router → Domain Agents)           │
│         ↓                                           │
│ llama.cpp (Vulkan) :8080 ← Qwen2.5-14B-Q4_K_M      │
│ BGE-M3 Embeddings :8004                             │
│ BGE Reranker :8004                                  │
│         ↓                                           │
│ Infrastructure: Qdrant, PostgreSQL, Redis           │
└─────────────────────────────────────────────────────┘
```

### New Architecture (vLLM)

```
┌─────────────────────────────────────────────────────┐
│ BestBox Agent System                                │
├─────────────────────────────────────────────────────┤
│ Frontend (Next.js) :3000                            │
│         ↓                                           │
│ Agent API (FastAPI) :8000                           │
│         ↓                                           │
│ LangGraph Agents (Router → Domain Agents)           │
│         ↓                                           │
│ vLLM (ROCm Docker) :8001 ← Qwen3-30B-A3B FP16      │
│ BGE-M3 Embeddings :8004                             │
│ BGE Reranker :8004                                  │
│         ↓                                           │
│ Infrastructure: Qdrant, PostgreSQL, Redis           │
└─────────────────────────────────────────────────────┘
```

### Key Changes

1. **LLM Backend:** llama.cpp (native Vulkan) → vLLM (Docker ROCm)
2. **Model:** Qwen2.5-14B-Q4_K_M (8GB VRAM) → Qwen3-30B-A3B-Instruct-2507 FP16 (~20GB VRAM)
3. **Port:** :8080 → :8001 (consistent with CUDA convention)
4. **API:** llama.cpp custom → OpenAI-compatible (no Agent API changes needed)
5. **Deployment:** Native binary → Docker container
6. **Performance Profile:** Single-user optimized (24 tok/s) → Multi-user batching (16-38 tok/s)

### Compatibility

- ✅ **Agent API:** No changes needed (both expose OpenAI-compatible `/v1/chat/completions`)
- ✅ **Frontend:** Transparent - CopilotKit talks to Agent API, not LLM directly
- ✅ **Tools:** No changes - LangGraph agents abstract LLM provider
- ⚠️ **Port References:** Update any hardcoded `:8080` → `:8001` in configs

---

## Component Changes

### Files to Copy from set-bestbox

**Docker Configuration:**
```
set-bestbox/docker-compose.yml (vLLM service) → BestBox/docker-compose.yml
set-bestbox/Dockerfile                        → BestBox/docker/Dockerfile.vllm
set-bestbox/Dockerfile.therock                → BestBox/docker/Dockerfile.vllm-rocm
```

**Scripts:**
```
set-bestbox/vllm_benchmark.py                 → BestBox/scripts/benchmark_vllm.py (update)
set-bestbox/installation.md                   → BestBox/docs/vllm_rocm_installation.md
set-bestbox/benchmark.md                      → BestBox/docs/vllm_rocm_benchmarks.md
set-bestbox/vllm_benchmark_report.md          → BestBox/docs/VLLM_QWEN3_30B_BENCHMARK.md
```

**Results (for reference):**
```
set-bestbox/results/                          → BestBox/docs/benchmarks/vllm-qwen3-30b/
```

### Files to Create (New)

**Startup Scripts:**
```
BestBox/scripts/start-vllm.sh                 # Primary vLLM startup script (port 8001)
BestBox/scripts/stop-vllm.sh                  # Graceful shutdown
BestBox/scripts/restart-vllm.sh               # Restart with health check
BestBox/scripts/monitor-vllm.sh               # Health monitoring
BestBox/scripts/rollback-to-llamacpp.sh       # Emergency rollback
```

**Environment Configuration:**
```
BestBox/.env.vllm                             # vLLM-specific environment variables
```

### Files to Archive (llama.cpp removal)

**Move to docs/archive/llama-cpp/:**
```
scripts/start-llm.sh                          → docs/archive/llama-cpp/scripts/
scripts/start-llm-cuda.sh                     → docs/archive/llama-cpp/scripts/
scripts/start-llm-strix.sh                    → docs/archive/llama-cpp/scripts/
scripts/start-llm-docker.sh                   → docs/archive/llama-cpp/scripts/
scripts/build-llama-cuda.sh                   → docs/archive/llama-cpp/scripts/
scripts/install-llama-rocm.sh                 → docs/archive/llama-cpp/scripts/
docs/llm_backend_comparison.md                → docs/archive/llama-cpp/docs/
docs/VULKAN_VALIDATION_REPORT.md              → docs/archive/llama-cpp/docs/
```

**Create archive README:**
```
docs/archive/llama-cpp/README.md              # Why archived, how to restore if needed
```

### Files to Update

**Documentation:**
```
CLAUDE.md                                     # Update LLM section for vLLM
README.md                                     # Update service ports and startup
docs/system_design.md                         # Update infrastructure layer
docs/PROJECT_STATUS.md                        # Mark vLLM migration complete
activate.sh                                   # Update LLM_BASE_URL from :8080 → :8001
activate-cuda.sh                              # Update LLM_BASE_URL
```

**Configuration:**
```
docker-compose.yml                            # Add vLLM service, update networks
.env (if exists)                              # Add vLLM environment variables
.gitignore                                    # Add vLLM model cache paths if needed
```

**Scripts:**
```
scripts/start-all-services.sh                 # Replace llama.cpp with vLLM
scripts/test_agents.py                        # Update LLM endpoint if hardcoded
```

### Files Unchanged

**Core Application (no changes needed):**
```
✅ agents/*                                   # Abstract LLM via LangChain
✅ tools/*                                    # No LLM direct dependency
✅ services/agent_api.py                      # Uses env var for LLM endpoint
✅ frontend/*                                 # Talks to Agent API, not LLM
✅ services/embeddings/                       # Independent service
✅ services/speech/                           # Independent service
```

---

## Configuration & Environment

### Docker Compose Service Definition

**Add to BestBox/docker-compose.yml:**

```yaml
services:
  # ... existing services (qdrant, postgres, redis) ...

  vllm:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    container_name: vllm-server
    restart: unless-stopped

    # ROCm device access
    devices:
      - /dev/kfd
      - /dev/dri

    # Security and capabilities
    cap_add:
      - SYS_PTRACE
    security_opt:
      - seccomp=unconfined

    # User/group permissions
    group_add:
      - video
      - render

    # IPC and shared memory
    ipc: host
    shm_size: 16G

    # Port mapping
    ports:
      - "8001:8001"

    # Volume mounts
    volumes:
      # ModelScope cache (primary)
      - ${HOME}/.cache/modelscope/hub/models:/models:ro
      # HuggingFace cache (fallback)
      - ${HOME}/.cache/huggingface:/root/.cache/huggingface:ro

    # Environment variables
    environment:
      # ROCm configuration
      - PYTORCH_ROCM_ARCH=gfx1151
      - HSA_OVERRIDE_GFX_VERSION=11.0.0
      - FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
      - HIP_VISIBLE_DEVICES=0
      - HSA_ENABLE_SDMA=1

      # Model paths
      - MODELSCOPE_CACHE=/models
      - HF_HOME=/root/.cache/huggingface
      - TRANSFORMERS_CACHE=/root/.cache/huggingface/hub

    # vLLM command (stability-first profile)
    command: >
      bash -c "
      pip install vllm amdsmi==7.0.2 &&
      vllm serve /models/Qwen/Qwen3-30B-A3B-Instruct-2507
        --host 0.0.0.0
        --port 8001
        --served-model-name qwen3-30b
        --dtype float16
        --gpu-memory-utilization 0.90
        --max-model-len 2048
        --max-num-seqs 8
        --max-num-batched-tokens 4096
        --enforce-eager
        --trust-remote-code
        --disable-log-requests
      "

    # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 180s  # 3 minutes for model loading

    # Logging
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

    # Network
    networks:
      - bestbox-network

networks:
  bestbox-network:
    driver: bridge
```

### Environment File (.env.vllm)

```bash
# vLLM ROCm Configuration
# Based on set-bestbox testing results

# Model Configuration
VLLM_MODEL_PATH=/models/Qwen/Qwen3-30B-A3B-Instruct-2507
VLLM_MODEL_NAME=qwen3-30b
VLLM_PORT=8001

# ROCm Settings (gfx1151 - Strix Halo)
PYTORCH_ROCM_ARCH=gfx1151
HSA_OVERRIDE_GFX_VERSION=11.0.0
FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
HIP_VISIBLE_DEVICES=0
HSA_ENABLE_SDMA=1

# Performance Profile: Stability-First
# Based on benchmark results: 76 tok/s, 0% failures
VLLM_DTYPE=float16
VLLM_GPU_MEMORY_UTIL=0.90
VLLM_MAX_MODEL_LEN=2048
VLLM_MAX_NUM_SEQS=8
VLLM_MAX_NUM_BATCHED_TOKENS=4096
VLLM_ENFORCE_EAGER=true  # Required for gfx1151 stability

# Cache Paths
MODELSCOPE_CACHE=/models
HF_HOME=/root/.cache/huggingface
TRANSFORMERS_CACHE=/root/.cache/huggingface/hub

# Logging
VLLM_LOG_LEVEL=INFO
VLLM_DISABLE_LOG_REQUESTS=true

# Health Check
VLLM_HEALTH_CHECK_TIMEOUT=180  # 3 minutes for model load
```

### Service Port Summary (Updated)

```
Frontend:          :3000
Agent API:         :8000
vLLM (NEW):        :8001  ← Qwen3-30B
Embeddings:        :8004
Reranker:          :8004
Qdrant:            :6333, :6334
PostgreSQL:        :5432
Redis:             :6379
S2S Gateway:       :8765

# Archived (llama.cpp):
# LLM (old):       :8080  ← Moved to docs/archive/
```

---

## Model Paths & Cache

### ModelScope Cache Structure

Models are located at:
```
~/.cache/modelscope/hub/models/
├── BAAI/bge-m3/                    # Embeddings (already in use)
├── BAAI/bge-reranker-v2-m3/        # Reranker (already in use)
└── Qwen/Qwen3-30B-A3B-Instruct-2507/  # NEW: vLLM model (16 shards)
```

### Docker Volume Mounts

**vLLM Service:**
```yaml
volumes:
  # ModelScope cache (primary)
  - ~/.cache/modelscope/hub/models:/models:ro
  # HuggingFace cache (fallback for compatibility)
  - ~/.cache/huggingface:/root/.cache/huggingface:ro
```

**Model Path for vLLM:**
```bash
# Inside container, model is at:
/models/Qwen/Qwen3-30B-A3B-Instruct-2507
```

### Cache Priority Strategy

1. **Primary:** ModelScope cache (`~/.cache/modelscope/hub/models/`)
   - All models already downloaded here
   - Read-only mount (`:ro`) for safety

2. **Secondary:** HuggingFace cache (for compatibility)
   - Some Python libraries default to HF cache
   - vLLM may check HF cache first, then use explicit path

3. **Explicit Paths:** Always pass full model path to vLLM
   ```bash
   vllm serve /models/Qwen/Qwen3-30B-A3B-Instruct-2507 \
     --served-model-name qwen3-30b ...
   ```

### Benefits

- ✅ No need to re-download 30B model (~60GB)
- ✅ Consistent with existing embeddings/reranker setup
- ✅ Both caches mounted for maximum compatibility
- ✅ Read-only mounts prevent accidental model corruption

---

## Migration Steps

### Pre-Migration Checklist

**Before starting migration:**
```bash
# 1. Verify current system is working
curl http://localhost:8080/v1/models  # llama.cpp health check
curl http://localhost:8000/health      # Agent API health check

# 2. Verify ModelScope models exist
ls -lh ~/.cache/modelscope/hub/models/Qwen/Qwen3-30B-A3B-Instruct-2507/
ls -lh ~/.cache/modelscope/hub/models/BAAI/bge-m3/

# 3. Stop all running services
docker compose down
pkill -f llama-server  # Stop any running llama.cpp instances

# 4. Create backup branch (we're on feature/amd-rocm already ✓)
git status
git add -A
git commit -m "checkpoint: pre-vllm-migration state"
```

### Phase 1: Archive llama.cpp (5 minutes)

```bash
# 1. Create archive directory structure
mkdir -p docs/archive/llama-cpp/{scripts,docs}

# 2. Move llama.cpp scripts
mv scripts/start-llm.sh docs/archive/llama-cpp/scripts/
mv scripts/start-llm-cuda.sh docs/archive/llama-cpp/scripts/
mv scripts/start-llm-strix.sh docs/archive/llama-cpp/scripts/
mv scripts/start-llm-docker.sh docs/archive/llama-cpp/scripts/
mv scripts/build-llama-cuda.sh docs/archive/llama-cpp/scripts/
mv scripts/install-llama-rocm.sh docs/archive/llama-cpp/scripts/

# 3. Move llama.cpp documentation
mv docs/llm_backend_comparison.md docs/archive/llama-cpp/docs/
mv docs/VULKAN_VALIDATION_REPORT.md docs/archive/llama-cpp/docs/

# 4. Create archive README (see full content in design)

# 5. Commit archive
git add docs/archive/llama-cpp/
git commit -m "chore: archive llama.cpp setup before vLLM migration"
```

### Phase 2: Copy vLLM files from set-bestbox (10 minutes)

```bash
# 1. Copy Docker configurations
cp /home/unergy/set-bestbox/Dockerfile docker/Dockerfile.vllm
cp /home/unergy/set-bestbox/Dockerfile.therock docker/Dockerfile.vllm-rocm

# 2. Copy documentation
cp /home/unergy/set-bestbox/installation.md docs/vllm_rocm_installation.md
cp /home/unergy/set-bestbox/benchmark.md docs/vllm_rocm_benchmarks.md
cp /home/unergy/set-bestbox/vllm_benchmark_report.md docs/VLLM_QWEN3_30B_BENCHMARK.md

# 3. Copy benchmark script
cp /home/unergy/set-bestbox/vllm_benchmark.py scripts/benchmark_vllm.py

# 4. Copy benchmark results for reference
mkdir -p docs/benchmarks/vllm-qwen3-30b
cp -r /home/unergy/set-bestbox/results/* docs/benchmarks/vllm-qwen3-30b/
```

### Phase 3: Create new vLLM configuration (15 minutes)

```bash
# 1. Create environment file (see .env.vllm content above)
# 2. Create startup script (see scripts/start-vllm.sh above)
# 3. Create stop script
# 4. Create restart script
# 5. Update docker-compose.yml (add vLLM service)
# 6. Commit new files

git add .env.vllm scripts/start-vllm.sh scripts/stop-vllm.sh scripts/restart-vllm.sh
git add docker/Dockerfile.vllm* docs/vllm_* docs/benchmarks/
git add docker-compose.yml
git commit -m "feat: add vLLM with Qwen3-30B configuration"
```

### Phase 4: Update documentation (10 minutes)

```bash
# 1. Update CLAUDE.md (LLM section)
# 2. Update README.md (service ports, startup)
# 3. Update activate.sh (port 8080 → 8001)
# 4. Update activate-cuda.sh
# 5. Update scripts/start-all-services.sh
# 6. Update docs/system_design.md
# 7. Update docs/PROJECT_STATUS.md

git add CLAUDE.md README.md activate*.sh scripts/start-all-services.sh docs/
git commit -m "docs: update for vLLM migration"
```

### Phase 5: First boot and validation (5-10 minutes)

```bash
# 1. Start infrastructure
docker compose up -d qdrant postgres redis

# 2. Start vLLM (this will take 2-3 minutes to load model)
./scripts/start-vllm.sh

# 3. Monitor startup
docker compose logs -f vllm

# 4. Test health endpoint
curl http://localhost:8001/health

# 5. Test model endpoint
curl http://localhost:8001/v1/models

# 6. Test simple completion (see test in Testing section)
```

### Timeline Summary

| Phase | Duration | Description |
|-------|----------|-------------|
| Pre-flight checks | 5 min | Verify current state, backup |
| Archive llama.cpp | 5 min | Move old files, create README |
| Copy from set-bestbox | 10 min | Bring in tested configs |
| Create vLLM config | 15 min | New scripts, env files |
| Update docs | 10 min | CLAUDE.md, README, etc. |
| First boot & test | 10 min | Start vLLM, validate |
| **Total** | **55 min** | **End-to-end migration** |

---

## Testing & Validation

### Level 1: Service Health Checks

```bash
# 1. Container status
docker compose ps vllm
# Expected: State = Up, Status = healthy

# 2. Health endpoint
curl -f http://localhost:8001/health
# Expected: HTTP 200 OK

# 3. Models endpoint
curl http://localhost:8001/v1/models | jq
# Expected: {"object":"list","data":[{"id":"qwen3-30b",...}]}

# 4. GPU utilization
docker exec vllm-server rocm-smi --showuse
# Expected: GPU 0 showing VRAM usage (~20GB for loaded model)

# 5. Container logs (no errors)
docker compose logs vllm | grep -i error
# Expected: No critical errors
```

### Level 2: LLM Functionality Tests

```bash
# Simple chat completion
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-30b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is 2+2?"}
    ],
    "max_tokens": 50,
    "temperature": 0.7
  }' | jq

# Expected: JSON response with answer about "4"
```

### Level 3: Agent API Integration Tests

```bash
# Run agent integration tests
python scripts/test_agents.py

# Tests should cover:
# - Router agent classification
# - ERP agent with tools
# - CRM agent with tools
# - IT Ops agent with tools
# - OA agent with tools
# - Fallback handling

# Expected: All tests pass with vLLM backend
```

### Level 4: End-to-End Frontend Tests

Manual testing via browser at http://localhost:3000:

- Select "ERP Scenario" from dropdown
- Type: "Show me inventory status"
- Verify: Agent responds via vLLM
- Test all 4 scenarios (ERP, CRM, IT Ops, OA)

### Level 5: Performance Validation

```bash
# Run comprehensive benchmark
python scripts/benchmark_vllm.py \
  --num-prompts 8 \
  --input-length 128 \
  --output-length 128 \
  --max-concurrent 2

# Expected results (from set-bestbox testing):
# ✅ Throughput: ~76 tok/s (stability-first config)
# ✅ Latency: ~7.3 seconds average
# ✅ Success rate: 100%
# ✅ P50 latency: ~7.4 seconds
```

### Acceptance Criteria

Migration is successful when:

- ✅ vLLM container starts and reaches healthy state
- ✅ Model loads in <5 minutes
- ✅ Health endpoint returns 200 OK
- ✅ Basic completions work (non-streaming)
- ✅ Streaming completions work
- ✅ Benchmark results match set-bestbox (16-76 tok/s)
- ✅ Agent API connects to vLLM on port 8001
- ✅ All 4 domain agents respond correctly
- ✅ Frontend UI works with all scenarios
- ✅ No errors in logs after 10 test requests
- ✅ GPU utilization stable during load
- ✅ Other services (embeddings, reranker) unaffected
- ✅ Performance meets stability-first profile targets

---

## Error Handling & Rollback

### Common Issues and Solutions

**Issue 1: vLLM container fails to start**

Symptoms: Container in Restarting or Exit 1 state

Diagnosis:
```bash
docker compose logs vllm | tail -50
# Common errors: No HIP GPUs, ImportError flash_attn, OutOfMemoryError
```

Solutions:
- GPU access: Check /dev/kfd and /dev/dri permissions
- Missing flash-attention: Rebuild with installation in Dockerfile
- OOM: Reduce gpu-memory-utilization to 0.85

**Issue 2: Model loading takes too long (>5 minutes)**

Solutions:
- Verify model files exist at ModelScope path
- Check volume mount inside container
- Increase health check start_period to 300s

**Issue 3: vLLM crashes during inference**

Solutions:
- Verify --enforce-eager is set (required for gfx1151)
- Reduce max-num-seqs to 4
- Lower gpu-memory-utilization to 0.80
- Check GPU temperature (<85°C)

**Issue 4: Agent API can't connect to vLLM**

Solutions:
- Check LLM_BASE_URL=http://localhost:8001/v1
- Test vLLM directly: curl http://localhost:8001/health
- Restart Agent API with correct env

**Issue 5: Poor performance (<10 tok/s)**

Solutions:
- Verify GPU utilization >80%
- Check dtype=float16 (not float32)
- Increase batching parameters
- Check system load (htop)

### Emergency Rollback (5 minutes)

```bash
#!/usr/bin/env bash
# scripts/rollback-to-llamacpp.sh

# 1. Stop vLLM
docker compose stop vllm

# 2. Restore llama.cpp scripts
cp docs/archive/llama-cpp/scripts/start-llm.sh scripts/
chmod +x scripts/start-llm.sh

# 3. Update environment
sed -i 's|:8001/v1"|:8080/v1"|g' activate.sh
source activate.sh

# 4. Start llama.cpp
./scripts/start-llm.sh &

# 5. Restart Agent API
pkill -f agent_api
./scripts/start-agent-api.sh &

# 6. Verify
curl -f http://localhost:8080/v1/models && echo "✅ llama.cpp operational"
curl http://localhost:8000/health && echo "✅ System operational"
```

### Monitoring

```bash
# scripts/monitor-vllm.sh
# Continuous monitoring of:
# - Container status
# - Health endpoint
# - GPU utilization
# - VRAM usage
# - Request count
# - Recent errors
```

---

## Acceptance Criteria

The vLLM migration is considered complete and successful when:

### Functional Requirements
- ✅ vLLM container starts automatically via docker compose
- ✅ Model loads successfully in <5 minutes
- ✅ Health check passes after startup
- ✅ Chat completions work (streaming and non-streaming)
- ✅ All 4 domain agents (ERP, CRM, IT Ops, OA) function correctly
- ✅ Frontend UI works with all scenarios
- ✅ RAG pipeline integrates with vLLM

### Performance Requirements
- ✅ Throughput: 16-76 tok/s (depending on batching)
- ✅ Latency: <10 seconds for 128 token generation
- ✅ Success rate: >99% for standard requests
- ✅ GPU utilization: 80-95% during active inference
- ✅ VRAM usage: Stable at ~20GB

### Operational Requirements
- ✅ Docker Compose orchestration works
- ✅ Health checks pass consistently
- ✅ Logging captures key events
- ✅ Monitoring scripts functional
- ✅ Rollback procedure tested and documented

### Documentation Requirements
- ✅ CLAUDE.md updated with vLLM info
- ✅ README.md reflects new ports and startup
- ✅ Migration guide complete
- ✅ Troubleshooting guide available
- ✅ Archive of llama.cpp setup preserved

---

## Next Steps

After this design is approved:

1. **Implementation Phase:**
   - Use writing-plans skill to create detailed implementation plan
   - Execute migration following the steps outlined
   - Run comprehensive testing suite
   - Document any deviations or issues

2. **Post-Migration:**
   - Monitor performance for 24-48 hours
   - Collect benchmark data
   - Update performance documentation
   - Consider optimization opportunities

3. **Future Enhancements:**
   - Explore quantized models (AWQ/GPTQ) for better throughput
   - Test with larger context windows (8192+ tokens)
   - Evaluate multi-GPU support if additional GPUs available
   - Consider vLLM version upgrades for gfx1151 optimizations

---

**Design Status:** ✅ APPROVED
**Ready for Implementation:** YES
**Estimated Migration Time:** 55 minutes
**Risk Level:** LOW (tested configuration from set-bestbox)
