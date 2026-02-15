# BestBox Customer Deployment Plan

Last updated: 2026-02-14

This document is the single source of truth for what BestBox has today, what it
needs for a real customer deployment, and how to get there.

---

## Part I — Honest Assessment of Current State

### What is production-ready today

| Capability | Implementation | Evidence |
|---|---|---|
| Multi-agent router + 6 domain agents | LangGraph StateGraph with structured routing | `agents/graph.py`, `agents/router.py` |
| Plugin/skill extensibility | Loader → Registry → API with lifecycle hooks | `plugins/` package, `skills/` directory |
| RAG pipeline (generic KB) | Embed → Qdrant hybrid search → reranker → citations | `tools/rag_tools.py`, `services/rag_pipeline/` |
| Troubleshooting hybrid search | AUTO/STRUCTURED/SEMANTIC/HYBRID with SQL+vector fusion | `services/troubleshooting/hybrid_searcher.py` |
| Admin RBAC + audit trail | JWT + OIDC (Authelia), 3 roles, audit_log table | `services/admin_auth.py`, `migrations/005_admin_rbac.sql` |
| Voice input (ASR) | FunASR/Whisper with WebSocket streaming | `services/speech/s2s_server.py` |
| Observability | Prometheus + Grafana + Jaeger + OTel collector | `docker-compose.yml`, `config/` |
| ERPNext live connector | REST client with availability caching + demo fallback | `services/erpnext_client.py`, `tools/erp_tools.py` |
| Knowledge seeding | Docling ingest → tiktoken chunking → BGE-M3 → Qdrant | `scripts/seed_knowledge_base.py` |

### What is incomplete or demo-only

| Gap | Severity for customer deploy | Current state |
|---|---|---|
| **CRM tools** — mock data only | BLOCKER | `tools/crm_tools.py` reads `demo_data.json`, no live CRM API |
| **IT Ops tools** — hardcoded returns | BLOCKER | `tools/it_ops_tools.py` returns static strings |
| **OA tools** — hardcoded returns | BLOCKER | `tools/oa_tools.py` returns static dicts |
| **Agent-level RBAC** — no user identity on tool calls | BLOCKER | `AgentState` has no `user_context` field |
| **Knowledge base** — tiny demo corpus | HIGH | 5 sample markdown files across 5 domains |
| **No customer onboarding automation** | HIGH | No script/wizard that populates a customer's KB from their docs |
| **No OpenAPI dynamic tools** | MEDIUM | Every API integration is hand-coded Python |
| **TTS** — disabled by default, hangs at init | LOW | Lazy-loaded behind `S2S_ENABLE_TTS=false` |
| **No multi-tenant isolation** | MEDIUM | Single-tenant, single-org only |
| **Secrets in repo files** | CRITICAL | API keys found in `README.md`, old design docs |

---

## Part II — What Actually Matters for Customer Deployment

After reading every tool, every agent, every service file, and the
infrastructure configs, these are the real priorities.

### Priority 1 — Build a Solid Knowledge Base (the #1 value driver)

The agent is only as good as the data it can access. Today the KB is 5 tiny
sample markdowns. A customer deployment needs:

#### 1a. Customer Document Ingestion Pipeline

The pipeline components already exist individually but not as an end-to-end
tool the customer can use:

```
Customer docs         scripts/seed_knowledge_base.py
  (PDF/DOCX/MD)  →  DocumentIngester (Docling)
                  →  TextChunker (512 tokens, 20% overlap)
                  →  EmbeddingService (BGE-M3 @ :8081)
                  →  Qdrant (hybrid dense + BM25 sparse)
```

**What to build:**

- **Admin UI batch upload** — extend the existing admin portal
  (`/en/admin`) to accept ZIP/folder of customer docs with domain tagging
- **Incremental re-index** — track `file_hash` + `indexed_at` to avoid
  re-processing unchanged documents
- **Domain auto-detection** — use the router LLM to classify documents
  into domains during ingestion, or accept a simple folder→domain mapping
- **Quality metrics** — after seeding, report chunk count, domain
  distribution, and sample search quality checks

#### 1b. Customer's Existing Knowledge Sources

Most manufacturing/enterprise customers have knowledge in:

| Source | Integration method |
|---|---|
| SOPs, manuals (PDF/DOCX) | Docling → existing pipeline |
| Feishu/Lark Wiki | Feishu Open API → Markdown export → pipeline |
| Confluence/SharePoint | REST API → HTML-to-MD → pipeline |
| Mold trial records (XLSX) | Already working via admin portal + `mold_case_extractor.py` |
| ERP master data | Should query live API, not index statically |
| Chat/email decisions | Low priority — index pinned messages only |

#### 1c. Knowledge Freshness Strategy

- **Static docs** → re-index on change (webhook or scheduled)
- **Live API data** → always query at tool-call time (already done for ERP)
- **Hybrid** — cache expensive API results in Redis (60s TTL) for repeated
  questions in the same session

### Priority 2 — Make Tool Integrations Real (not demo stubs)

The ERP tools already have the right pattern: try ERPNext API first, fall back
to demo data. The other domains don't.

#### 2a. Tool Adapter Pattern

Introduce a `tools/adapters/` layer so tool functions don't encode any
specific backend:

```python
# tools/adapters/base.py
class BackendAdapter(Protocol):
    def is_available(self) -> bool: ...
    def query(self, operation: str, params: dict) -> dict: ...

# tools/adapters/erpnext.py (already exists as services/erpnext_client.py)
# tools/adapters/odoo.py (future)
# tools/adapters/sap.py (future)
```

Per-customer config selects which adapter to use:

```yaml
# config/customer.yaml
integrations:
  erp:
    backend: erpnext        # or "odoo", "sap"
    url: http://erp.customer.local
    auth: env:ERP_API_KEY
  crm:
    backend: erpnext_crm    # or "hubspot", "salesforce"
    url: http://crm.customer.local
    auth: env:CRM_API_KEY
  it_ops:
    backend: zabbix          # or "prometheus_api", "datadog"
    url: http://monitoring.customer.local
```

#### 2b. OpenAPI Auto-Tool Generation (Phase 2)

For systems with OpenAPI specs, generate LangChain tools dynamically:

```python
# tools/discovery/openapi_loader.py
def load_tools_from_spec(
    spec_url: str,
    allowlist: list[str],       # Only these endpoint patterns
    auth_header: str = None,
) -> list[BaseTool]:
    """Parse OpenAPI spec, create one tool per allowed endpoint."""
```

This eliminates hand-coding for every new customer system.

#### 2c. Immediate Fixes for Demo Agents

Before adapter pattern is ready, make the stub tools useful:

- **CRM**: Connect to ERPNext CRM module (it has Customer, Lead,
  Opportunity doctypes) — same pattern as `erp_tools.py`
- **IT Ops**: Connect to Prometheus API (`/api/v1/query`) for real
  metrics, or accept Zabbix/Grafana endpoint
- **OA**: Connect to calendar API (Google/Outlook) or return "not
  configured" instead of fake data

### Priority 3 — Agent-Level Security (enterprise deal-breaker)

#### 3a. User Context in AgentState

```python
# agents/state.py — add to AgentState
class UserContext(TypedDict, total=False):
    user_id: str                  # "bob@customer.com"
    roles: List[str]              # ["procurement", "viewer"]
    org_id: str                   # tenant isolation
    permissions: List[str]        # ["erp:read", "crm:read", "crm:write"]

class AgentState(TypedDict):
    # ... existing fields ...
    user_context: Optional[UserContext]   # NEW
```

#### 3b. Injection Point

In `services/agent_api.py`, extract user from JWT (already decoded by
`admin_auth.py`) and inject into `AgentState` before graph invocation:

```python
inputs: AgentState = {
    "messages": lc_messages,
    "current_agent": "router",
    "tool_calls": 0,
    "user_context": {                    # NEW
        "user_id": jwt_claims["username"],
        "roles": jwt_claims.get("groups", []),
        "org_id": jwt_claims.get("org", "default"),
    },
    ...
}
```

#### 3c. Tool-Level Enforcement

High-risk tools check permissions. Pattern:

```python
@tool
def get_financial_summary(period: str, state: AgentState = None):
    user = (state or {}).get("user_context", {})
    if "finance" not in user.get("roles", []):
        return {"error": "Permission denied: requires finance role"}
```

#### 3d. Audit Trail for Tool Execution

Extend `audit_log` table to record every tool call with user, tool name,
params hash, result status, and latency. The hook system already has
`AFTER_TOOL_CALL` — wire it to the audit writer.

### Priority 4 — Deployment Packaging

#### 4a. Customer Deployment Bundle

```
bestbox-deploy/
├── docker-compose.customer.yml    # Minimal: Qdrant, Postgres, Redis
├── config/
│   ├── customer.yaml              # Per-customer integrations config
│   └── authelia/                   # SSO config templates
├── scripts/
│   ├── setup-customer.sh          # One-command initial setup
│   ├── seed-customer-kb.sh        # Ingest customer docs
│   └── health-check.sh            # Verify all services
├── systemd/                        # Service units for production
│   ├── bestbox-api.service
│   ├── bestbox-embeddings.service
│   └── bestbox-reranker.service
└── docs/
    └── DEPLOYMENT.md              # Customer-facing setup guide
```

#### 4b. Configuration Externalization

Move all hardcoded values to a single `config/customer.yaml`:

- LLM endpoint and model name
- Embedding service URL
- Qdrant collection names
- ERP/CRM/IT Ops backend URLs and auth
- Domain-to-agent mapping
- Knowledge base source directories
- RBAC role-to-permission mapping

#### 4c. Secret Management

- Remove all credentials from tracked files immediately
- Use `.env` files (gitignored) for dev, environment variables for production
- Document which env vars each service requires

---

## Part III — Execution Plan

### Week 0: Security + Cleanup (2 days)

- [ ] Rotate all exposed credentials (Nvidia API key, ERPNext password, Feishu secrets)
- [ ] Add `.env.example` with all required variables (no values)
- [ ] Add `detect-secrets` or `gitleaks` pre-commit hook
- [ ] Remove credential values from `README.md` lines 430-470
- [ ] Create `config/customer.yaml.example` template

### Week 1-2: Knowledge Base Foundation

- [ ] Build admin batch-upload endpoint for document folders
- [ ] Add document deduplication (file hash tracking in Postgres)
- [ ] Add domain auto-tag or folder-to-domain mapping
- [ ] Create `scripts/seed-customer-kb.sh` wrapper
- [ ] Build Feishu Docs sync script (`scripts/sync_feishu_docs.py`)
- [ ] Write post-seed quality report (chunk stats, sample queries)
- [ ] Test with 50+ real documents from target customer domain

### Week 3-4: Tool Integration Layer

- [ ] Create `tools/adapters/base.py` with `BackendAdapter` protocol
- [ ] Refactor `services/erpnext_client.py` into `tools/adapters/erpnext.py`
- [ ] Connect CRM tools to ERPNext CRM module (real API, demo fallback)
- [ ] Connect IT Ops to Prometheus API (or stub with "not configured")
- [ ] Add `config/customer.yaml` loader for per-deployment backend selection
- [ ] Build `tools/discovery/openapi_loader.py` MVP (generate tools from spec)
- [ ] Test: add a new system endpoint in <30 minutes via config, not code

### Week 5-6: Security + Multi-User

- [ ] Add `UserContext` to `AgentState`
- [ ] Inject user identity from JWT into agent invocation path
- [ ] Add permission checks to `get_purchase_orders`, `get_financial_summary`
- [ ] Wire `AFTER_TOOL_CALL` hook to audit_log with user context
- [ ] Test: user A cannot see user B's financial data
- [ ] Document RBAC configuration in deployment guide

### Week 7-8: Deployment Packaging + Customer Pilot

- [ ] Create `docker-compose.customer.yml` (stripped of dev services)
- [ ] Write systemd service units for API, embeddings, reranker
- [ ] Create `scripts/setup-customer.sh` (one-command bootstrap)
- [ ] Create `scripts/health-check.sh` (verify all components)
- [ ] Write customer-facing `DEPLOYMENT.md`
- [ ] Run deployment dry-run on clean machine
- [ ] Pilot with first customer's actual documents and systems

---

## Part IV — Legacy System Integration Strategy

### The Real Problem

Most enterprise customers don't have clean REST APIs. They have:

| System type | Common integrations | Approach |
|---|---|---|
| Modern ERP (ERPNext, Odoo) | REST API | Direct adapter (already working) |
| SAP ECC/S4HANA | RFC/BAPI or OData | OData adapter + SAP API Business Hub |
| Oracle EBS | PL/SQL APIs or REST Gateway | Oracle REST Data Services (ORDS) adapter |
| Legacy databases | ODBC/JDBC only | Read-only SQL adapter with connection pooling |
| File-based systems | CSV/Excel exports | Scheduled file ingest → Qdrant |
| SOAP services | WSDL-defined | `zeep` client wrapper adapter |

### Recommended Architecture

```
Customer System         BestBox Adapter Layer         Agent Tools
┌──────────────┐        ┌───────────────────┐        ┌──────────────┐
│ SAP OData    │───────→│ tools/adapters/   │───────→│ @tool        │
│ Oracle ORDS  │───────→│   sap.py          │───────→│ get_purchase_│
│ ERPNext REST │───────→│   oracle.py       │        │ orders()     │
│ Custom DB    │───────→│   erpnext.py      │        │              │
│              │        │   sql_readonly.py  │        │ Tool doesn't │
│              │        │   base.py (proto)  │        │ know which   │
└──────────────┘        └───────────────────┘        │ backend runs │
                                                      └──────────────┘
```

### Key Principles

1. **Tools define business intent**, adapters handle transport
2. **Read-only by default** — never let LLM write to production systems
   without explicit human approval step
3. **Circuit breaker** — if backend is down, return "system unavailable"
   not hallucinated data
4. **Connection pooling** — reuse sessions/connections across tool calls
5. **Data transformation** — normalize all backend responses to a
   canonical schema so the LLM prompt doesn't change per backend

### Per-Customer Integration Playbook

1. Customer provides: system type, API docs or OpenAPI spec, test credentials
2. We determine: adapter class needed (existing? new? OpenAPI auto?)
3. We configure: `config/customer.yaml` with endpoint + auth
4. We test: run `scripts/test_agents.py` against customer's staging environment
5. We validate: customer SME confirms answers match expected data

---

## Part V — Knowledge Base Architecture (Deep Dive)

### Current Pipeline (working)

```
  Source Document (PDF/DOCX/MD/XLSX)
         │
         ▼
  DocumentIngester (Docling)
  ├── extract_text() → Markdown
  └── extract_metadata() → {source, domain, title}
         │
         ▼
  TextChunker (tiktoken cl100k_base)
  ├── chunk_size=512 tokens
  ├── overlap=20% (~100 tokens)
  └── output: [{text, chunk_id, token_count, section}]
         │
         ▼
  BGE-M3 Embeddings (localhost:8081)
  ├── 1024-dim dense vectors
  └── normalize=True
         │
         ▼
  Qdrant (localhost:6333)
  ├── Dense vector index (COSINE)
  ├── BM25 sparse vector index
  ├── Payload: {text, domain, source, title, section, token_count}
  └── Collection: bestbox_knowledge
```

### What's Missing for Production KB

| Gap | Impact | Fix |
|---|---|---|
| No document versioning | Can't tell if a doc was re-indexed | Add `file_hash` + `indexed_at` to payload |
| No access control on KB | All users see all docs | Add `org_id` + `visibility` to payload, filter on query |
| No chunking quality validation | Bad chunks = bad answers | Sample-test after seeding, flag short/long outliers |
| No section-aware chunking | Loses document structure | Split on headings first, then chunk within sections |
| Single collection for all domains | Works but limits per-domain tuning | Consider per-domain collections for large deployments |
| No metadata enrichment | Missing: author, date, doc type, language | Extract during ingestion, store in payload |
| No feedback loop | Can't improve retrieval | Log which chunks lead to good/bad answers, fine-tune |

### Target Architecture

```
  Multiple Source Connectors
  ├── File upload (admin portal)
  ├── Feishu Docs sync (scheduled)
  ├── Confluence/SharePoint sync
  ├── XLSX mold case extractor (existing)
  └── Watched folder (inotify)
         │
         ▼
  Unified Ingestion Pipeline
  ├── Dedup (file_hash check)
  ├── Language detection
  ├── Section-aware chunking (heading-first split)
  ├── Metadata enrichment (author, date, doc_type)
  └── Access control tagging (org_id, visibility)
         │
         ▼
  Embedding + Indexing
  ├── BGE-M3 dense (1024-dim)
  ├── BM25 sparse (hashed term vectors)
  └── Qdrant upsert with idempotent chunk IDs
         │
         ▼
  Retrieval Layer
  ├── Domain-filtered hybrid search (existing)
  ├── Cross-domain federated search (new)
  ├── Reranker (BGE-reranker-base, existing)
  └── Citation formatting with source URLs
```

---

## Part VI — Feishu Integration (Specific Guidance)

No Feishu/Lark code exists in the Python codebase today. Integration should
focus on two paths:

### Path A: Document Sync (Priority — Week 1-2)

Use Feishu Open API to pull wiki/doc content into the existing RAG pipeline:

```python
# scripts/sync_feishu_docs.py
# 1. Auth via app_id + app_secret → tenant_access_token
# 2. List spaces → list docs per space
# 3. For each doc: GET /open-apis/docx/v1/documents/{id}/raw_content
# 4. Convert to markdown
# 5. Run through DocumentIngester → TextChunker → Qdrant pipeline
# 6. Store updated_at cursor for incremental sync
```

### Path B: Bot Channel (Lower Priority)

Receive user messages from Feishu → forward to BestBox agent API → return
response. This is a thin HTTP relay that can be implemented as a plugin/skill
or via an existing gateway (e.g., OpenClaw channel connector).

Credentials must be stored in environment variables, never in code:
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`

---

## Summary: What to Build, In What Order

| Priority | Item | Why it matters | Effort |
|---|---|---|---|
| P0 | Secret rotation + `.env` cleanup | Cannot deploy with exposed keys | 1 day |
| P1 | Customer KB ingestion pipeline | Agent is useless without real data | 1 week |
| P1 | CRM/IT/OA tool adapter + real backends | 3 of 4 demo domains are stubs | 1 week |
| P1 | Agent-level RBAC (`user_context`) | Enterprise deal-breaker | 3 days |
| P2 | Tool execution audit trail | Compliance requirement | 2 days |
| P2 | OpenAPI dynamic tool loader | Scales to new customer systems | 1 week |
| P2 | Feishu/Confluence doc sync | Knowledge freshness | 3 days |
| P2 | Deployment packaging + health checks | Repeatable customer installs | 3 days |
| P3 | Multi-tenant isolation | Multiple orgs on same instance | 1 week |
| P3 | Feedback loop (answer quality tracking) | Continuous improvement | 1 week |
| P3 | TTS stabilization | Only if voice output required | 3 days |

**Critical path to first customer deployment: P0 → P1 items → P2 deployment packaging = ~4 weeks.**
