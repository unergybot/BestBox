# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BestBox is an enterprise agentic applications demo kit supporting both AMD (Ryzen AI Max+ 395, Radeon 8060S) and NVIDIA (RTX 3080, Tesla P100) hardware. It demonstrates multi-agent orchestration using LangGraph with four specialized agents: ERP, CRM, IT Ops, and Office Automation. The system runs entirely on-premise with local LLM inference via llama.cpp (Vulkan for AMD, CUDA for NVIDIA).

## Common Commands

### Environment Activation
```bash
# AMD ROCm systems
source ~/BestBox/activate.sh  # Activates venv and sets ROCm environment variables

# NVIDIA CUDA systems
source ~/BestBox/activate-cuda.sh  # Activates venv and sets CUDA environment variables
```

### Start Services
```bash
# Infrastructure (run first)
docker compose up -d                    # Qdrant, PostgreSQL, Redis

# Backend services (each in separate terminal)
./scripts/start-llm.sh                  # LLM server on :8080 (AMD Vulkan)
./scripts/start-llm-cuda.sh             # LLM server on :8001 (NVIDIA CUDA)
./scripts/start-embeddings.sh           # Embeddings and Reranker on :8004
./scripts/start-agent-api.sh            # Agent API on :8000

# Frontend
cd frontend/copilot-demo && npm run dev # Next.js on :3000
```

### Testing
```bash
python scripts/test_agents.py           # Agent integration tests
cd frontend/copilot-demo && npm run lint # Frontend linting
```

### Health Checks
```bash
curl http://localhost:8001/health       # LLM server
curl http://localhost:8004/health       # Embeddings
curl http://localhost:8004/health       # Reranker
curl http://localhost:8000/health       # Agent API
```

## Architecture

### Multi-Agent System
```
User Query → Router Agent → {ERP, CRM, IT Ops, OA, Fallback} Agent → Tool Node → Response
```

The router (`agents/router.py`) classifies intent and routes to domain-specific agents. Each agent has access to domain tools defined in `tools/`.

## RAG Pipeline

The system includes a RAG pipeline for knowledge base search:

- Documents in `data/demo_docs/{erp,crm,itops,oa}/`
- Qdrant vector store (port 6333)
- Reranker service (port 8082)
- Agents can use `search_knowledge_base(query, domain, top_k)` tool

### Seeding Knowledge Base
```bash
python scripts/seed_knowledge_base.py
```

### Adding Documents
1. Add document to appropriate domain folder in `data/demo_docs/`
2. Run seeding script to index new documents

### Key Directories
- `agents/` - LangGraph agent implementations and state management
- `tools/` - Tool definitions (erp_tools.py, crm_tools.py, it_ops_tools.py, oa_tools.py)
- `services/` - FastAPI backends (agent_api.py, embeddings/main.py)
- `frontend/copilot-demo/` - Next.js + CopilotKit UI
- `scripts/` - Startup scripts and tests
- `plugins/` - Plugin system core (registry, loader, hooks)
- `skills/` - Lightweight SKILL.md plugins
- `plugins_contrib/` - Full plugin modules

### Service Ports
| Service | Port |
|---------|------|
| LLM (llama-server) | 8001 |
| Embeddings (BGE-M3) | 8004 |
| Reranker (BGE-reranker-v2-m3) | 8004 |
| Agent API | 8000 |
| S2S Gateway | 8765 |
| Frontend | 3000 |
| Qdrant | 6333/6334 |
| PostgreSQL | 5432 |
| Redis | 6379 |

### Agent State (`agents/state.py`)
- `messages` - Conversation history
- `current_agent` - Active agent (erp, crm, it_ops, oa)
- `tool_calls` - SLA counter (max 5)
- `confidence` - Classification confidence (0.0-1.0)
- `plugin_context` - Plugin system data (active_plugins, tool_results, hook_data)

### LLM Configuration

**AMD (Vulkan):**
- Model: Qwen3-30B-A3B-Instruct-2507-Q4_K_M via llama.cpp (MoE architecture: 30B total, 3B active per token)
- Backend: Vulkan (not HIP/ROCm directly - llama.cpp uses Vulkan for gfx1151)
- Context: 8192 tokens
- Performance: ~206 tok/s prompt processing, ~85 tok/s generation

**NVIDIA (CUDA):**
- Model: Qwen3-4B-Instruct-Q4_K_M (or larger depending on VRAM)
- Backend: CUDA (llama.cpp with CUDA support)
- Context: 4096 tokens (adjust based on VRAM)
- Build: `./scripts/build-llama-cuda.sh`

## Speech-to-Speech (S2S)

The S2S feature provides voice interaction with the agent system.

**Status:** ⚠️ Partially working - WebSocket and ASR functional, TTS disabled by default (see `docs/S2S_QUICK_FIX_RESULTS.md`)

### Start S2S Service
```bash
./scripts/start-s2s.sh                  # S2S Gateway on :8765
# TTS disabled by default to prevent startup hang
# To enable TTS: export S2S_ENABLE_TTS=true
```

### S2S Environment Variables
- `S2S_ENABLE_TTS` - Enable TTS synthesis (default: false)
- `ASR_DEVICE` - ASR device: cuda or cpu (default: cuda, falls back to cpu on AMD)
- `ASR_MODEL` - Whisper model size (default: large-v3)
- `ASR_LANGUAGE` - Recognition language (default: zh)

### S2S Architecture
```
Mic → WebSocket → ASR (faster-whisper) → LangGraph → TTS (XTTS v2) → Audio Playback
```

### S2S Components
- `services/speech/asr.py` - Streaming ASR with VAD
- `services/speech/tts.py` - XTTS v2 synthesis + SpeechBuffer
- `services/speech/s2s_server.py` - FastAPI WebSocket gateway
- `frontend/.../hooks/useS2S.ts` - Client-side audio hooks
- `frontend/.../components/VoiceButton.tsx` - Voice UI

### S2S WebSocket Protocol
```
Client → Server: Binary (PCM16 16kHz) or JSON control
Server → Client: JSON (asr_partial, llm_token) or Binary (PCM16 24kHz)
```

## Adding a New Agent

1. Create agent file: `agents/new_agent.py` (follow pattern from existing agents)
2. Define tools: `tools/new_tools.py` using `@tool` decorator
3. Register in `agents/graph.py`:
   - Add node: `graph.add_node("new_agent", create_new_agent_node())`
   - Add edges for routing and tool handling
4. Update router system prompt in `agents/router.py` to recognize the new domain

## GPU Notes

### AMD ROCm
The system uses AMD ROCm 7.2.0. Key environment variables are set in `activate.sh`:
```bash
HSA_OVERRIDE_GFX_VERSION=11.0.0  # Maps gfx1151 → gfx1100
PYTORCH_ROCM_ARCH=gfx1100
```

llama.cpp uses Vulkan backend (not HIP) because Vulkan has better support for gfx1151 (RDNA 3.5). The LLM server runs natively, not in Docker, for better GPU access.

### NVIDIA CUDA
For NVIDIA GPUs, use the CUDA activation script and CUDA-specific services:
```bash
source ~/BestBox/activate-cuda.sh
./scripts/build-llama-cuda.sh    # Build llama.cpp with CUDA
./scripts/start-llm-cuda.sh      # Start LLM with CUDA backend
```

Key environment variables (set in `.env` or `.env.cuda`):
```bash
LLM_MODEL_PATH=~/models/4b/Qwen3-4B-Instruct-Q4_K_M.gguf
LLM_CUDA_DEVICE=0           # RTX 3080 for LLM
EMBEDDINGS_DEVICE=cuda:1    # P100 for embeddings
RERANKER_DEVICE=cuda:1      # P100 for reranker
```

## Frontend Architecture

Next.js 16 with CopilotKit integration:
- `app/page.tsx` - Main UI with scenario selector
- `app/api/copilotkit/route.ts` - Bridges to Python agent API at :8000
- Uses React 19 and Tailwind CSS 4

## Plugin System

BestBox includes an extensible plugin system for adding tools, lifecycle hooks, and HTTP routes.

### Plugin Types

1. **Skills** - Lightweight plugins with `SKILL.md` files (YAML frontmatter)
2. **Full Plugins** - Complete Python modules with `bestbox.plugin.json` manifests

### Discovery Locations (priority order)
1. Bundled: `skills/`, `plugins_contrib/`
2. Global: `~/.bestbox/plugins/`
3. Workspace: `.bestbox/plugins/`
4. Config-specified paths

### Creating a Skill

```yaml
---
name: my-skill
version: 1.0.0
tools:
  - name: my_tool
    description: Tool description
    parameters: {type: object}
hooks:
  - event: BEFORE_ROUTING
    handler: skills.my_skill.hooks.handler
---

Skill documentation...
```

### Creating a Plugin

1. Create `plugins_contrib/my-plugin/bestbox.plugin.json`
2. Add `__init__.py` with `register(api)` function
3. Restart agent API

### Lifecycle Hooks

Available events: `BEFORE_ROUTING`, `AFTER_ROUTING`, `BEFORE_TOOL_CALL`, `AFTER_TOOL_CALL`, etc.

Hooks execute in priority order and can modify agent state.

### Testing

```bash
pytest tests/test_plugins.py -v                   # Unit tests
pytest tests/test_plugin_integration.py -v        # Integration tests
```

See `docs/PLUGIN_SYSTEM.md` for complete documentation.

## Documentation

- `docs/system_design.md` - Complete architecture specification (800+ lines)
- `docs/rocm_deployment_guide.md` - Hardware and ROCm setup
- `docs/PROJECT_STATUS.md` - Current development status
- `docs/PLUGIN_SYSTEM.md` - Plugin system guide
- `PLUGIN_SYSTEM_IMPLEMENTATION.md` - Implementation summary
