# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BestBox is an enterprise agentic applications demo kit supporting AMD (Ryzen AI Max+ 395, Radeon 8060S) hardware. It demonstrates multi-agent orchestration using LangGraph with four specialized agents: ERP, CRM, IT Ops, and Office Automation. The system runs entirely on-premise with local LLM inference via vLLM (ROCm Docker).

## Common Commands

### Environment Activation
```bash
# Automatic detection (recommended)
source ~/BestBox/activate.sh  # Auto-detects: rocm | cuda | cpu

# Manual override
BESTBOX_GPU_BACKEND=rocm source ~/BestBox/activate.sh
BESTBOX_GPU_BACKEND=cuda source ~/BestBox/activate.sh
BESTBOX_GPU_BACKEND=cpu source ~/BestBox/activate.sh

# Persistent local config
mkdir -p .bestbox && echo "gpu_backend=cuda" > .bestbox/config
```

### Start Services
```bash
# Unified startup (recommended)
./start-all-services.sh

# Manual compose startup
docker compose $BESTBOX_COMPOSE_FILES up -d

# Optional stop
./stop-all-services.sh

# Legacy scripts (deprecated, still functional)
./scripts/start-vllm.sh
./scripts/start-embeddings.sh
./scripts/start-agent-api.sh

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
curl http://localhost:8081/health       # Embeddings
curl http://localhost:8082/health       # Reranker
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
| LLM (vLLM) | 8001 |
| Embeddings (BGE-M3) | 8081 |
| Reranker (BGE-reranker-v2-m3) | 8082 |
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

**AMD (vLLM ROCm):**
- Model: Qwen3-30B-A3B-Instruct-2507 FP16 (MoE architecture: 30B total, 3B active per token)
- Backend: vLLM with ROCm 7.2 (Docker)
- Context: 2048 tokens (stability-first profile)
- Performance: 16-76 tok/s (multi-user batching)
- Port: 8001
- Startup: `./scripts/start-vllm.sh`

**Performance Profile:**
- Stability-first configuration for gfx1151 (Strix Halo)
- `--enforce-eager` required for stability
- GPU memory utilization: 90%
- Max concurrent sequences: 8

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

## Streaming Responses

The chat stack supports progressive streaming responses for a more responsive UX.

### Streaming Configuration
Set environment variables in `.env` or shell:

```bash
STREAMING_CHUNK_SIZE=1
STREAMING_TIMEOUT_SECONDS=60
```

### Streaming Path
```
CopilotKit → Agent API (/v1/chat/completions or /v1/responses)
  → responses_api_stream() → SSE response.output_text.delta events
  → CopilotChat progressive rendering
```

### Monitoring
```bash
tail -f ~/BestBox/logs/agent_api.log | grep "STREAMING METRICS" -A 7
tail -f ~/BestBox/logs/agent_api.log | grep "STREAMING CHECK"
```

### Performance Targets
- TTFT (time to first token): < 500ms
- Smooth progressive chunk display during generation

### Troubleshooting
1. Verify stream flag logs show `stream flag: True`
2. Verify `STREAMING_CHUNK_SIZE` and `STREAMING_TIMEOUT_SECONDS`
3. Restart Agent API after env changes
4. Check `[STREAMING ERROR]` and `[STREAMING METRICS]` logs

## Adding a New Agent

1. Create agent file: `agents/new_agent.py` (follow pattern from existing agents)
2. Define tools: `tools/new_tools.py` using `@tool` decorator
3. Register in `agents/graph.py`:
   - Add node: `graph.add_node("new_agent", create_new_agent_node())`
   - Add edges for routing and tool handling
4. Update router system prompt in `agents/router.py` to recognize the new domain

## GPU Notes

Backend detection priority:
1. `BESTBOX_GPU_BACKEND` environment variable
2. `.bestbox/config` (`gpu_backend=...`)
3. Auto-detect (`nvidia-smi` → `rocm-smi|rocminfo` → `cpu`)

### AMD ROCm
The system uses AMD ROCm 7.2.0 for vLLM. Key environment variables are set in `activate.sh`:
```bash
HSA_OVERRIDE_GFX_VERSION=11.0.0  # Maps gfx1151 → gfx1100
PYTORCH_ROCM_ARCH=gfx1151
```

vLLM runs in Docker with ROCm GPU access (/dev/kfd, /dev/dri). The Qwen3-30B model is loaded from ModelScope cache at `~/.cache/modelscope/hub/models/`.

**Important:** The `--enforce-eager` flag is required for stability on gfx1151 (Strix Halo). HIP Graphs cause driver timeouts without this flag.

### NVIDIA CUDA
Use the unified activation + compose overlays:
```bash
BESTBOX_GPU_BACKEND=cuda source activate.sh
docker compose $BESTBOX_COMPOSE_FILES up -d
```

Key environment variables:
```bash
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
