# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BestBox is an enterprise agentic applications demo kit running on AMD hardware (Ryzen AI Max+ 395, Radeon 8060S GPU). It demonstrates multi-agent orchestration using LangGraph with four specialized agents: ERP, CRM, IT Ops, and Office Automation. The system runs entirely on-premise with local LLM inference via llama.cpp and Vulkan backend.

## Common Commands

### Environment Activation
```bash
source ~/BestBox/activate.sh  # Activates venv and sets ROCm environment variables
```

### Start Services
```bash
# Infrastructure (run first)
docker compose up -d                    # Qdrant, PostgreSQL, Redis

# Backend services (each in separate terminal)
./scripts/start-llm.sh                  # LLM server on :8080
./scripts/start-embeddings.sh           # Embeddings on :8081
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
curl http://localhost:8080/health       # LLM server
curl http://localhost:8081/health       # Embeddings
curl http://localhost:8000/health       # Agent API
```

## Architecture

### Multi-Agent System
```
User Query → Router Agent → {ERP, CRM, IT Ops, OA, Fallback} Agent → Tool Node → Response
```

The router (`agents/router.py`) classifies intent and routes to domain-specific agents. Each agent has access to domain tools defined in `tools/`.

### Key Directories
- `agents/` - LangGraph agent implementations and state management
- `tools/` - Tool definitions (erp_tools.py, crm_tools.py, it_ops_tools.py, oa_tools.py)
- `services/` - FastAPI backends (agent_api.py, embeddings/main.py)
- `frontend/copilot-demo/` - Next.js + CopilotKit UI
- `scripts/` - Startup scripts and tests

### Service Ports
| Service | Port |
|---------|------|
| LLM (llama-server) | 8080 |
| Embeddings (BGE-M3) | 8081 |
| Agent API | 8000 |
| Frontend | 3000 |
| Qdrant | 6333/6334 |
| PostgreSQL | 5432 |
| Redis | 6379 |

### Agent State (`agents/state.py`)
- `messages` - Conversation history
- `current_agent` - Active agent (erp, crm, it_ops, oa)
- `tool_calls` - SLA counter (max 5)
- `confidence` - Classification confidence (0.0-1.0)

### LLM Configuration
- Model: Qwen2.5-14B-Instruct-Q4_K_M via llama.cpp
- Backend: Vulkan (not HIP/ROCm directly - llama.cpp uses Vulkan for gfx1151)
- Context: 4096 tokens
- Performance: ~527 tok/s prompt processing, ~24 tok/s generation

## Adding a New Agent

1. Create agent file: `agents/new_agent.py` (follow pattern from existing agents)
2. Define tools: `tools/new_tools.py` using `@tool` decorator
3. Register in `agents/graph.py`:
   - Add node: `graph.add_node("new_agent", create_new_agent_node())`
   - Add edges for routing and tool handling
4. Update router system prompt in `agents/router.py` to recognize the new domain

## ROCm/GPU Notes

The system uses AMD ROCm 7.2.0. Key environment variables are set in `activate.sh`:
```bash
HSA_OVERRIDE_GFX_VERSION=11.0.0  # Maps gfx1151 → gfx1100
PYTORCH_ROCM_ARCH=gfx1100
```

llama.cpp uses Vulkan backend (not HIP) because Vulkan has better support for gfx1151 (RDNA 3.5). The LLM server runs natively, not in Docker, for better GPU access.

## Frontend Architecture

Next.js 16 with CopilotKit integration:
- `app/page.tsx` - Main UI with scenario selector
- `app/api/copilotkit/route.ts` - Bridges to Python agent API at :8000
- Uses React 19 and Tailwind CSS 4

## Documentation

- `docs/system_design.md` - Complete architecture specification (800+ lines)
- `docs/rocm_deployment_guide.md` - Hardware and ROCm setup
- `docs/PROJECT_STATUS.md` - Current development status
