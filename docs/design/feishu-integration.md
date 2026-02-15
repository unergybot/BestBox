# Feishu Integration Plan (Current)

Last updated: 2026-02-14

The project-level Feishu deployment strategy and priority order now lives in:
- `docs/design/deployment-plan.md`

## Scope

Feishu integration is split into two tracks:
1. **Document sync (priority)** — ingest Feishu docs/wiki into BestBox RAG pipeline.
2. **Bot channel relay (secondary)** — route Feishu chat messages to agent API.

## Security Requirements

- Never commit Feishu credentials in code or docs.
- Use environment variables only:
  - `FEISHU_APP_ID`
  - `FEISHU_APP_SECRET`

## Next Implementation Step

Implement `scripts/sync_feishu_docs.py` following the Week 1-2 tasks in
`docs/design/deployment-plan.md`.
