# Copilot instructions (BestBox)

## Big picture
- BestBox is an on-prem enterprise multi-agent system with **OpenClaw as control plane**.
- **OpenClaw Gateway** (`:18789`) routes messages from channels (WhatsApp/Telegram/Slack/Discord/Signal/iMessage) → `bestbox` tool → BestBox Agent API (`:8000`).
- BestBox Agent API hosts LangGraph multi-agent graph: Router → {ERP, CRM, IT Ops, OA} agents → domain tools + RAG.
- The router in `agents/router.py` classifies intent; agents wired in `agents/graph.py`.
- RAG uses Qdrant + (optional) reranker: documents in `data/demo_docs/{erp,crm,itops,oa}/`, indexed via `scripts/seed_knowledge_base.py`.

## Architecture (OpenClaw + BestBox)
```
WhatsApp/Telegram/Slack/Discord/Signal/iMessage
                    │
                    ▼
         OpenClaw Gateway (:18789)  ← control plane
                    │
                    ▼
           bestbox tool (extension)
                    │
                    ▼
         BestBox Agent API (:8000)
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
  Router → ERP/CRM/IT Ops/OA → Tools + RAG
```

## Local dev workflow (known-good)
- Activate env (sets GPU env vars): `source ~/BestBox/activate.sh`.
- Start infra first: `docker compose up -d` (Qdrant/Postgres/Redis).
- Start BestBox services (separate terminals): `./scripts/start-llm.sh` (8080), `./scripts/start-embeddings.sh` (8081), `./scripts/start-agent-api.sh` (8000).
- Start OpenClaw Gateway: `openclaw gateway run --port 18789` (enable `bestbox` plugin first).
- Optional standalone frontend: `cd frontend/copilot-demo && npm run dev` (3000).

## Code map / where to change things
- Agent orchestration: `agents/graph.py`, agent state in `agents/state.py`.
- Domain tools: `tools/*.py` (tools are exposed via `@tool`; keep signatures typed).
- HTTP API + health: `services/agent_api.py`.
- Speech-to-speech: `services/speech/s2s_server.py`, `services/speech/asr.py`, `services/speech/tts.py`; TTS is off by default—enable via `S2S_ENABLE_TTS=true`.
- Frontend bridge to backend: `frontend/copilot-demo/app/api/copilotkit/route.ts`.

## Plugins
- Skills: `skills/**/SKILL.md` (YAML frontmatter).
- Full plugins: `plugins_contrib/` + `plugins/` (manifest `bestbox.plugin.json`).
- Discovery order (highest priority first): bundled (`skills/`, `plugins_contrib/`) → global (`~/.bestbox/plugins/`) → workspace (`.bestbox/plugins/`).

## Tests
- Python agent tests: `python scripts/test_agents.py` (integration-style).
- Broader suite: `./scripts/run_integration_tests.sh --fast|--full`.

## OpenClaw Integration
- The `bestbox` extension lives at `~/openclaw/extensions/bestbox/`.
- Enable: `openclaw plugins enable bestbox`.
- Configure: `openclaw config set plugins.entries.bestbox.config.apiUrl "http://localhost:8000"`.
- The extension registers a `bestbox` tool that forwards enterprise queries to the Agent API.
