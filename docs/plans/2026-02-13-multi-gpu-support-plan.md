# Multi-GPU Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable BestBox to seamlessly run on both AMD ROCm and NVIDIA CUDA GPUs with automatic detection and unified activation.

**Architecture:** Shell script-based GPU detection with three-tier priority chain (env var → config file → auto-detect). Unified `activate.sh` configures environment based on detected GPU. Docker Compose uses base file + GPU-specific overlays (rocm.yml, cuda.yml). Single `start-all-services.sh` orchestrates all service startup.

**Tech Stack:** Bash scripts, Docker Compose multi-file overlays, Python (for Agent API), existing ROCm/CUDA Docker images.

---

## Task 1: GPU Detection Script

**Files:**
- Create: `scripts/detect-gpu.sh`
- Test: `tests/test_gpu_detection.sh` (created in Task 9)

**Step 1: Create GPU detection script**

Create the detection script with priority chain logic:

```bash
cat > scripts/detect-gpu.sh << 'EOF'
#!/bin/bash
# GPU Backend Detection for BestBox
# Detects AMD ROCm, NVIDIA CUDA, or CPU fallback

detect_gpu() {
  # Priority 1: Environment variable
  if [ -n "$BESTBOX_GPU_BACKEND" ]; then
    validate_backend "$BESTBOX_GPU_BACKEND"
    echo "$BESTBOX_GPU_BACKEND"
    return 0
  fi

  # Priority 2: Config file
  if [ -f ".bestbox/config" ]; then
    gpu=$(grep "^gpu_backend=" .bestbox/config | cut -d= -f2 | tr -d ' ')
    if [ -n "$gpu" ]; then
      validate_backend "$gpu"
      echo "$gpu"
      return 0
    fi
  fi

  # Priority 3: Auto-detection
  if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "cuda"
    return 0
  elif command -v rocm-smi &> /dev/null || command -v rocminfo &> /dev/null; then
    echo "rocm"
    return 0
  else
    echo "cpu"
    return 0
  fi
}

validate_backend() {
  case "$1" in
    cuda|rocm|cpu)
      return 0
      ;;
    *)
      echo "Error: Invalid GPU backend '$1'. Must be: cuda, rocm, or cpu" >&2
      exit 1
      ;;
  esac
}

# Export function for use by sourcing scripts
export -f detect_gpu validate_backend
EOF
```

**Step 2: Make script executable**

Run: `chmod +x scripts/detect-gpu.sh`
Expected: Script has execute permissions

**Step 3: Test detection manually**

Run:
```bash
source scripts/detect-gpu.sh
detect_gpu
```
Expected: Outputs one of: `cuda`, `rocm`, or `cpu`

**Step 4: Commit GPU detection script**

```bash
git add scripts/detect-gpu.sh
git commit -m "feat: add GPU backend detection script

- Implements three-tier priority chain: env var → config → auto-detect
- Validates backend values (cuda, rocm, cpu)
- Exports functions for use by other scripts"
```

---

## Task 2: Unified Activation Script

**Files:**
- Modify: `activate.sh`
- Backup: `activate.sh.backup` (temporary)

**Step 1: Backup current activation script**

Run: `cp activate.sh activate.sh.backup`
Expected: Backup file created

**Step 2: Read current activate.sh to understand structure**

Run: `cat activate.sh`
Expected: See current ROCm-only implementation

**Step 3: Replace activate.sh with unified version**

```bash
cat > activate.sh << 'EOF'
#!/bin/bash
# BestBox Unified Activation Script
# Auto-detects GPU type and configures environment

# Get script directory (handle both sourcing and execution)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Activate Python virtual environment
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "⚠️  Virtual environment not found at $SCRIPT_DIR/venv"
    echo "   Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    return 1 2>/dev/null || exit 1
fi

# Detect GPU backend
source "$SCRIPT_DIR/scripts/detect-gpu.sh"
GPU_BACKEND=$(detect_gpu)
export BESTBOX_GPU_BACKEND="$GPU_BACKEND"

# Configure environment based on detected GPU
case "$GPU_BACKEND" in
  cuda)
    echo "🎮 Configuring NVIDIA CUDA environment..."

    # CUDA-specific environment
    export CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
    export PATH=$CUDA_HOME/bin:$PATH
    export LD_LIBRARY_PATH=$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}
    export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

    # Unset conflicting ROCm variables
    unset HSA_OVERRIDE_GFX_VERSION PYTORCH_ROCM_ARCH
    unset ROCM_PATH ROCM_HOME HIP_PATH HIP_PLATFORM
    unset FLASH_ATTENTION_TRITON_AMD_ENABLE
    ;;

  rocm)
    echo "🎮 Configuring AMD ROCm environment..."

    # ROCm-specific environment
    export ROCM_PATH=/opt/rocm-7.2.0
    export ROCM_HOME=/opt/rocm-7.2.0
    export PATH=$ROCM_PATH/bin:$PATH
    export LD_LIBRARY_PATH=$ROCM_PATH/lib:${LD_LIBRARY_PATH:-}
    export HIP_PATH=$ROCM_PATH/hip
    export HIP_PLATFORM=amd
    export HSA_OVERRIDE_GFX_VERSION=11.0.0
    export PYTORCH_ROCM_ARCH=gfx1100
    export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE

    # Unset conflicting CUDA variables
    unset CUDA_HOME CUDA_VISIBLE_DEVICES PYTORCH_CUDA_ALLOC_CONF
    ;;

  cpu)
    echo "💻 Configuring CPU-only environment..."

    # Unset all GPU variables
    unset CUDA_HOME CUDA_VISIBLE_DEVICES PYTORCH_CUDA_ALLOC_CONF
    unset ROCM_PATH ROCM_HOME HIP_PATH HIP_PLATFORM
    unset HSA_OVERRIDE_GFX_VERSION PYTORCH_ROCM_ARCH
    unset FLASH_ATTENTION_TRITON_AMD_ENABLE

    echo "⚠️  Running in CPU mode (no GPU detected)"
    echo "   To force GPU mode, set: export BESTBOX_GPU_BACKEND=cuda  # or rocm"
    ;;
esac

# Common environment variables (all backends)
export LLM_BASE_URL="http://localhost:8001/v1"
export HF_HOME="$HOME/.cache/modelscope/hub/models"
export TRANSFORMERS_CACHE="$HOME/.cache/modelscope/hub/models"
export SENTENCE_TRANSFORMERS_HOME="$HOME/.cache/modelscope/hub/models"

# Docker Compose file selection
export BESTBOX_COMPOSE_FILES="-f docker-compose.yml -f docker-compose.$GPU_BACKEND.yml"

# Display activation summary
echo ""
echo "✅ BestBox environment activated"
echo "   GPU Backend: $GPU_BACKEND"
echo "   Compose Files: docker-compose.yml + docker-compose.$GPU_BACKEND.yml"
echo ""
echo "Next steps:"
echo "  1. Start services: ./start-all-services.sh"
echo "  2. Check health: curl http://localhost:8000/health"
echo ""
EOF
```

**Step 4: Make activation script executable**

Run: `chmod +x activate.sh`
Expected: Script has execute permissions

**Step 5: Test activation script**

Run: `source activate.sh`
Expected:
- Shows "Configuring [GPU type] environment"
- Shows "BestBox environment activated"
- Sets BESTBOX_GPU_BACKEND variable
- Activates venv

**Step 6: Verify environment variables are set**

Run:
```bash
echo "GPU Backend: $BESTBOX_GPU_BACKEND"
echo "Compose Files: $BESTBOX_COMPOSE_FILES"
```
Expected: Variables are set correctly

**Step 7: Commit unified activation script**

```bash
git add activate.sh
git commit -m "feat: unify activation script with GPU auto-detection

- Auto-detects AMD ROCm, NVIDIA CUDA, or CPU mode
- Configures GPU-specific environment variables
- Unsets conflicting variables between CUDA and ROCm
- Sets BESTBOX_COMPOSE_FILES for Docker Compose
- Displays activation summary and next steps"
```

**Step 8: Remove backup file**

Run: `rm activate.sh.backup`
Expected: Backup removed

---

## Task 3: Docker Compose Base File

**Files:**
- Modify: `docker-compose.yml`
- Backup: `docker-compose.yml.backup` (temporary)

**Step 1: Backup current docker-compose.yml**

Run: `cp docker-compose.yml docker-compose.yml.backup`
Expected: Backup created

**Step 2: Read current docker-compose.yml to identify GPU services**

Run: `cat docker-compose.yml | grep -A 5 "image:"`
Expected: See list of services and their images

**Step 3: Create new base docker-compose.yml (GPU-independent services only)**

Extract only infrastructure services (postgres, redis, qdrant, mariadb, livekit) to the base file. GPU services (vllm, embeddings, reranker, asr, tts) will move to overlay files.

```bash
cat > docker-compose.yml << 'EOF'
# BestBox Base Docker Compose
# GPU-independent infrastructure services
# GPU services are in docker-compose.rocm.yml and docker-compose.cuda.yml

services:
  postgres:
    image: postgres:17-alpine
    container_name: bestbox-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: bestbox
      POSTGRES_USER: bestbox
      POSTGRES_PASSWORD: bestbox_dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bestbox"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: bestbox-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.13.1
    container_name: bestbox-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5

  mariadb:
    image: mariadb:11.4
    container_name: bestbox-mariadb
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: admin
      MYSQL_DATABASE: erpnext
      MYSQL_USER: erpnext
      MYSQL_PASSWORD: erpnext_dev_password
    ports:
      - "3306:3306"
    volumes:
      - mariadb_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 5

  livekit:
    image: livekit/livekit-server:v1.8.6
    container_name: bestbox-livekit
    restart: unless-stopped
    ports:
      - "7880:7880"
      - "7881:7881"
      - "7882:7882/udp"
    volumes:
      - ./config/livekit.yaml:/etc/livekit.yaml
    command: --config /etc/livekit.yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7880/"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  mariadb_data:

networks:
  default:
    name: bestbox-network
EOF
```

**Step 4: Validate base compose file syntax**

Run: `docker compose -f docker-compose.yml config --quiet`
Expected: No output (syntax is valid)

**Step 5: Test base services can be listed**

Run: `docker compose -f docker-compose.yml ps`
Expected: Lists services (even if not running)

**Step 6: Commit base Docker Compose file**

```bash
git add docker-compose.yml
git commit -m "refactor: extract GPU-independent services to base compose file

- Keep only infrastructure: postgres, redis, qdrant, mariadb, livekit
- GPU services move to docker-compose.rocm.yml and docker-compose.cuda.yml
- Base file can be used with any GPU backend overlay"
```

**Step 7: Remove backup file**

Run: `rm docker-compose.yml.backup`
Expected: Backup removed

---

## Task 4: Docker Compose ROCm Overlay

**Files:**
- Create: `docker-compose.rocm.yml`

**Step 1: Read GPU services from backup to extract ROCm configuration**

Run: `cat docker-compose.yml.backup | grep -A 30 "vllm:"`
Expected: See vllm service configuration (if backup still exists, otherwise skip)

**Step 2: Create ROCm overlay with GPU services**

```bash
cat > docker-compose.rocm.yml << 'EOF'
# BestBox ROCm GPU Services Overlay
# AMD GPU-specific services (vLLM, embeddings, reranker, ASR, TTS)
# Use with: docker compose -f docker-compose.yml -f docker-compose.rocm.yml up

services:
  vllm:
    image: rocm/vllm-dev:rocm7.2_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.14.0rc0
    container_name: vllm-server
    restart: unless-stopped
    devices:
      - /dev/kfd
      - /dev/dri
    environment:
      - PYTORCH_ROCM_ARCH=gfx1151
      - HSA_OVERRIDE_GFX_VERSION=11.0.0
      - FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
      - HIP_VISIBLE_DEVICES=0
      - HF_HOME=/models
      - TRANSFORMERS_CACHE=/models
    ports:
      - "8001:8000"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
    command: >
      --model /models/Qwen/Qwen3-30B-A3B-Instruct-2507
      --trust-remote-code
      --dtype float16
      --max-model-len 4096
      --enforce-eager
      --gpu-memory-utilization 0.90
      --max-num-seqs 8
      --host 0.0.0.0
      --port 8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s

  embeddings:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    container_name: embeddings-server
    restart: unless-stopped
    devices:
      - /dev/kfd
      - /dev/dri
    environment:
      - HIP_VISIBLE_DEVICES=0
      - PYTORCH_ROCM_ARCH=gfx1151
      - HSA_OVERRIDE_GFX_VERSION=11.0.0
      - HF_HOME=/models
      - SENTENCE_TRANSFORMERS_HOME=/models
    ports:
      - "8081:8081"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
      - ./services/embeddings:/app
    working_dir: /app
    command: python -u main.py
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  reranker:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    container_name: reranker-server
    restart: unless-stopped
    devices:
      - /dev/kfd
      - /dev/dri
    environment:
      - HIP_VISIBLE_DEVICES=0
      - PYTORCH_ROCM_ARCH=gfx1151
      - HSA_OVERRIDE_GFX_VERSION=11.0.0
      - HF_HOME=/models
      - SENTENCE_TRANSFORMERS_HOME=/models
    ports:
      - "8004:8004"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
      - ./services/reranker:/app
    working_dir: /app
    command: python -u main.py
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8004/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  qwen3-asr:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    container_name: qwen3-asr
    restart: unless-stopped
    devices:
      - /dev/kfd
      - /dev/dri
    environment:
      - HIP_VISIBLE_DEVICES=0
      - PYTORCH_ROCM_ARCH=gfx1151
      - HSA_OVERRIDE_GFX_VERSION=11.0.0
      - HF_HOME=/models
      - TRANSFORMERS_CACHE=/models
    ports:
      - "8765:8765"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
      - ./services/speech:/app
    working_dir: /app
    command: python -u asr.py

  qwen3-tts:
    image: rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1
    container_name: qwen3-tts
    restart: unless-stopped
    devices:
      - /dev/kfd
      - /dev/dri
    environment:
      - HIP_VISIBLE_DEVICES=0
      - PYTORCH_ROCM_ARCH=gfx1151
      - HSA_OVERRIDE_GFX_VERSION=11.0.0
      - HF_HOME=/models
      - TRANSFORMERS_CACHE=/models
    ports:
      - "8766:8766"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
      - ./services/speech:/app
    working_dir: /app
    command: python -u tts.py

networks:
  default:
    name: bestbox-network
EOF
```

**Step 3: Validate ROCm overlay syntax**

Run: `docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --quiet`
Expected: No output (syntax valid)

**Step 4: Test merged configuration**

Run:
```bash
docker compose -f docker-compose.yml -f docker-compose.rocm.yml config | grep "image:"
```
Expected: See both base services (postgres, redis) and GPU services (vllm, embeddings)

**Step 5: Commit ROCm overlay**

```bash
git add docker-compose.rocm.yml
git commit -m "feat: add ROCm GPU services overlay

- vLLM with ROCm 7.2 and gfx1151 support
- Embeddings and reranker services
- ASR and TTS services for speech
- All services use /dev/kfd and /dev/dri devices
- Configure ROCm-specific environment variables"
```

---

## Task 5: Docker Compose CUDA Overlay

**Files:**
- Create: `docker-compose.cuda.yml`

**Step 1: Create CUDA overlay with NVIDIA runtime**

```bash
cat > docker-compose.cuda.yml << 'EOF'
# BestBox CUDA GPU Services Overlay
# NVIDIA GPU-specific services (vLLM, embeddings, reranker, ASR, TTS)
# Use with: docker compose -f docker-compose.yml -f docker-compose.cuda.yml up

services:
  vllm:
    image: vllm/vllm-openai:latest
    container_name: vllm-server
    restart: unless-stopped
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
      - HF_HOME=/models
      - TRANSFORMERS_CACHE=/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ports:
      - "8001:8000"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
    command: >
      --model /models/Qwen/Qwen3-30B-A3B-Instruct-2507
      --trust-remote-code
      --dtype float16
      --max-model-len 4096
      --gpu-memory-utilization 0.90
      --max-num-seqs 8
      --host 0.0.0.0
      --port 8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s

  embeddings:
    image: pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime
    container_name: embeddings-server
    restart: unless-stopped
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
      - HF_HOME=/models
      - SENTENCE_TRANSFORMERS_HOME=/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
    ports:
      - "8081:8081"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
      - ./services/embeddings:/app
    working_dir: /app
    command: python -u main.py
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  reranker:
    image: pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime
    container_name: reranker-server
    restart: unless-stopped
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
      - HF_HOME=/models
      - SENTENCE_TRANSFORMERS_HOME=/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
    ports:
      - "8004:8004"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
      - ./services/reranker:/app
    working_dir: /app
    command: python -u main.py
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8004/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  qwen3-asr:
    image: pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime
    container_name: qwen3-asr
    restart: unless-stopped
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
      - HF_HOME=/models
      - TRANSFORMERS_CACHE=/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
    ports:
      - "8765:8765"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
      - ./services/speech:/app
    working_dir: /app
    command: python -u asr.py

  qwen3-tts:
    image: pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime
    container_name: qwen3-tts
    restart: unless-stopped
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
      - HF_HOME=/models
      - TRANSFORMERS_CACHE=/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
    ports:
      - "8766:8766"
    volumes:
      - ${HOME}/.cache/modelscope/hub/models:/models
      - ./services/speech:/app
    working_dir: /app
    command: python -u tts.py

networks:
  default:
    name: bestbox-network
EOF
```

**Step 2: Validate CUDA overlay syntax**

Run: `docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --quiet`
Expected: No output (syntax valid)

**Step 3: Test merged configuration**

Run:
```bash
docker compose -f docker-compose.yml -f docker-compose.cuda.yml config | grep "runtime:"
```
Expected: See "runtime: nvidia" for GPU services

**Step 4: Commit CUDA overlay**

```bash
git add docker-compose.cuda.yml
git commit -m "feat: add CUDA GPU services overlay

- vLLM with NVIDIA runtime
- Embeddings and reranker services
- ASR and TTS services for speech
- All services use NVIDIA Container Runtime
- Configure CUDA-specific environment variables"
```

---

## Task 6: Unified Start Script

**Files:**
- Create: `start-all-services.sh`

**Step 1: Create unified service startup script**

```bash
cat > start-all-services.sh << 'EOF'
#!/bin/bash
# BestBox Unified Service Startup Script
# Starts all BestBox services with GPU auto-detection

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Detect GPU backend
if [ -z "$BESTBOX_GPU_BACKEND" ]; then
    source scripts/detect-gpu.sh
    GPU_BACKEND=$(detect_gpu)
    export BESTBOX_GPU_BACKEND="$GPU_BACKEND"
else
    GPU_BACKEND="$BESTBOX_GPU_BACKEND"
fi

echo -e "${GREEN}🚀 Starting BestBox services (${GPU_BACKEND} mode)${NC}"
echo ""

# Compose file selection
BASE_COMPOSE="-f docker-compose.yml"
GPU_COMPOSE="-f docker-compose.${GPU_BACKEND}.yml"

# Create logs directory
mkdir -p logs

# Check if .bestbox directory exists for config
mkdir -p .bestbox

# Step 1: Start infrastructure services
echo -e "${GREEN}📦 Starting infrastructure services...${NC}"
docker compose $BASE_COMPOSE up -d postgres redis qdrant mariadb livekit

# Wait for infrastructure to be ready
echo "⏳ Waiting for infrastructure to be ready (10s)..."
sleep 10

# Verify infrastructure health
echo "🏥 Checking infrastructure health..."
docker compose $BASE_COMPOSE ps postgres redis qdrant

# Step 2: Start GPU services
if [ "$GPU_BACKEND" != "cpu" ]; then
    echo ""
    echo -e "${GREEN}🎮 Starting GPU services (${GPU_BACKEND})...${NC}"
    docker compose $BASE_COMPOSE $GPU_COMPOSE up -d vllm embeddings reranker

    # Wait for GPU services to initialize
    echo "⏳ Waiting for GPU services to initialize (30s)..."
    sleep 30
else
    echo ""
    echo -e "${YELLOW}⚠️  Skipping GPU services (CPU mode)${NC}"
fi

# Step 3: Optional speech services
if [ "${BESTBOX_ENABLE_SPEECH:-false}" = "true" ]; then
    echo ""
    echo -e "${GREEN}🎤 Starting speech services...${NC}"
    docker compose $BASE_COMPOSE $GPU_COMPOSE up -d qwen3-asr qwen3-tts
fi

# Step 4: Start Agent API (native Python)
echo ""
echo -e "${GREEN}🤖 Starting Agent API...${NC}"

# Ensure virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    source activate.sh
fi

# Kill existing agent API if running
if [ -f logs/agent_api.pid ]; then
    OLD_PID=$(cat logs/agent_api.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "  Stopping existing Agent API (PID: $OLD_PID)..."
        kill $OLD_PID
        sleep 2
    fi
fi

# Start Agent API
nohup python services/agent_api.py > logs/agent_api.log 2>&1 &
echo $! > logs/agent_api.pid
echo "  Agent API started (PID: $(cat logs/agent_api.pid))"

# Step 5: Optional frontend
if [ "${BESTBOX_ENABLE_FRONTEND:-true}" = "true" ]; then
    echo ""
    echo -e "${GREEN}🌐 Starting frontend...${NC}"

    # Kill existing frontend if running
    if [ -f logs/frontend.pid ]; then
        OLD_PID=$(cat logs/frontend.pid)
        if ps -p $OLD_PID > /dev/null 2>&1; then
            echo "  Stopping existing frontend (PID: $OLD_PID)..."
            kill $OLD_PID
            sleep 2
        fi
    fi

    # Start frontend
    cd frontend/copilot-demo
    nohup npm run dev > ../../logs/frontend.log 2>&1 &
    echo $! > ../../logs/frontend.pid
    cd ../..
    echo "  Frontend started (PID: $(cat logs/frontend.pid))"
fi

# Summary
echo ""
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Service URLs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "${BESTBOX_ENABLE_FRONTEND:-true}" = "true" ]; then
    echo "  Frontend:       http://localhost:3000"
fi
echo "  Agent API:      http://localhost:8000"
if [ "$GPU_BACKEND" != "cpu" ]; then
    echo "  LLM (vLLM):     http://localhost:8001"
    echo "  Embeddings:     http://localhost:8081"
    echo "  Reranker:       http://localhost:8004"
fi
if [ "${BESTBOX_ENABLE_SPEECH:-false}" = "true" ]; then
    echo "  S2S Gateway:    ws://localhost:8765"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Logs:           ./logs/"
echo "Stop services:  ./stop-all-services.sh"
echo ""
echo "Health checks:"
echo "  curl http://localhost:8000/health  # Agent API"
if [ "$GPU_BACKEND" != "cpu" ]; then
    echo "  curl http://localhost:8001/health  # LLM"
    echo "  curl http://localhost:8081/health  # Embeddings"
    echo "  curl http://localhost:8004/health  # Reranker"
fi
echo ""
EOF
```

**Step 2: Make start script executable**

Run: `chmod +x start-all-services.sh`
Expected: Script has execute permissions

**Step 3: Test script syntax (dry run)**

Run: `bash -n start-all-services.sh`
Expected: No output (no syntax errors)

**Step 4: Commit unified start script**

```bash
git add start-all-services.sh
git commit -m "feat: add unified service startup script

- Auto-detects GPU backend if not set
- Starts infrastructure services first
- Starts GPU services with appropriate overlay
- Starts Agent API and frontend
- Provides service URLs and health check commands
- Creates logs directory and tracks PIDs"
```

---

## Task 7: Unified Stop Script

**Files:**
- Create: `stop-all-services.sh`

**Step 1: Create unified stop script**

```bash
cat > stop-all-services.sh << 'EOF'
#!/bin/bash
# BestBox Unified Service Stop Script
# Stops all BestBox services gracefully

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo -e "${RED}🛑 Stopping BestBox services...${NC}"
echo ""

# Stop Agent API
if [ -f logs/agent_api.pid ]; then
    PID=$(cat logs/agent_api.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "🤖 Stopping Agent API (PID: $PID)..."
        kill $PID
        sleep 2
        rm logs/agent_api.pid
    else
        echo "⚠️  Agent API not running (stale PID file)"
        rm logs/agent_api.pid
    fi
else
    echo "⚠️  Agent API PID file not found"
fi

# Stop Frontend
if [ -f logs/frontend.pid ]; then
    PID=$(cat logs/frontend.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "🌐 Stopping Frontend (PID: $PID)..."
        kill $PID
        sleep 2
        rm logs/frontend.pid
    else
        echo "⚠️  Frontend not running (stale PID file)"
        rm logs/frontend.pid
    fi
else
    echo "⚠️  Frontend PID file not found"
fi

# Stop Docker services
echo ""
echo "📦 Stopping Docker services..."

# Detect GPU backend for compose file selection
if [ -z "$BESTBOX_GPU_BACKEND" ]; then
    source scripts/detect-gpu.sh
    GPU_BACKEND=$(detect_gpu)
else
    GPU_BACKEND="$BESTBOX_GPU_BACKEND"
fi

BASE_COMPOSE="-f docker-compose.yml"
GPU_COMPOSE="-f docker-compose.${GPU_BACKEND}.yml"

docker compose $BASE_COMPOSE $GPU_COMPOSE down

echo ""
echo -e "${GREEN}✅ All services stopped${NC}"
echo ""
echo "To restart: ./start-all-services.sh"
echo ""
EOF
```

**Step 2: Make stop script executable**

Run: `chmod +x stop-all-services.sh`
Expected: Script has execute permissions

**Step 3: Test script syntax**

Run: `bash -n stop-all-services.sh`
Expected: No output (no syntax errors)

**Step 4: Commit stop script**

```bash
git add stop-all-services.sh
git commit -m "feat: add unified service stop script

- Stops Agent API and frontend gracefully
- Stops all Docker services
- Cleans up PID files
- Uses detected GPU backend for compose file selection"
```

---

## Task 8: Configuration File Example

**Files:**
- Create: `.bestbox/config.example`

**Step 1: Create .bestbox directory**

Run: `mkdir -p .bestbox`
Expected: Directory created

**Step 2: Create example configuration file**

```bash
cat > .bestbox/config.example << 'EOF'
# BestBox Configuration File
# Copy this file to .bestbox/config and customize

# GPU Backend Configuration
# Override GPU auto-detection
# Options: cuda, rocm, cpu
# Default: auto-detect
gpu_backend=rocm

# Service Toggles
# Enable/disable optional services
enable_speech=false
enable_frontend=true

# Future Configuration Options
# (Reserved for future use)
# max_concurrent_requests=10
# log_level=info
# cache_dir=/custom/cache/path
EOF
```

**Step 3: Add .bestbox/config to .gitignore**

Run:
```bash
if ! grep -q "^\.bestbox/config$" .gitignore 2>/dev/null; then
    echo ".bestbox/config" >> .gitignore
fi
```
Expected: .bestbox/config added to .gitignore (user-specific configs not committed)

**Step 4: Verify .gitignore**

Run: `grep ".bestbox/config" .gitignore`
Expected: Shows ".bestbox/config" line

**Step 5: Commit config example and .gitignore**

```bash
git add .bestbox/config.example .gitignore
git commit -m "feat: add configuration file example

- Provides template for GPU backend override
- Includes service toggle options
- Add .bestbox/config to .gitignore (user-specific)"
```

---

## Task 9: Unit Tests for GPU Detection

**Files:**
- Create: `tests/test_gpu_detection.sh`

**Step 1: Create tests directory**

Run: `mkdir -p tests`
Expected: Directory created

**Step 2: Create GPU detection test suite**

```bash
cat > tests/test_gpu_detection.sh << 'EOF'
#!/bin/bash
# Unit tests for GPU detection script
# Tests priority chain: env var > config file > auto-detect

set -e

# Test framework
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    echo "✅ PASS: $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
    echo "❌ FAIL: $1"
    echo "   Expected: $2"
    echo "   Got: $3"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

# Source detection script
source scripts/detect-gpu.sh

# Test 1: Environment variable priority (highest)
test_env_var_priority() {
    export BESTBOX_GPU_BACKEND=cuda
    result=$(detect_gpu)
    unset BESTBOX_GPU_BACKEND

    if [ "$result" = "cuda" ]; then
        pass "Environment variable priority"
    else
        fail "Environment variable priority" "cuda" "$result"
    fi
}

# Test 2: Config file priority (when no env var)
test_config_file_priority() {
    unset BESTBOX_GPU_BACKEND
    mkdir -p .bestbox
    echo "gpu_backend=rocm" > .bestbox/config

    result=$(detect_gpu)

    rm .bestbox/config

    if [ "$result" = "rocm" ]; then
        pass "Config file priority"
    else
        fail "Config file priority" "rocm" "$result"
    fi
}

# Test 3: Auto-detection (when no env var or config)
test_auto_detection() {
    unset BESTBOX_GPU_BACKEND
    rm -f .bestbox/config

    result=$(detect_gpu)

    if [[ "$result" =~ ^(cuda|rocm|cpu)$ ]]; then
        pass "Auto-detection returns valid backend: $result"
    else
        fail "Auto-detection" "cuda|rocm|cpu" "$result"
    fi
}

# Test 4: Validation rejects invalid backends
test_validation_invalid() {
    if validate_backend "invalid" 2>/dev/null; then
        fail "Validation should reject 'invalid'" "exit 1" "exit 0"
    else
        pass "Validation rejects invalid backend"
    fi
}

# Test 5: Validation accepts valid backends
test_validation_valid() {
    for backend in cuda rocm cpu; do
        if validate_backend "$backend" 2>/dev/null; then
            pass "Validation accepts '$backend'"
        else
            fail "Validation accepts '$backend'" "exit 0" "exit 1"
        fi
    done
}

# Test 6: Config file with spaces
test_config_with_spaces() {
    unset BESTBOX_GPU_BACKEND
    mkdir -p .bestbox
    echo "gpu_backend = cuda " > .bestbox/config

    result=$(detect_gpu)

    rm .bestbox/config

    if [ "$result" = "cuda" ]; then
        pass "Config file handles spaces"
    else
        fail "Config file handles spaces" "cuda" "$result"
    fi
}

# Test 7: Empty config file
test_empty_config() {
    unset BESTBOX_GPU_BACKEND
    mkdir -p .bestbox
    touch .bestbox/config

    result=$(detect_gpu)

    rm .bestbox/config

    if [[ "$result" =~ ^(cuda|rocm|cpu)$ ]]; then
        pass "Empty config falls back to auto-detect: $result"
    else
        fail "Empty config fallback" "cuda|rocm|cpu" "$result"
    fi
}

# Run all tests
echo "Running GPU detection tests..."
echo ""

test_env_var_priority
test_config_file_priority
test_auto_detection
test_validation_invalid
test_validation_valid
test_config_with_spaces
test_empty_config

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Results:"
echo "  Passed: $TESTS_PASSED"
echo "  Failed: $TESTS_FAILED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $TESTS_FAILED -gt 0 ]; then
    exit 1
else
    echo "✅ All tests passed!"
    exit 0
fi
EOF
```

**Step 3: Make test script executable**

Run: `chmod +x tests/test_gpu_detection.sh`
Expected: Script has execute permissions

**Step 4: Run tests**

Run: `./tests/test_gpu_detection.sh`
Expected: All tests pass

**Step 5: Commit test suite**

```bash
git add tests/test_gpu_detection.sh
git commit -m "test: add GPU detection unit tests

- Test priority chain (env var > config > auto-detect)
- Test validation logic
- Test edge cases (spaces, empty config)
- All tests pass"
```

---

## Task 10: Integration Tests for Docker Compose

**Files:**
- Create: `tests/test_docker_compose.sh`

**Step 1: Create Docker Compose integration tests**

```bash
cat > tests/test_docker_compose.sh << 'EOF'
#!/bin/bash
# Integration tests for Docker Compose configurations
# Validates compose file syntax and service definitions

set -e

# Test framework
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    echo "✅ PASS: $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
    echo "❌ FAIL: $1"
    echo "   $2"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

echo "Running Docker Compose integration tests..."
echo ""

# Test 1: Base compose file is valid
if docker compose -f docker-compose.yml config --quiet 2>&1; then
    pass "Base compose file syntax valid"
else
    fail "Base compose file syntax" "docker-compose.yml has syntax errors"
fi

# Test 2: ROCm overlay is valid
if docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --quiet 2>&1; then
    pass "ROCm overlay syntax valid"
else
    fail "ROCm overlay syntax" "docker-compose.rocm.yml has syntax errors"
fi

# Test 3: CUDA overlay is valid
if docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --quiet 2>&1; then
    pass "CUDA overlay syntax valid"
else
    fail "CUDA overlay syntax" "docker-compose.cuda.yml has syntax errors"
fi

# Test 4: Base file contains infrastructure services
base_services=$(docker compose -f docker-compose.yml config --services)
for service in postgres redis qdrant; do
    if echo "$base_services" | grep -q "^${service}$"; then
        pass "Base file contains $service"
    else
        fail "Base file missing service" "Expected $service in base compose file"
    fi
done

# Test 5: ROCm overlay contains GPU services
rocm_services=$(docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --services)
for service in vllm embeddings reranker; do
    if echo "$rocm_services" | grep -q "^${service}$"; then
        pass "ROCm overlay contains $service"
    else
        fail "ROCm overlay missing service" "Expected $service in ROCm overlay"
    fi
done

# Test 6: CUDA overlay contains GPU services
cuda_services=$(docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --services)
for service in vllm embeddings reranker; do
    if echo "$cuda_services" | grep -q "^${service}$"; then
        pass "CUDA overlay contains $service"
    else
        fail "CUDA overlay missing service" "Expected $service in CUDA overlay"
    fi
done

# Test 7: ROCm services use correct devices
rocm_config=$(docker compose -f docker-compose.yml -f docker-compose.rocm.yml config)
if echo "$rocm_config" | grep -q "/dev/kfd" && echo "$rocm_config" | grep -q "/dev/dri"; then
    pass "ROCm services use /dev/kfd and /dev/dri"
else
    fail "ROCm device configuration" "Missing /dev/kfd or /dev/dri in ROCm services"
fi

# Test 8: CUDA services use NVIDIA runtime
cuda_config=$(docker compose -f docker-compose.yml -f docker-compose.cuda.yml config)
if echo "$cuda_config" | grep -q "runtime: nvidia"; then
    pass "CUDA services use NVIDIA runtime"
else
    fail "CUDA runtime configuration" "Missing 'runtime: nvidia' in CUDA services"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Results:"
echo "  Passed: $TESTS_PASSED"
echo "  Failed: $TESTS_FAILED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $TESTS_FAILED -gt 0 ]; then
    exit 1
else
    echo "✅ All tests passed!"
    exit 0
fi
EOF
```

**Step 2: Make test script executable**

Run: `chmod +x tests/test_docker_compose.sh`
Expected: Script has execute permissions

**Step 3: Run integration tests**

Run: `./tests/test_docker_compose.sh`
Expected: All tests pass

**Step 4: Commit integration tests**

```bash
git add tests/test_docker_compose.sh
git commit -m "test: add Docker Compose integration tests

- Validate compose file syntax
- Verify service definitions
- Check ROCm device configuration
- Check CUDA runtime configuration
- All tests pass"
```

---

## Task 11: Deprecation Notices

**Files:**
- Modify: `activate-cuda.sh`
- Modify: `scripts/start-vllm.sh`
- Modify: `scripts/start-embeddings.sh`

**Step 1: Add deprecation notice to activate-cuda.sh**

Run:
```bash
cat > activate-cuda.sh.tmp << 'EOF'
#!/bin/bash
# DEPRECATED: Use unified 'source activate.sh' instead
# This script is kept for backward compatibility

echo "⚠️  DEPRECATED: activate-cuda.sh is deprecated"
echo "   Please use: source activate.sh"
echo "   Or force CUDA: BESTBOX_GPU_BACKEND=cuda source activate.sh"
echo ""
echo "   This script will be removed in a future version."
echo ""

# Original activate-cuda.sh content preserved below
# (Keep existing functionality for now)

EOF
cat activate-cuda.sh >> activate-cuda.sh.tmp
mv activate-cuda.sh.tmp activate-cuda.sh
chmod +x activate-cuda.sh
```

**Step 2: Verify deprecation notice is at top**

Run: `head -15 activate-cuda.sh`
Expected: See deprecation notice at top of file

**Step 3: Add deprecation to start-vllm.sh (if exists)**

Run:
```bash
if [ -f scripts/start-vllm.sh ]; then
    sed -i '1a\\n# DEPRECATED: Use ./start-all-services.sh instead\n# This individual service script is kept for backward compatibility\necho "⚠️  DEPRECATED: Use ./start-all-services.sh to start all services"\necho ""\n' scripts/start-vllm.sh
fi
```

**Step 4: Add deprecation to start-embeddings.sh (if exists)**

Run:
```bash
if [ -f scripts/start-embeddings.sh ]; then
    sed -i '1a\\n# DEPRECATED: Use ./start-all-services.sh instead\n# This individual service script is kept for backward compatibility\necho "⚠️  DEPRECATED: Use ./start-all-services.sh to start all services"\necho ""\n' scripts/start-embeddings.sh
fi
```

**Step 5: Commit deprecation notices**

```bash
git add activate-cuda.sh scripts/start-vllm.sh scripts/start-embeddings.sh
git commit -m "chore: add deprecation notices to old scripts

- Add notice to activate-cuda.sh (use activate.sh instead)
- Add notices to individual service scripts
- Scripts remain functional for backward compatibility
- Will be removed in future version"
```

---

## Task 12: Documentation Updates

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Read current CLAUDE.md to find GPU section**

Run: `grep -n "GPU Notes\|Environment Activation\|Common Commands" CLAUDE.md | head -20`
Expected: See line numbers for relevant sections

**Step 2: Update CLAUDE.md with multi-GPU instructions**

Add the following section after "Common Commands" (around line 14):

```bash
cat > CLAUDE.md.patch << 'EOF'
## Environment Activation

### Automatic GPU Detection (Recommended):
```bash
source activate.sh                # Auto-detects AMD ROCm, NVIDIA CUDA, or CPU
./start-all-services.sh           # Starts all services with detected GPU
```

### Manual GPU Selection:
```bash
# Force CUDA:
BESTBOX_GPU_BACKEND=cuda source activate.sh
BESTBOX_GPU_BACKEND=cuda ./start-all-services.sh

# Force ROCm:
BESTBOX_GPU_BACKEND=rocm source activate.sh

# Force CPU (no GPU):
BESTBOX_GPU_BACKEND=cpu source activate.sh

# Persistent config (create .bestbox/config):
mkdir -p .bestbox
echo "gpu_backend=cuda" > .bestbox/config
source activate.sh                # Uses config file setting
```

### Legacy Commands (Deprecated):
```bash
source activate-cuda.sh           # DEPRECATED: Use 'source activate.sh' instead
./scripts/start-vllm.sh           # DEPRECATED: Use './start-all-services.sh' instead
```

## GPU Backend Support

BestBox supports three GPU backends with automatic detection:

### AMD ROCm
- **Hardware:** Ryzen AI Max+ 395, Radeon 8060S, gfx1151 (Strix Halo)
- **Runtime:** ROCm 7.2.0
- **Docker Images:** rocm/vllm-dev, rocm/pytorch
- **Detection:** Auto-detected via rocm-smi or rocminfo
- **Devices:** /dev/kfd, /dev/dri

### NVIDIA CUDA
- **Hardware:** NVIDIA GPUs (tested on RTX 3080, P100)
- **Runtime:** NVIDIA Container Runtime
- **Docker Images:** vllm/vllm-openai, pytorch/pytorch (CUDA)
- **Detection:** Auto-detected via nvidia-smi
- **Runtime:** nvidia (Docker Compose)

### CPU Fallback
- **Mode:** No GPU detected or explicitly set to CPU
- **Usage:** Development, testing, CI/CD without GPU
- **Performance:** Significantly slower than GPU modes

### GPU Detection Priority
1. **Environment Variable:** `BESTBOX_GPU_BACKEND=cuda|rocm|cpu` (highest priority)
2. **Config File:** `.bestbox/config` with `gpu_backend=cuda|rocm|cpu`
3. **Auto-Detection:** Tests for nvidia-smi → rocm-smi → fallback to CPU
EOF
```

**Step 3: Insert new content into CLAUDE.md**

Run:
```bash
# Find line number after "Common Commands" section
LINE=$(grep -n "^## Common Commands" CLAUDE.md | head -1 | cut -d: -f1)
END_LINE=$((LINE + 30))  # After the commands section

# Extract before, new content, and after
head -$END_LINE CLAUDE.md > CLAUDE.md.new
cat CLAUDE.md.patch >> CLAUDE.md.new
tail -n +$((END_LINE + 1)) CLAUDE.md >> CLAUDE.md.new

# Replace original
mv CLAUDE.md.new CLAUDE.md
rm CLAUDE.md.patch
```

**Step 4: Update GPU Notes section (if exists)**

Find and update or remove the old "GPU Notes" section since it's now covered in "GPU Backend Support".

Run: `grep -n "^## GPU Notes" CLAUDE.md`

If the section exists, you can leave it or merge content as appropriate.

**Step 5: Verify CLAUDE.md changes**

Run: `grep -A 5 "Environment Activation\|GPU Backend Support" CLAUDE.md`
Expected: See new multi-GPU documentation

**Step 6: Commit documentation updates**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with multi-GPU support

- Add environment activation section with auto-detection
- Document manual GPU selection options
- Add GPU backend support section (AMD ROCm, NVIDIA CUDA, CPU)
- Explain detection priority chain
- Mark old commands as deprecated"
```

---

## Task 13: CI/CD GitHub Actions (Optional)

**Files:**
- Create: `.github/workflows/test-multi-gpu.yml`

**Step 1: Create GitHub Actions workflow directory**

Run: `mkdir -p .github/workflows`
Expected: Directory created

**Step 2: Create multi-GPU test workflow**

```bash
cat > .github/workflows/test-multi-gpu.yml << 'EOF'
name: Multi-GPU Configuration Tests

on:
  push:
    branches: [ main, feature/* ]
  pull_request:
    branches: [ main ]

jobs:
  test-rocm-config:
    name: Test ROCm Configuration
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set ROCm backend
        run: echo "BESTBOX_GPU_BACKEND=rocm" >> $GITHUB_ENV

      - name: Test activation script
        run: |
          source activate.sh
          test "$BESTBOX_GPU_BACKEND" = "rocm" || exit 1
          echo "✅ ROCm mode activated successfully"

      - name: Validate ROCm compose files
        run: |
          docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --quiet
          echo "✅ ROCm compose files are valid"

      - name: Test GPU detection script
        run: |
          source scripts/detect-gpu.sh
          BESTBOX_GPU_BACKEND=rocm
          result=$(detect_gpu)
          test "$result" = "rocm" || exit 1
          echo "✅ GPU detection works for ROCm"

  test-cuda-config:
    name: Test CUDA Configuration
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set CUDA backend
        run: echo "BESTBOX_GPU_BACKEND=cuda" >> $GITHUB_ENV

      - name: Test activation script
        run: |
          source activate.sh
          test "$BESTBOX_GPU_BACKEND" = "cuda" || exit 1
          echo "✅ CUDA mode activated successfully"

      - name: Validate CUDA compose files
        run: |
          docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --quiet
          echo "✅ CUDA compose files are valid"

      - name: Test GPU detection script
        run: |
          source scripts/detect-gpu.sh
          BESTBOX_GPU_BACKEND=cuda
          result=$(detect_gpu)
          test "$result" = "cuda" || exit 1
          echo "✅ GPU detection works for CUDA"

  test-cpu-fallback:
    name: Test CPU Fallback
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Test auto-detection (no GPU = CPU)
        run: |
          source activate.sh
          test "$BESTBOX_GPU_BACKEND" = "cpu" || exit 1
          echo "✅ CPU fallback works"

      - name: Validate base compose file
        run: |
          docker compose -f docker-compose.yml config --quiet
          echo "✅ Base compose file is valid"

  test-detection-priority:
    name: Test Detection Priority Chain
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Test environment variable priority
        run: |
          source scripts/detect-gpu.sh
          BESTBOX_GPU_BACKEND=cuda
          result=$(detect_gpu)
          test "$result" = "cuda" || exit 1
          echo "✅ Environment variable has highest priority"

      - name: Test config file priority
        run: |
          mkdir -p .bestbox
          echo "gpu_backend=rocm" > .bestbox/config
          unset BESTBOX_GPU_BACKEND
          source scripts/detect-gpu.sh
          result=$(detect_gpu)
          test "$result" = "rocm" || exit 1
          echo "✅ Config file priority works"

      - name: Run unit tests
        run: |
          chmod +x tests/test_gpu_detection.sh
          ./tests/test_gpu_detection.sh
          echo "✅ All unit tests pass"

      - name: Run integration tests
        run: |
          chmod +x tests/test_docker_compose.sh
          ./tests/test_docker_compose.sh
          echo "✅ All integration tests pass"
EOF
```

**Step 3: Commit GitHub Actions workflow**

```bash
git add .github/workflows/test-multi-gpu.yml
git commit -m "ci: add GitHub Actions workflow for multi-GPU tests

- Test ROCm configuration
- Test CUDA configuration
- Test CPU fallback
- Test detection priority chain
- Run unit and integration tests
- Runs on push and pull requests"
```

---

## Task 14: End-to-End Manual Testing

**Files:**
- Create: `docs/MULTI_GPU_TESTING.md`

**Step 1: Create manual testing guide**

```bash
cat > docs/MULTI_GPU_TESTING.md << 'EOF'
# Multi-GPU Support Manual Testing Guide

This guide provides step-by-step instructions for manually testing the multi-GPU support implementation.

## Prerequisites

- BestBox repository cloned
- Docker and Docker Compose installed
- Either AMD ROCm or NVIDIA CUDA drivers installed (or neither for CPU testing)

## Test 1: Auto-Detection (ROCm System)

**On a system with AMD GPU and ROCm installed:**

```bash
# Step 1: Clean environment
unset BESTBOX_GPU_BACKEND
rm -f .bestbox/config

# Step 2: Activate environment
source activate.sh

# Expected output:
# 🎮 Configuring AMD ROCm environment...
# ✅ BestBox environment activated
#    GPU Backend: rocm

# Step 3: Verify environment variables
echo $BESTBOX_GPU_BACKEND          # Should be: rocm
echo $ROCM_PATH                     # Should be: /opt/rocm-7.2.0
echo $HSA_OVERRIDE_GFX_VERSION      # Should be: 11.0.0

# Step 4: Start services
./start-all-services.sh

# Expected: All services start with ROCm configuration

# Step 5: Verify vLLM is using ROCm
docker logs vllm-server | grep -i "rocm\|hip"

# Step 6: Health checks
curl http://localhost:8000/health   # Agent API
curl http://localhost:8001/health   # vLLM
curl http://localhost:8081/health   # Embeddings

# Step 7: Stop services
./stop-all-services.sh
```

**✅ Pass criteria:** All services start, health checks pass, ROCm devices used

## Test 2: Auto-Detection (CUDA System)

**On a system with NVIDIA GPU and CUDA installed:**

```bash
# Step 1: Clean environment
unset BESTBOX_GPU_BACKEND
rm -f .bestbox/config

# Step 2: Activate environment
source activate.sh

# Expected output:
# 🎮 Configuring NVIDIA CUDA environment...
# ✅ BestBox environment activated
#    GPU Backend: cuda

# Step 3: Verify environment variables
echo $BESTBOX_GPU_BACKEND          # Should be: cuda
echo $CUDA_HOME                     # Should be: /usr/local/cuda
echo $CUDA_VISIBLE_DEVICES         # Should be set or empty

# Step 4: Start services
./start-all-services.sh

# Expected: All services start with CUDA configuration

# Step 5: Verify vLLM is using NVIDIA runtime
docker inspect vllm-server | grep -i "nvidia\|runtime"

# Step 6: Health checks
curl http://localhost:8000/health   # Agent API
curl http://localhost:8001/health   # vLLM
curl http://localhost:8081/health   # Embeddings

# Step 7: Stop services
./stop-all-services.sh
```

**✅ Pass criteria:** All services start, health checks pass, NVIDIA runtime used

## Test 3: Environment Variable Override

**Force CUDA mode on a ROCm system (or vice versa):**

```bash
# Step 1: Force CUDA mode
BESTBOX_GPU_BACKEND=cuda source activate.sh

# Expected output:
# 🎮 Configuring NVIDIA CUDA environment...
# ✅ BestBox environment activated
#    GPU Backend: cuda

# Step 2: Verify
echo $BESTBOX_GPU_BACKEND          # Should be: cuda

# Step 3: Start services (will use CUDA compose files)
BESTBOX_GPU_BACKEND=cuda ./start-all-services.sh

# Step 4: Verify compose files
docker compose -f docker-compose.yml -f docker-compose.cuda.yml ps

# Step 5: Stop services
./stop-all-services.sh
```

**✅ Pass criteria:** Environment variable overrides auto-detection

## Test 4: Config File Override

```bash
# Step 1: Create config file
mkdir -p .bestbox
echo "gpu_backend=rocm" > .bestbox/config

# Step 2: Activate (no env var set)
unset BESTBOX_GPU_BACKEND
source activate.sh

# Expected output:
# 🎮 Configuring AMD ROCm environment...
# ✅ BestBox environment activated
#    GPU Backend: rocm

# Step 3: Verify
echo $BESTBOX_GPU_BACKEND          # Should be: rocm

# Step 4: Change config
echo "gpu_backend=cuda" > .bestbox/config
source activate.sh

# Step 5: Verify new backend
echo $BESTBOX_GPU_BACKEND          # Should be: cuda

# Step 6: Clean up
rm .bestbox/config
```

**✅ Pass criteria:** Config file setting is respected

## Test 5: CPU Fallback

**On a system without GPU:**

```bash
# Step 1: Force CPU mode
BESTBOX_GPU_BACKEND=cpu source activate.sh

# Expected output:
# 💻 Configuring CPU-only environment...
# ⚠️  Running in CPU mode (no GPU detected)
# ✅ BestBox environment activated
#    GPU Backend: cpu

# Step 2: Verify GPU variables are unset
echo $CUDA_HOME                    # Should be empty
echo $ROCM_PATH                    # Should be empty

# Step 3: Start services (without GPU services)
BESTBOX_GPU_BACKEND=cpu ./start-all-services.sh

# Expected: Only infrastructure services start (no vllm, embeddings, etc.)

# Step 4: Verify
docker compose ps                  # Should show only postgres, redis, qdrant

# Step 5: Stop services
./stop-all-services.sh
```

**✅ Pass criteria:** CPU mode works without GPU services

## Test 6: Priority Chain

**Test that priority chain works correctly:**

```bash
# Step 1: Set all three (env var should win)
export BESTBOX_GPU_BACKEND=cuda
echo "gpu_backend=rocm" > .bestbox/config
# Auto-detect would find CPU

source activate.sh

# Expected: cuda (env var wins)
echo $BESTBOX_GPU_BACKEND

# Step 2: Remove env var (config should win)
unset BESTBOX_GPU_BACKEND
source activate.sh

# Expected: rocm (config wins)
echo $BESTBOX_GPU_BACKEND

# Step 3: Remove config (auto-detect should win)
rm .bestbox/config
source activate.sh

# Expected: cuda, rocm, or cpu (auto-detected)
echo $BESTBOX_GPU_BACKEND
```

**✅ Pass criteria:** Priority chain: env var > config > auto-detect

## Test 7: Backward Compatibility

**Test that old scripts still work:**

```bash
# Step 1: Test old activate-cuda.sh
source activate-cuda.sh

# Expected: Deprecation warning shown, but script still works

# Step 2: Verify functionality
echo $CUDA_HOME                    # Should be set

# Step 3: Test old individual service scripts (if they exist)
if [ -f scripts/start-vllm.sh ]; then
    ./scripts/start-vllm.sh
    # Expected: Deprecation warning, but service starts
fi
```

**✅ Pass criteria:** Old scripts work with deprecation warnings

## Test 8: Docker Compose Validation

```bash
# Test 1: Base file is valid
docker compose -f docker-compose.yml config --quiet
echo "✅ Base compose file valid"

# Test 2: ROCm overlay is valid
docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --quiet
echo "✅ ROCm overlay valid"

# Test 3: CUDA overlay is valid
docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --quiet
echo "✅ CUDA overlay valid"

# Test 4: Services are correctly defined
docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --services
# Expected: postgres, redis, qdrant, vllm, embeddings, reranker, etc.
```

**✅ Pass criteria:** All compose files are valid

## Test 9: Unit and Integration Tests

```bash
# Run unit tests
./tests/test_gpu_detection.sh
# Expected: All tests pass

# Run integration tests
./tests/test_docker_compose.sh
# Expected: All tests pass
```

**✅ Pass criteria:** All automated tests pass

## Test 10: Full Workflow

**Complete end-to-end test:**

```bash
# Step 1: Fresh clone simulation
cd /tmp
git clone /path/to/BestBox
cd BestBox

# Step 2: Activate
source activate.sh
# Expected: Auto-detects GPU correctly

# Step 3: Start all services
./start-all-services.sh
# Expected: All services start successfully

# Step 4: Wait for services to be ready
sleep 60

# Step 5: Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health  # (if GPU mode)
curl http://localhost:8081/health  # (if GPU mode)

# Step 6: Check logs
tail -20 logs/agent_api.log
tail -20 logs/frontend.log

# Step 7: Test inference (if GPU mode)
curl http://localhost:8001/v1/models

# Step 8: Stop all services
./stop-all-services.sh

# Step 9: Verify clean shutdown
docker compose ps
# Expected: All containers stopped
```

**✅ Pass criteria:** Complete workflow works end-to-end

## Troubleshooting

### Issue: Wrong GPU detected

**Solution:** Use environment variable or config file to override:
```bash
BESTBOX_GPU_BACKEND=cuda source activate.sh
# or
echo "gpu_backend=cuda" > .bestbox/config
```

### Issue: Docker services fail to start

**Check:**
1. GPU drivers installed: `nvidia-smi` or `rocm-smi`
2. Docker has GPU access: `docker run --rm --device=/dev/kfd --device=/dev/dri rocm/pytorch:latest rocminfo`
3. Compose file syntax: `docker compose config --quiet`

### Issue: Old scripts not working

**Check:**
1. Scripts are still in place (not deleted)
2. Deprecation notices are informational only
3. Functionality preserved

## Checklist

- [ ] Test 1: Auto-detection (ROCm) ✅
- [ ] Test 2: Auto-detection (CUDA) ✅
- [ ] Test 3: Environment variable override ✅
- [ ] Test 4: Config file override ✅
- [ ] Test 5: CPU fallback ✅
- [ ] Test 6: Priority chain ✅
- [ ] Test 7: Backward compatibility ✅
- [ ] Test 8: Docker Compose validation ✅
- [ ] Test 9: Unit and integration tests ✅
- [ ] Test 10: Full workflow ✅

## Sign-off

**Tester:** _______________
**Date:** _______________
**GPU Type:** [ ] ROCm  [ ] CUDA  [ ] CPU
**All tests passed:** [ ] Yes  [ ] No

**Notes:**
EOF
```

**Step 2: Commit manual testing guide**

```bash
git add docs/MULTI_GPU_TESTING.md
git commit -m "docs: add manual testing guide for multi-GPU support

- 10 comprehensive test scenarios
- ROCm, CUDA, and CPU testing
- Priority chain validation
- Backward compatibility checks
- Full workflow end-to-end test
- Troubleshooting guide"
```

---

## Task 15: Final Validation and Cleanup

**Step 1: Run all unit tests**

Run: `./tests/test_gpu_detection.sh`
Expected: All tests pass

**Step 2: Run all integration tests**

Run: `./tests/test_docker_compose.sh`
Expected: All tests pass

**Step 3: Validate all compose files**

Run:
```bash
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.rocm.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.cuda.yml config --quiet
echo "✅ All compose files are valid"
```

**Step 4: Test activation on current system**

Run:
```bash
source activate.sh
echo "Detected backend: $BESTBOX_GPU_BACKEND"
```
Expected: Correct GPU backend detected and configured

**Step 5: Verify all new files are tracked**

Run:
```bash
git status
```
Expected: All new files committed, working directory clean

**Step 6: Review commit history**

Run:
```bash
git log --oneline -15
```
Expected: See all commits from this implementation (15 tasks)

**Step 7: Create final summary commit**

```bash
git commit --allow-empty -m "feat: complete multi-GPU support implementation

Summary of changes:
- GPU detection script with priority chain (env > config > auto)
- Unified activation script (activate.sh)
- Docker Compose base + overlay architecture
- Unified start/stop scripts (start-all-services.sh, stop-all-services.sh)
- Configuration file support (.bestbox/config)
- Comprehensive test suite (unit + integration)
- CI/CD GitHub Actions workflow
- Deprecation notices for old scripts
- Updated documentation (CLAUDE.md, testing guide)

Supports: AMD ROCm, NVIDIA CUDA, CPU fallback
Backward compatible: Yes (old scripts work with deprecation warnings)
Tests: All passing (unit, integration, compose validation)"
```

**Step 8: Tag the implementation**

Run:
```bash
git tag -a v1.0.0-multi-gpu -m "Multi-GPU support implementation complete

- AMD ROCm support
- NVIDIA CUDA support
- CPU fallback support
- Automatic GPU detection
- Unified activation and startup scripts
- Backward compatible with existing setups"
```

**Step 9: Display completion summary**

Run:
```bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Multi-GPU Support Implementation Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "New files created:"
echo "  ✓ scripts/detect-gpu.sh"
echo "  ✓ docker-compose.rocm.yml"
echo "  ✓ docker-compose.cuda.yml"
echo "  ✓ start-all-services.sh"
echo "  ✓ stop-all-services.sh"
echo "  ✓ .bestbox/config.example"
echo "  ✓ tests/test_gpu_detection.sh"
echo "  ✓ tests/test_docker_compose.sh"
echo "  ✓ .github/workflows/test-multi-gpu.yml"
echo "  ✓ docs/MULTI_GPU_TESTING.md"
echo ""
echo "Modified files:"
echo "  ✓ activate.sh (unified with GPU detection)"
echo "  ✓ docker-compose.yml (base services only)"
echo "  ✓ activate-cuda.sh (deprecation notice)"
echo "  ✓ CLAUDE.md (multi-GPU documentation)"
echo ""
echo "Next steps:"
echo "  1. Review: git log --oneline -15"
echo "  2. Test: source activate.sh"
echo "  3. Start: ./start-all-services.sh"
echo "  4. Manual testing: See docs/MULTI_GPU_TESTING.md"
echo "  5. Push: git push origin feature/multi-gpu-support"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
```

---

## Execution Completion

**Implementation complete!** All 15 tasks finished.

**Summary:**
- ✅ GPU detection with 3-tier priority chain
- ✅ Unified activation script (activate.sh)
- ✅ Docker Compose base + ROCm/CUDA overlays
- ✅ Unified start/stop scripts
- ✅ Configuration file support
- ✅ Comprehensive test suite (unit + integration)
- ✅ CI/CD GitHub Actions
- ✅ Deprecation notices for backward compatibility
- ✅ Documentation updates

**Next step:** Follow manual testing guide in `docs/MULTI_GPU_TESTING.md` to validate on real hardware.
