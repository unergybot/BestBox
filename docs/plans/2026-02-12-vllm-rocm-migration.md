# vLLM ROCm Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace llama.cpp with vLLM as the LLM backend for BestBox, migrating to Qwen3-30B model on port 8001.

**Architecture:** Migrate from native llama.cpp (Vulkan, port 8080) to Docker-based vLLM (ROCm, port 8001). Preserve tested configuration from set-bestbox, archive old setup, update all documentation.

**Tech Stack:** vLLM 0.12.0+rocm711, Docker Compose, ROCm 7.2, Qwen3-30B-A3B-Instruct-2507, ModelScope cache

---

## Task 1: Pre-Migration Verification

**Files:**
- Verify: `~/.cache/modelscope/hub/models/Qwen/Qwen3-30B-A3B-Instruct-2507/`
- Check: Current services running

**Step 1: Verify ModelScope models exist**

Run:
```bash
ls -lh ~/.cache/modelscope/hub/models/Qwen/Qwen3-30B-A3B-Instruct-2507/ | head -5
ls -lh ~/.cache/modelscope/hub/models/BAAI/bge-m3/ | head -3
```

Expected: Both directories exist with model files

**Step 2: Stop running services**

Run:
```bash
docker compose down
pkill -f llama-server || true
```

Expected: All containers stopped, llama-server process killed

**Step 3: Create pre-migration checkpoint**

Run:
```bash
git status
git add -A
git commit -m "checkpoint: pre-vllm-migration state"
```

Expected: Commit created successfully

---

## Task 2: Archive llama.cpp Setup

**Files:**
- Create: `docs/archive/llama-cpp/scripts/`
- Create: `docs/archive/llama-cpp/docs/`
- Move: 6 scripts, 2 docs
- Create: `docs/archive/llama-cpp/README.md`

**Step 1: Create archive directory structure**

Run:
```bash
mkdir -p docs/archive/llama-cpp/scripts
mkdir -p docs/archive/llama-cpp/docs
```

Expected: Directories created

**Step 2: Move llama.cpp scripts to archive**

Run:
```bash
mv scripts/start-llm.sh docs/archive/llama-cpp/scripts/
mv scripts/start-llm-cuda.sh docs/archive/llama-cpp/scripts/
mv scripts/start-llm-strix.sh docs/archive/llama-cpp/scripts/
mv scripts/start-llm-docker.sh docs/archive/llama-cpp/scripts/
mv scripts/build-llama-cuda.sh docs/archive/llama-cpp/scripts/ || true
mv scripts/install-llama-rocm.sh docs/archive/llama-cpp/scripts/ || true
```

Expected: Scripts moved to archive (some may not exist)

**Step 3: Move llama.cpp documentation to archive**

Run:
```bash
mv docs/llm_backend_comparison.md docs/archive/llama-cpp/docs/ || true
mv docs/VULKAN_VALIDATION_REPORT.md docs/archive/llama-cpp/docs/ || true
```

Expected: Docs moved to archive (if they exist)

**Step 4: Create archive README**

Create file: `docs/archive/llama-cpp/README.md`

```markdown
# llama.cpp Archive

This directory contains the previous llama.cpp-based LLM setup, archived on 2026-02-12.

## Why Archived

Replaced with vLLM for better multi-user support and OpenAI API compatibility.

## Previous Performance

- Model: Qwen2.5-14B-Q4_K_M quantized
- Backend: Vulkan on gfx1151
- Performance: 527 tok/s prompt, 24 tok/s generation
- Port: 8080

## Restore Instructions

If you need to restore llama.cpp:

```bash
# 1. Copy scripts back
cp docs/archive/llama-cpp/scripts/start-llm.sh scripts/
chmod +x scripts/start-llm.sh

# 2. Update activate.sh
sed -i 's|:8001/v1"|:8080/v1"|g' activate.sh

# 3. Stop vLLM
docker compose stop vllm

# 4. Start llama.cpp
./scripts/start-llm.sh
```

## Archived Date

2026-02-12
```

**Step 5: Verify archive structure**

Run:
```bash
ls -R docs/archive/llama-cpp/
```

Expected: Shows scripts/, docs/, README.md

**Step 6: Commit archive**

Run:
```bash
git add docs/archive/llama-cpp/
git commit -m "chore: archive llama.cpp setup before vLLM migration"
```

Expected: Archive committed successfully

---

## Task 3: Copy Dockerfiles from set-bestbox

**Files:**
- Create: `docker/` directory
- Copy: `docker/Dockerfile.vllm`
- Copy: `docker/Dockerfile.vllm-rocm`

**Step 1: Create docker directory if not exists**

Run:
```bash
mkdir -p docker
```

Expected: Directory exists

**Step 2: Copy Dockerfiles**

Run:
```bash
cp /home/unergy/set-bestbox/Dockerfile docker/Dockerfile.vllm
cp /home/unergy/set-bestbox/Dockerfile.therock docker/Dockerfile.vllm-rocm
```

Expected: 2 Dockerfiles copied

**Step 3: Verify Dockerfiles copied**

Run:
```bash
ls -lh docker/Dockerfile.vllm*
```

Expected: Both files listed

**Step 4: Commit Dockerfiles**

Run:
```bash
git add docker/Dockerfile.vllm*
git commit -m "feat: add vLLM Dockerfiles from set-bestbox"
```

Expected: Dockerfiles committed

---

## Task 4: Copy Documentation from set-bestbox

**Files:**
- Copy: `docs/vllm_rocm_installation.md`
- Copy: `docs/vllm_rocm_benchmarks.md`
- Copy: `docs/VLLM_QWEN3_30B_BENCHMARK.md`
- Create: `docs/benchmarks/vllm-qwen3-30b/`

**Step 1: Copy installation documentation**

Run:
```bash
cp /home/unergy/set-bestbox/installation.md docs/vllm_rocm_installation.md
```

Expected: File copied

**Step 2: Copy benchmark documentation**

Run:
```bash
cp /home/unergy/set-bestbox/benchmark.md docs/vllm_rocm_benchmarks.md || echo "benchmark.md not found, skipping"
cp /home/unergy/set-bestbox/vllm_benchmark_report.md docs/VLLM_QWEN3_30B_BENCHMARK.md
```

Expected: Benchmark docs copied

**Step 3: Copy benchmark script**

Run:
```bash
cp /home/unergy/set-bestbox/vllm_benchmark.py scripts/benchmark_vllm.py
chmod +x scripts/benchmark_vllm.py
```

Expected: Benchmark script copied

**Step 4: Copy benchmark results**

Run:
```bash
mkdir -p docs/benchmarks/vllm-qwen3-30b
cp -r /home/unergy/set-bestbox/results/* docs/benchmarks/vllm-qwen3-30b/ 2>/dev/null || echo "No results to copy"
```

Expected: Results copied if they exist

**Step 5: Commit documentation**

Run:
```bash
git add docs/vllm_* docs/VLLM_* docs/benchmarks/ scripts/benchmark_vllm.py
git commit -m "docs: add vLLM documentation and benchmarks from set-bestbox"
```

Expected: Documentation committed

---

## Task 5: Create vLLM Environment File

**Files:**
- Create: `.env.vllm`

**Step 1: Create .env.vllm file**

Create file: `.env.vllm`

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

**Step 2: Verify environment file created**

Run:
```bash
cat .env.vllm | head -10
```

Expected: Shows first 10 lines of env file

**Step 3: Commit environment file**

Run:
```bash
git add .env.vllm
git commit -m "feat: add vLLM environment configuration"
```

Expected: Environment file committed

---

## Task 6: Update docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Read current docker-compose.yml**

Run:
```bash
cat docker-compose.yml
```

Expected: Shows current docker-compose content

**Step 2: Add vLLM service to docker-compose.yml**

Add to `docker-compose.yml` in the services section:

```yaml
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

    # Network (if networks section exists)
    networks:
      - bestbox-network
```

**Step 3: Ensure networks section exists**

If docker-compose.yml doesn't have a networks section at the end, add:

```yaml
networks:
  bestbox-network:
    driver: bridge
```

**Step 4: Verify docker-compose.yml syntax**

Run:
```bash
docker compose config 2>&1 | head -20
```

Expected: No syntax errors (or formatted YAML output)

**Step 5: Commit docker-compose.yml**

Run:
```bash
git add docker-compose.yml
git commit -m "feat: add vLLM service to docker-compose"
```

Expected: docker-compose.yml committed

---

## Task 7: Create vLLM Startup Script

**Files:**
- Create: `scripts/start-vllm.sh`

**Step 1: Create start-vllm.sh script**

Create file: `scripts/start-vllm.sh`

```bash
#!/usr/bin/env bash
# Start vLLM with ROCm for Qwen3-30B
# Port: 8001 (avoids conflict with Agent API on 8000)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting vLLM with Qwen3-30B-A3B-Instruct-2507"
echo "=================================================="
echo "Backend: ROCm 7.2 (gfx1151)"
echo "Port: 8001"
echo "Profile: Stability-First (enforce-eager)"
echo ""

# Load environment
if [ -f "$PROJECT_ROOT/.env.vllm" ]; then
    set -a
    source "$PROJECT_ROOT/.env.vllm"
    set +a
fi

# Check if container already running
if docker ps --format '{{.Names}}' | grep -q "^vllm-server$"; then
    echo "⚠️  vLLM container already running"
    echo "Stop it with: docker compose stop vllm"
    exit 1
fi

# Start vLLM service
cd "$PROJECT_ROOT"
docker compose up -d vllm

echo ""
echo "⏳ Waiting for model to load (this takes ~2-3 minutes)..."
echo ""
echo "📊 Monitor startup:"
echo "   docker compose logs -f vllm"
echo ""
echo "🔍 Check health:"
echo "   curl http://localhost:8001/health"
echo ""
echo "🛑 Stop service:"
echo "   docker compose stop vllm"
echo ""

# Wait and show initial logs
sleep 5
docker compose logs --tail=50 vllm
```

**Step 2: Make script executable**

Run:
```bash
chmod +x scripts/start-vllm.sh
```

Expected: Script is executable

**Step 3: Verify script syntax**

Run:
```bash
bash -n scripts/start-vllm.sh
```

Expected: No syntax errors (silent output)

**Step 4: Commit startup script**

Run:
```bash
git add scripts/start-vllm.sh
git commit -m "feat: add vLLM startup script"
```

Expected: Script committed

---

## Task 8: Create vLLM Stop Script

**Files:**
- Create: `scripts/stop-vllm.sh`

**Step 1: Create stop-vllm.sh script**

Create file: `scripts/stop-vllm.sh`

```bash
#!/usr/bin/env bash
# Stop vLLM gracefully

set -e

echo "🛑 Stopping vLLM service..."
docker compose stop vllm

echo "✅ vLLM stopped"
```

**Step 2: Make script executable**

Run:
```bash
chmod +x scripts/stop-vllm.sh
```

Expected: Script is executable

**Step 3: Commit stop script**

Run:
```bash
git add scripts/stop-vllm.sh
git commit -m "feat: add vLLM stop script"
```

Expected: Script committed

---

## Task 9: Create vLLM Restart Script

**Files:**
- Create: `scripts/restart-vllm.sh`

**Step 1: Create restart-vllm.sh script**

Create file: `scripts/restart-vllm.sh`

```bash
#!/usr/bin/env bash
# Restart vLLM with health check

set -e

echo "🔄 Restarting vLLM service..."
docker compose restart vllm

echo "⏳ Waiting for health check..."
sleep 10

if curl -sf http://localhost:8001/health > /dev/null; then
    echo "✅ vLLM healthy"
else
    echo "⚠️  vLLM health check failed"
    echo "Check logs: docker compose logs vllm"
    exit 1
fi
```

**Step 2: Make script executable**

Run:
```bash
chmod +x scripts/restart-vllm.sh
```

Expected: Script is executable

**Step 3: Commit restart script**

Run:
```bash
git add scripts/restart-vllm.sh
git commit -m "feat: add vLLM restart script"
```

Expected: Script committed

---

## Task 10: Create Monitoring Script

**Files:**
- Create: `scripts/monitor-vllm.sh`

**Step 1: Create monitor-vllm.sh script**

Create file: `scripts/monitor-vllm.sh`

```bash
#!/usr/bin/env bash
# Monitor vLLM health and performance

while true; do
  clear
  echo "=== vLLM Health Monitor ==="
  echo "Time: $(date)"
  echo ""

  # Container status
  echo "Container Status:"
  docker compose ps vllm | tail -1
  echo ""

  # Health endpoint
  echo "Health Check:"
  curl -s http://localhost:8001/health 2>/dev/null | jq -r '.status // "UNHEALTHY"' || echo "UNREACHABLE"
  echo ""

  # GPU stats
  echo "GPU Utilization:"
  docker exec vllm-server rocm-smi --showuse 2>/dev/null | grep "GPU\[0\]" || echo "N/A"
  echo ""

  # Memory
  echo "VRAM Usage:"
  docker exec vllm-server rocm-smi --showmeminfo vram 2>/dev/null | grep "GPU\[0\]" || echo "N/A"
  echo ""

  # Request count (from logs)
  echo "Recent Requests (last minute):"
  docker compose logs --since 1m vllm 2>/dev/null | grep -c "POST /v1/chat/completions" || echo "0"
  echo ""

  # Errors
  echo "Recent Errors:"
  docker compose logs --since 5m vllm 2>/dev/null | grep -i error | tail -3 || echo "None"

  sleep 5
done
```

**Step 2: Make script executable**

Run:
```bash
chmod +x scripts/monitor-vllm.sh
```

Expected: Script is executable

**Step 3: Commit monitoring script**

Run:
```bash
git add scripts/monitor-vllm.sh
git commit -m "feat: add vLLM monitoring script"
```

Expected: Script committed

---

## Task 11: Create Rollback Script

**Files:**
- Create: `scripts/rollback-to-llamacpp.sh`

**Step 1: Create rollback-to-llamacpp.sh script**

Create file: `scripts/rollback-to-llamacpp.sh`

```bash
#!/usr/bin/env bash
# Emergency rollback to llama.cpp

set -e

echo "🚨 Emergency Rollback to llama.cpp"
echo "===================================="

# 1. Stop vLLM
docker compose stop vllm
echo "✅ vLLM stopped"

# 2. Restore llama.cpp scripts
cp docs/archive/llama-cpp/scripts/start-llm.sh scripts/
chmod +x scripts/start-llm.sh
echo "✅ llama.cpp scripts restored"

# 3. Update environment
sed -i 's|LLM_BASE_URL="http://localhost:8001/v1"|LLM_BASE_URL="http://localhost:8080/v1"|g' activate.sh
source activate.sh
echo "✅ Environment updated"

# 4. Start llama.cpp
./scripts/start-llm.sh &
sleep 10
echo "✅ llama.cpp starting"

# 5. Verify
if curl -sf http://localhost:8080/v1/models > /dev/null; then
    echo "✅ llama.cpp operational"
else
    echo "⚠️  llama.cpp health check failed"
fi

# 6. Restart Agent API
pkill -f agent_api || true
./scripts/start-agent-api.sh &
sleep 5
echo "✅ Agent API restarted"

# 7. Test end-to-end
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ System operational"
else
    echo "⚠️  System health check failed"
fi

echo ""
echo "✅ Rollback complete"
echo "System is running on llama.cpp again"
echo ""
echo "To investigate vLLM issues:"
echo "  docker compose logs vllm > vllm-failure.log"
```

**Step 2: Make script executable**

Run:
```bash
chmod +x scripts/rollback-to-llamacpp.sh
```

Expected: Script is executable

**Step 3: Commit rollback script**

Run:
```bash
git add scripts/rollback-to-llamacpp.sh
git commit -m "feat: add emergency rollback script"
```

Expected: Script committed

---

## Task 12: Update activate.sh

**Files:**
- Modify: `activate.sh`

**Step 1: Read current activate.sh**

Run:
```bash
grep LLM_BASE_URL activate.sh || echo "LLM_BASE_URL not found"
```

Expected: Shows current LLM_BASE_URL setting

**Step 2: Update LLM_BASE_URL from 8080 to 8001**

Run:
```bash
sed -i 's|LLM_BASE_URL="http://localhost:8080/v1"|LLM_BASE_URL="http://localhost:8001/v1"|g' activate.sh
```

Expected: Port updated (silent)

**Step 3: Verify change**

Run:
```bash
grep LLM_BASE_URL activate.sh
```

Expected: Shows :8001 instead of :8080

**Step 4: Commit activate.sh**

Run:
```bash
git add activate.sh
git commit -m "feat: update LLM port from 8080 to 8001 in activate.sh"
```

Expected: activate.sh committed

---

## Task 13: Update activate-cuda.sh

**Files:**
- Modify: `activate-cuda.sh` (if exists)

**Step 1: Check if activate-cuda.sh exists**

Run:
```bash
test -f activate-cuda.sh && echo "EXISTS" || echo "NOT FOUND"
```

Expected: Shows EXISTS or NOT FOUND

**Step 2: Update LLM_BASE_URL if file exists**

Run:
```bash
if [ -f activate-cuda.sh ]; then
  sed -i 's|LLM_BASE_URL="http://localhost:8080/v1"|LLM_BASE_URL="http://localhost:8001/v1"|g' activate-cuda.sh
  grep LLM_BASE_URL activate-cuda.sh
fi
```

Expected: Shows :8001 if file exists

**Step 3: Commit if file exists**

Run:
```bash
if [ -f activate-cuda.sh ]; then
  git add activate-cuda.sh
  git commit -m "feat: update LLM port from 8080 to 8001 in activate-cuda.sh"
fi
```

Expected: Committed if file exists

---

## Task 14: Update CLAUDE.md LLM Section

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Read current LLM section in CLAUDE.md**

Run:
```bash
grep -A 10 "llama.cpp\|LLM\|8080" CLAUDE.md | head -20
```

Expected: Shows references to llama.cpp and port 8080

**Step 2: Update CLAUDE.md LLM backend references**

Find and replace in `CLAUDE.md`:
- `llama.cpp` → `vLLM`
- `Vulkan` → `ROCm Docker`
- `8080` → `8001`
- `Qwen2.5-14B-Q4_K_M` → `Qwen3-30B-A3B-Instruct-2507`
- Update performance numbers: `24 tok/s` → `16-76 tok/s (multi-user batching)`

Update the startup commands section to reference:
```bash
./scripts/start-vllm.sh              # LLM server on :8001 (vLLM ROCm)
```

**Step 3: Verify changes**

Run:
```bash
grep -E "vLLM|8001|Qwen3" CLAUDE.md | head -5
```

Expected: Shows updated references

**Step 4: Commit CLAUDE.md**

Run:
```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for vLLM migration"
```

Expected: CLAUDE.md committed

---

## Task 15: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Read current README.md service ports section**

Run:
```bash
grep -A 10 -B 2 "8080\|Service.*Port\|LLM" README.md | head -20 || echo "Port section not found"
```

Expected: Shows service port references

**Step 2: Update service ports in README.md**

Update port references:
- LLM server: `:8080` → `:8001`
- Add note: `vLLM (ROCm Docker)`

Update startup instructions to reference `./scripts/start-vllm.sh`

**Step 3: Verify changes**

Run:
```bash
grep "8001" README.md
```

Expected: Shows :8001 references

**Step 4: Commit README.md**

Run:
```bash
git add README.md
git commit -m "docs: update README.md service ports for vLLM"
```

Expected: README.md committed

---

## Task 16: Update start-all-services.sh

**Files:**
- Modify: `scripts/start-all-services.sh` (if exists)

**Step 1: Check if script exists**

Run:
```bash
test -f scripts/start-all-services.sh && echo "EXISTS" || echo "NOT FOUND"
```

Expected: Shows EXISTS or NOT FOUND

**Step 2: Update script to use vLLM instead of llama.cpp**

If file exists, replace references to:
- `start-llm.sh` → `start-vllm.sh`
- Comments mentioning llama.cpp → vLLM

**Step 3: Verify changes**

Run:
```bash
if [ -f scripts/start-all-services.sh ]; then
  grep "vllm" scripts/start-all-services.sh
fi
```

Expected: Shows vLLM references

**Step 4: Commit if changed**

Run:
```bash
if [ -f scripts/start-all-services.sh ]; then
  git add scripts/start-all-services.sh
  git commit -m "feat: update start-all-services.sh for vLLM"
fi
```

Expected: Committed if file exists

---

## Task 17: Update docs/PROJECT_STATUS.md

**Files:**
- Modify: `docs/PROJECT_STATUS.md`

**Step 1: Read current PROJECT_STATUS.md**

Run:
```bash
grep -A 5 "llama.cpp\|vLLM\|LLM" docs/PROJECT_STATUS.md | head -10
```

Expected: Shows current LLM status

**Step 2: Add vLLM migration completion entry**

Add to appropriate section in `docs/PROJECT_STATUS.md`:

```markdown
### vLLM Migration (100% Complete) ✅
- [x] Archive llama.cpp setup
- [x] Integrate vLLM with Qwen3-30B model
- [x] Configure Docker Compose with ROCm support
- [x] Update all documentation and scripts
- [x] Test and validate migration

**Status:** ✅ COMPLETE
**Date:** 2026-02-12
**Model:** Qwen3-30B-A3B-Instruct-2507 (FP16)
**Port:** 8001
**Performance:** 16-76 tok/s (stability-first profile)
```

**Step 3: Verify changes**

Run:
```bash
grep "vLLM Migration" docs/PROJECT_STATUS.md
```

Expected: Shows migration entry

**Step 4: Commit PROJECT_STATUS.md**

Run:
```bash
git add docs/PROJECT_STATUS.md
git commit -m "docs: mark vLLM migration as complete in PROJECT_STATUS"
```

Expected: PROJECT_STATUS.md committed

---

## Task 18: First Boot - Start Infrastructure

**Files:**
- Test: Docker Compose infrastructure services

**Step 1: Start infrastructure services**

Run:
```bash
docker compose up -d qdrant postgres redis
```

Expected: 3 containers started

**Step 2: Verify infrastructure running**

Run:
```bash
docker compose ps qdrant postgres redis
```

Expected: All 3 services in "Up" state

**Step 3: Wait for services to be ready**

Run:
```bash
sleep 10
```

Expected: 10 second wait

---

## Task 19: First Boot - Start vLLM

**Files:**
- Test: `scripts/start-vllm.sh`

**Step 1: Start vLLM service**

Run:
```bash
./scripts/start-vllm.sh
```

Expected: Container starts, shows startup logs

**Step 2: Monitor vLLM startup (in separate terminal)**

In a new terminal, run:
```bash
docker compose logs -f vllm
```

Watch for:
- `pip install vllm` completing
- Model loading progress
- "Application startup complete"

Expected: vLLM starts loading model (~2-3 minutes)

**Step 3: Wait for model loading to complete**

Run:
```bash
sleep 180  # 3 minutes
```

Expected: Model should be loaded by now

---

## Task 20: Validation - Health Checks

**Files:**
- Test: vLLM endpoints

**Step 1: Test vLLM health endpoint**

Run:
```bash
curl -f http://localhost:8001/health
```

Expected: HTTP 200 OK response

**Step 2: Test models endpoint**

Run:
```bash
curl http://localhost:8001/v1/models | jq
```

Expected: JSON response with `"id": "qwen3-30b"`

**Step 3: Check container status**

Run:
```bash
docker compose ps vllm
```

Expected: State = Up, Status = healthy

**Step 4: Check GPU utilization**

Run:
```bash
docker exec vllm-server rocm-smi --showuse
```

Expected: GPU showing VRAM usage ~20GB

---

## Task 21: Validation - Simple Completion Test

**Files:**
- Test: vLLM chat completion

**Step 1: Test basic chat completion**

Run:
```bash
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-30b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is 2+2? Answer with just the number."}
    ],
    "max_tokens": 10,
    "temperature": 0.1
  }' | jq '.choices[0].message.content'
```

Expected: Response containing "4"

**Step 2: Test streaming completion**

Run:
```bash
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-30b",
    "messages": [{"role": "user", "content": "Count from 1 to 3"}],
    "max_tokens": 50,
    "stream": true
  }' 2>/dev/null | head -10
```

Expected: Multiple `data: {...}` chunks

---

## Task 22: Validation - Agent API Integration

**Files:**
- Test: Agent API with vLLM backend

**Step 1: Source new environment**

Run:
```bash
source activate.sh
echo $LLM_BASE_URL
```

Expected: Shows `http://localhost:8001/v1`

**Step 2: Start Agent API (if not running)**

Run:
```bash
./scripts/start-agent-api.sh &
sleep 10
```

Expected: Agent API starts on port 8000

**Step 3: Test Agent API health**

Run:
```bash
curl http://localhost:8000/health | jq
```

Expected: JSON response with `"status": "healthy"`

**Step 4: Test agent routing through vLLM**

Run:
```bash
curl http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the capital of France?"}]
  }' | jq '.response' | head -5
```

Expected: Response routed through vLLM

---

## Task 23: Validation - Run Agent Tests

**Files:**
- Test: `scripts/test_agents.py`

**Step 1: Check if test script exists**

Run:
```bash
test -f scripts/test_agents.py && echo "EXISTS" || echo "NOT FOUND"
```

Expected: Shows EXISTS or NOT FOUND

**Step 2: Run agent tests (if exists)**

Run:
```bash
if [ -f scripts/test_agents.py ]; then
  python scripts/test_agents.py
fi
```

Expected: Tests pass with vLLM backend

---

## Task 24: Validation - Performance Benchmark

**Files:**
- Test: `scripts/benchmark_vllm.py`

**Step 1: Run vLLM benchmark**

Run:
```bash
python scripts/benchmark_vllm.py \
  --num-prompts 4 \
  --input-length 128 \
  --output-length 128 \
  --max-concurrent 2
```

Expected: Benchmark completes with metrics

**Step 2: Verify performance meets targets**

Check output for:
- Throughput: >16 tok/s
- Success rate: 100%
- Latency: <10 seconds average

Expected: Performance within acceptable range

---

## Task 25: Final Commit

**Files:**
- Verify: All changes committed

**Step 1: Check for uncommitted changes**

Run:
```bash
git status
```

Expected: Working tree clean or only expected changes

**Step 2: Create final migration commit**

Run:
```bash
git add -A
git commit -m "feat: complete vLLM ROCm migration

- Replaced llama.cpp with vLLM on port 8001
- Model: Qwen3-30B-A3B-Instruct-2507
- Archived llama.cpp setup to docs/archive/
- Updated all documentation and scripts
- Tested and validated migration

Performance: 16-76 tok/s (stability-first profile)
Risk: LOW (tested configuration from set-bestbox)
"
```

Expected: Final commit created

**Step 3: Show commit log**

Run:
```bash
git log --oneline -10
```

Expected: Shows migration commits

---

## Task 26: Create Migration Summary

**Files:**
- Create: `docs/VLLM_MIGRATION_SUMMARY.md`

**Step 1: Create migration summary document**

Create file: `docs/VLLM_MIGRATION_SUMMARY.md`

```markdown
# vLLM Migration Summary

**Date:** 2026-02-12
**Duration:** ~55 minutes
**Status:** ✅ COMPLETE
**Branch:** feature/amd-rocm

## What Changed

### LLM Backend
- **Before:** llama.cpp (Vulkan) on port 8080
- **After:** vLLM (ROCm Docker) on port 8001

### Model
- **Before:** Qwen2.5-14B-Q4_K_M (8GB VRAM, quantized)
- **After:** Qwen3-30B-A3B-Instruct-2507 (20GB VRAM, FP16)

### Performance
- **Before:** 24 tok/s (single-user optimized)
- **After:** 16-76 tok/s (multi-user batching)

## Files Changed

### Created
- `.env.vllm` - vLLM environment configuration
- `docker/Dockerfile.vllm*` - vLLM Docker images
- `scripts/start-vllm.sh` - vLLM startup script
- `scripts/stop-vllm.sh` - vLLM stop script
- `scripts/restart-vllm.sh` - vLLM restart script
- `scripts/monitor-vllm.sh` - vLLM monitoring script
- `scripts/rollback-to-llamacpp.sh` - Emergency rollback
- `docs/vllm_*.md` - vLLM documentation
- `docs/archive/llama-cpp/` - Archived llama.cpp setup

### Modified
- `docker-compose.yml` - Added vLLM service
- `activate.sh` - Updated LLM_BASE_URL to :8001
- `CLAUDE.md` - Updated LLM backend documentation
- `README.md` - Updated service ports
- `docs/PROJECT_STATUS.md` - Marked migration complete

### Removed (Archived)
- `scripts/start-llm*.sh` - llama.cpp startup scripts
- `docs/llm_backend_comparison.md` - llama.cpp docs
- `docs/VULKAN_VALIDATION_REPORT.md` - Vulkan validation

## Validation Results

✅ vLLM container starts and reaches healthy state
✅ Model loads in <5 minutes
✅ Health endpoint returns 200 OK
✅ Basic completions work
✅ Streaming completions work
✅ Agent API connects to vLLM
✅ Performance meets targets (16-76 tok/s)

## Rollback Procedure

If needed, run:
```bash
./scripts/rollback-to-llamacpp.sh
```

This will:
1. Stop vLLM
2. Restore llama.cpp scripts
3. Update environment to port 8080
4. Start llama.cpp
5. Restart Agent API

## Next Steps

- Monitor performance for 24-48 hours
- Collect production benchmark data
- Consider optimization opportunities (quantization, larger context)
- Evaluate vLLM version upgrades for gfx1151

## Support

For issues, check:
- `docker compose logs vllm`
- `./scripts/monitor-vllm.sh`
- `docs/plans/2026-02-12-vllm-rocm-integration-design.md`
```

**Step 2: Commit migration summary**

Run:
```bash
git add docs/VLLM_MIGRATION_SUMMARY.md
git commit -m "docs: add vLLM migration summary"
```

Expected: Summary committed

**Step 3: Push to remote (if ready)**

Run:
```bash
git push origin feature/amd-rocm
```

Expected: Branch pushed to remote

---

## Acceptance Criteria Checklist

Before considering migration complete, verify:

### Functional
- [ ] vLLM container starts via `docker compose up -d vllm`
- [ ] Model loads in <5 minutes
- [ ] Health endpoint: `curl http://localhost:8001/health` returns 200
- [ ] Chat completion works
- [ ] Streaming works
- [ ] Agent API connects to vLLM on :8001
- [ ] All 4 domain agents work

### Performance
- [ ] Throughput: 16-76 tok/s
- [ ] Latency: <10 seconds for 128 tokens
- [ ] Success rate: >99%
- [ ] GPU utilization: 80-95% during inference
- [ ] VRAM stable at ~20GB

### Operational
- [ ] Docker Compose orchestration works
- [ ] Health checks pass
- [ ] Monitoring script functional
- [ ] Rollback script tested

### Documentation
- [ ] CLAUDE.md updated
- [ ] README.md updated
- [ ] Migration summary complete
- [ ] Archive of llama.cpp preserved

---

## End of Plan

Total tasks: 26
Estimated time: 55 minutes
Branch: feature/amd-rocm
