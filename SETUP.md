# BestBox Setup Guide

**For:** Fresh git clone on AMD Ryzen AI Max+ 395 (Strix Halo) with ROCm 7.2

## Prerequisites

✅ **Required (pre-installed):**
- ROCm 7.2.0 (`rocm-smi`)
- Docker with Compose plugin (`docker compose`)
- Python 3.12
- Git

✅ **Model files (already downloaded):**
- Qwen3-30B-A3B-Instruct-2507 at `~/.cache/modelscope/hub/models/`

✅ **Docker images (already pulled):**
- `rocm/vllm-dev:rocm7.2_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.14.0rc0` (41.5GB)

## Setup Steps

### 1. Clone Repository

```bash
git clone <repository-url> ~/BestBox
cd ~/BestBox
git checkout feature/amd-rocm  # Use vLLM migration branch
```

### 2. Create Python Virtual Environment

```bash
python3 -m venv venv
```

### 3. Install Python Dependencies

```bash
source venv/bin/activate
pip install --upgrade pip

# Install core dependencies (skip TTS for Python 3.12 compatibility)
grep -v "^TTS" requirements.txt > /tmp/requirements-no-tts.txt
pip install -r /tmp/requirements-no-tts.txt
```

**Note:** TTS library (for Speech-to-Speech) requires Python 3.11. Skip it unless you need S2S features.

### 4. Start Infrastructure Services

```bash
docker compose up -d qdrant postgres redis
```

Wait ~1 minute for services to be healthy:

```bash
docker compose ps  # Should show all as "healthy"
```

### 5. Start vLLM Server

```bash
./scripts/start-vllm.sh
```

**Model loading takes 2-3 minutes.** Monitor with:

```bash
docker compose logs -f vllm
```

Look for: `Application startup complete`

### 6. Verify vLLM

```bash
# Health check
curl http://localhost:8001/health

# Check model
curl http://localhost:8001/v1/models | jq

# Test completion
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-30b",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "max_tokens": 10
  }' | jq '.choices[0].message.content'
```

Expected: `"4"`

### 7. Start Agent API (Optional)

```bash
source activate.sh  # Sets ROCm env vars and LLM_BASE_URL
./scripts/start-agent-api.sh
```

Test:

```bash
curl http://localhost:8000/health
```

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| vLLM (LLM) | 8001 | http://localhost:8001 |
| Agent API | 8000 | http://localhost:8000 |
| Qdrant (Vector DB) | 6333 | http://localhost:6333 |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

## Management Commands

```bash
# vLLM
./scripts/start-vllm.sh      # Start vLLM
./scripts/stop-vllm.sh       # Stop vLLM
./scripts/restart-vllm.sh    # Restart vLLM
./scripts/monitor-vllm.sh    # Monitor GPU & stats

# Infrastructure
docker compose up -d         # Start all
docker compose stop          # Stop all
docker compose logs -f vllm  # View logs

# Emergency rollback to llama.cpp
./scripts/rollback-to-llamacpp.sh
```

## Troubleshooting

### TTS Installation Error

**Error:** `No matching distribution found for TTS>=0.22.0`

**Cause:** TTS requires Python 3.11, you have 3.12

**Solution:** Skip TTS (only needed for Speech-to-Speech feature):
```bash
grep -v "^TTS" requirements.txt > /tmp/requirements-no-tts.txt
pip install -r /tmp/requirements-no-tts.txt
```

### Docker Compose Command Not Found

**Error:** `docker-compose: command not found`

**Solution:** Use `docker compose` (plugin version, not standalone):
```bash
docker compose version  # Should show v5.0.2+
```

If not installed:
```bash
sudo apt-get install docker-compose-plugin
```

### vLLM Container Fails to Start

**Check logs:**
```bash
docker compose logs vllm | grep -i error
```

**Common issues:**
- Wrong Docker image (must be ROCm 7.2 for gfx1151)
- Model not found (check `~/.cache/modelscope/hub/models/`)
- Out of memory (Qwen3-30B needs ~20GB VRAM)

### Model Not Found

**Error:** Model path `/models/Qwen/Qwen3-30B-A3B-Instruct-2507` not found

**Solution:** Download the model:
```bash
# Install modelscope
pip install modelscope

# Download model
python -c "from modelscope import snapshot_download; \
snapshot_download('Qwen/Qwen3-30B-A3B-Instruct-2507')"
```

## Performance Expectations

- **Throughput:** 13-76 tok/s (depending on batching)
- **Latency:** ~5-8 seconds for 128 tokens
- **VRAM:** ~20GB during inference
- **Model loading:** 2-3 minutes

## Documentation

- [System Design](docs/system_design.md) - Architecture overview
- [vLLM Migration Summary](docs/VLLM_MIGRATION_SUMMARY.md) - What changed
- [Project Status](docs/PROJECT_STATUS.md) - Development progress
- [CLAUDE.md](CLAUDE.md) - Developer guide for Claude Code

## Quick Start (Summary)

```bash
# 1. Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # or use requirements-no-tts.txt

# 2. Start services
docker compose up -d
./scripts/start-vllm.sh

# 3. Verify
curl http://localhost:8001/v1/models | jq
```

Done! 🎉
