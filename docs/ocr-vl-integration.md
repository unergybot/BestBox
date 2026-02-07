# OCR-VL Integration

GPU-aware document processing pipeline with intelligent quality escalation.

## Overview

This implementation follows the design in `docs/design/ocr-vl-docling.md`, providing:

- **P100 (GPU 0)**: Classical OCR (GOT-OCR2.0) - always on
- **RTX 3080 (GPU 1)**: OCR-VL (GLM-OCR via Ollama) - on demand
- **CPU**: Docling document parsing with quality gate
- **GPU Scheduler**: Mutual exclusion between LLM and OCR-VL on RTX 3080

## Architecture

```
PDF / Image
    ↓
[CPU] Docling (text extraction)
    ↓
Quality Check
    ├─ OK → store + embed
    └─ FAIL → [P100] GOT-OCR2.0
                  ↓
            Quality Check
                ├─ OK → store + embed
                └─ FAIL → escalate to [RTX 3080] GLM-OCR
                                ↓
                          replace page result
```

## Services

| Service | Port | GPU | Description |
|---------|------|-----|-------------|
| ocr-service | 8084 | P100 (0) | GOT-OCR2.0 classical OCR |
| glm-ocr-service | 11434 | RTX 3080 (1) | GLM-OCR via Ollama |
| docling-service | 8085 | CPU | Document parsing with quality gate |
| gpu-scheduler | 8086 | - | Mutual exclusion scheduler |

## Quick Start

```bash
# Start all OCR services
./scripts/start-ocr-docker.sh

# Test the pipeline
./scripts/test-ocr-pipeline.sh

# Stop services
./scripts/stop-ocr-docker.sh
```

## Usage

### Parse Document with OCR-VL Fallback

```bash
curl -X POST http://localhost:8085/parse \
  -F "file=@document.pdf" \
  -F "run_ocr=true"
```

Response includes:
- `text`: Combined text (Docling + OCR results)
- `ocr_results`: Array of OCR results with source attribution
- `metadata.pages_escalated`: Number of pages sent to GLM-OCR

### Direct GOT-OCR2.0 (P100)

```bash
curl -X POST http://localhost:8084/ocr \
  -F "file=@page.png"
```

### Direct GLM-OCR (RTX 3080)

```bash
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-ocr",
    "prompt": "Extract all text from this image",
    "images": ["base64encodedimage..."],
    "stream": false
  }'
```

### GPU Scheduler API

```bash
# Acquire lock for OCR-VL
curl -X POST http://localhost:8086/lock \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": "my-worker-1",
    "workload_type": "ocr-vl",
    "timeout": 300
  }'

# Check status
curl http://localhost:8086/status

# Release lock
curl -X POST "http://localhost:8086/lock/release?worker_id=my-worker-1"
```

## Quality Gate

The docling service automatically checks for quality issues:

- Empty text blocks
- High garbage ratio (>30% non-ASCII)
- Collapsed tables
- Very short text (<50 chars)

Failed pages escalate through:
1. GOT-OCR2.0 (P100)
2. GLM-OCR (RTX 3080) if still failing

## GPU Scheduling

Critical rule: **OCR-VL never runs concurrently with LLM inference**

The GPU scheduler provides:
- File-based locks (fallback)
- Redis-based locks (if available)
- Automatic lock expiration (5 min default)
- Health monitoring

## Environment Variables

### Docling Service
- `OCR_SERVICE_URL`: GOT-OCR2.0 endpoint (default: http://ocr-service:8084)
- `GLM_OCR_URL`: GLM-OCR endpoint (default: http://glm-ocr-service:11434)
- `GPU_SCHEDULER_URL`: Scheduler endpoint (default: http://gpu-scheduler:8086)
- `OCR_MIN_TEXT_CHARS`: Minimum text threshold (default: 50)
- `GARBAGE_THRESHOLD`: Garbage ratio limit (default: 0.30)
- `ENABLE_QUALITY_GATE`: Enable quality checks (default: true)
- `ENABLE_GLM_OCR_FALLBACK`: Enable GLM-OCR escalation (default: true)

### GPU Scheduler
- `SCHEDULER_PORT`: Service port (default: 8086)
- `LOCK_TIMEOUT`: Lock expiration in seconds (default: 300)
- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379)

## Docker Compose

```bash
# Build and start
docker compose -f docker/docker-compose.ocr.yml up --build -d

# View logs
docker compose -f docker/docker-compose.ocr.yml logs -f

# Scale down
docker compose -f docker/docker-compose.ocr.yml down
```

## VRAM Requirements

| Model | GPU | VRAM |
|-------|-----|------|
| GOT-OCR2.0 | P100 | ~4GB |
| GLM-OCR | RTX 3080 | ~5GB |
| Qwen2.5-14B | RTX 3080 | ~4.5GB |

Total peak on RTX 3080: ~9.5GB (fits in 12GB)

## Troubleshooting

### Services not starting
```bash
# Check GPU availability
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### GLM-OCR not responding
```bash
# Check Ollama model
curl http://localhost:11434/api/tags

# Pull model manually
docker exec bestbox-glm-ocr ollama pull glm-ocr
```

### GPU lock contention
```bash
# Check scheduler status
curl http://localhost:8086/status

# Force release (emergency)
curl -X POST "http://localhost:8086/lock/release?worker_id=FORCE"
```

## Files

- `docker/Dockerfile.glm-ocr`: GLM-OCR service with Ollama
- `docker/Dockerfile.gpu-scheduler`: GPU scheduler service
- `docker/docker-compose.ocr.yml`: Complete OCR stack
- `services/ocr/glm_ocr_client.py`: Python client for GLM-OCR
- `services/gpu_scheduler/main.py`: GPU scheduler implementation
- `services/ocr/doc_parsing_service.py`: Enhanced docling with quality gate
- `scripts/start-ocr-docker.sh`: Start script
- `scripts/stop-ocr-docker.sh`: Stop script
- `scripts/test-ocr-pipeline.sh`: Test script
