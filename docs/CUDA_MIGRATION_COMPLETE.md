# CUDA Migration Complete 🎉

**Date:** 2026-01-31  
**Status:** ✅ Successfully migrated from AMD ROCm to NVIDIA CUDA

## Summary

BestBox has been successfully migrated from AMD Ryzen AI Max+ 395 (ROCm) to NVIDIA GPUs (RTX 3080 + Tesla P100) with CUDA acceleration.

## Working Configuration

### Hardware
- **LLM (vLLM):** NVIDIA RTX 3080 (12GB VRAM) - cuda:0
- **Embeddings:** Tesla P100 (16GB VRAM) - via CUDA 11.7 Docker container (sm_60 compatible)

### Services

| Service | Port | GPU | Container | Status |
|---------|------|-----|-----------|--------|
| vLLM (Qwen3-4B-Instruct) | 8001 | RTX 3080 | shaie-vllm | ✅ Running |
| Embeddings (BGE-M3) | 8004 | P100 | shaie-p100-services | ✅ Running |
| Agent API | 8000 | - | Native Python | ✅ Running |
| Frontend (Next.js) | 3000 | - | Node.js | ✅ Running |
| Qdrant Vector Store | 6333 | - | bestbox-qdrant | ✅ Running |

### Key Configuration Files

1. **Backend Environment** ([.env](.env))
   ```bash
   LLM_BASE_URL=http://127.0.0.1:8001/v1
   LLM_MODEL=Qwen/Qwen3-4B-Instruct-2507
   EMBEDDINGS_BASE_URL=http://127.0.0.1:8004
   ```

2. **Frontend Environment** ([frontend/copilot-demo/.env.local](frontend/copilot-demo/.env.local))
   ```bash
   NEXT_PUBLIC_LLM_PORT=8001
   NEXT_PUBLIC_EMBEDDINGS_PORT=8004
   NEXT_PUBLIC_RERANKER_PORT=8004
   ```

## Changes Made

### Backend Updates
- [services/agent_api.py](services/agent_api.py) - Added OpenAI Responses API format for CopilotKit v1.51+ compatibility
- [services/embeddings/main.py](services/embeddings/main.py) - Added `EMBEDDINGS_DEVICE` and `EMBEDDINGS_MODEL_NAME` environment variables
- [services/rag_pipeline/reranker.py](services/rag_pipeline/reranker.py) - Added `RERANKER_DEVICE` env var
- [scripts/start-agent-api.sh](scripts/start-agent-api.sh) - Sources `.env` for LLM configuration

### Frontend Updates
- [frontend/copilot-demo/next.config.ts](frontend/copilot-demo/next.config.ts) - Made service ports configurable via environment variables
- [frontend/copilot-demo/messages/en.json](frontend/copilot-demo/messages/en.json) - Updated footer to show NVIDIA hardware
- [frontend/copilot-demo/messages/zh.json](frontend/copilot-demo/messages/zh.json) - Updated footer to show NVIDIA hardware
- [frontend/copilot-demo/app/api/copilotkit/route.ts](frontend/copilot-demo/app/api/copilotkit/route.ts) - Updated system info

### New Scripts
- [activate-cuda.sh](activate-cuda.sh) - CUDA environment activation script
- [scripts/start-llm-cuda.sh](scripts/start-llm-cuda.sh) - NVIDIA LLM startup script
- [scripts/build-llama-cuda.sh](scripts/build-llama-cuda.sh) - llama.cpp CUDA build script

## Technical Notes

### P100 Compatibility Issue
The Tesla P100 (compute capability sm_60) is **NOT compatible** with PyTorch 2.10+ (requires sm_70+). The solution is to use the SHAIE Docker container which uses CUDA 11.7/11.8 with an older PyTorch version that supports sm_60.

### GPU Index Mapping
- **nvidia-smi**: GPU 0 = P100, GPU 1 = RTX 3080
- **PyTorch**: cuda:0 = RTX 3080, cuda:1 = P100 (PyTorch reorders by compute capability)

### vLLM Configuration
The vLLM container runs on port 8001 with model `Qwen/Qwen3-4B-Instruct-2507`, providing an OpenAI-compatible API.

## Verification

The chat functionality was tested and confirmed working:
- ✅ Basic conversation (e.g., "What is 2+2?" → "2 + 2 = 4")
- ✅ Self-identification (assistant describes itself as BestBox General Assistant)
- ✅ System status monitoring (4/5 services healthy)
- ✅ UI rendering correctly

## Screenshot

See `.playwright-mcp/cuda-migration-completed.png` for the working UI screenshot.

## Next Steps (Optional)

1. **Start S2S Gateway** - If voice features are needed
2. **Test ERP/CRM tools** - Verify domain-specific agents work correctly
3. **Performance tuning** - Adjust vLLM batch size and context length for optimal throughput
