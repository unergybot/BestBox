# Agentic RAG with ReAct Reasoning — BestBox Design

**Date:** 2026-02-04
**Status:** Draft
**Phase:** Demo Enhancement

## Overview

This design adds intelligent agent behavior to BestBox for an impressive stakeholder demo. The agent will show visible reasoning, drill down across data sources, and enable admin monitoring.

### Goals

1. **Impressive demo** — Agent shows thinking, reasons through complex questions
2. **Multi-source synthesis** — Combines documents + ERPNext data in answers
3. **Basic observability** — Admin can review conversations, understand performance

### Non-Goals (This Phase)

- Production-ready scaling
- Full admin dashboard with analytics
- User authentication/multi-tenancy

## Features (Priority Order)

| # | Feature | Description |
|---|---------|-------------|
| 1 | ReAct reasoning trace | Visible Think→Act→Observe loop |
| 2 | Hybrid routing | Router hints domain, agent can cross-domain |
| 3 | Session logging | Save all conversations to PostgreSQL |
| 4 | Admin UI | Review sessions, see traces, rate quality |
| 5 | Context compression | Summarize old turns when near token limit |
| 6 | Hybrid search | Dense + BM25 retrieval |

## Architecture

### Current Flow (Unchanged)

```
User → Router → Domain Agent → Tools → Response
         ↓
    /chat endpoint
```

### New ReAct Flow (Parallel Path)

```
User → Router (with hints) → ReAct Node → Response
              ↓                    ↓
    primary + secondary      Think → Act → Observe → Loop
         domains                    ↓
                            All tools available
              ↓
       /chat/react endpoint
```

### Key Decision: Parallel Deployment

The ReAct graph runs alongside the existing system:
- `/chat` — Current behavior (unchanged)
- `/chat/react` — New ReAct behavior

**Rationale:** No risk to existing functionality. Demo uses ReAct path; can switch back if issues.

## Detailed Design

### 1. ReAct Node

**Location:** `agents/react_node.py`

```python
class ReasoningStep(TypedDict):
    type: Literal["think", "act", "observe", "answer"]
    content: str
    tool_name: Optional[str]
    tool_args: Optional[dict]
    timestamp: float

def react_node(state: AgentState) -> AgentState:
    """
    ReAct loop: Think → Act → Observe → repeat until answer
    Max 5 iterations to prevent infinite loops.
    """
    reasoning_trace = []
    max_iterations = 5

    for i in range(max_iterations):
        # 1. THINK: Ask LLM what to do next
        thought = llm.invoke(REACT_PROMPT, state, reasoning_trace)
        reasoning_trace.append({
            "type": "think",
            "content": thought.reasoning,
            "timestamp": time.time()
        })

        # 2. DECIDE: Tool call or final answer?
        if thought.action == "answer":
            reasoning_trace.append({
                "type": "answer",
                "content": thought.response,
                "timestamp": time.time()
            })
            break

        # 3. ACT: Call the tool
        reasoning_trace.append({
            "type": "act",
            "tool_name": thought.tool,
            "tool_args": thought.args,
            "timestamp": time.time()
        })
        result = call_tool(thought.tool, thought.args)

        # 4. OBSERVE: Record result
        reasoning_trace.append({
            "type": "observe",
            "content": str(result),
            "timestamp": time.time()
        })

    return {**state, "reasoning_trace": reasoning_trace}
```

**ReAct Prompt:**

```
You are an assistant that thinks step-by-step to answer questions.

Router analysis:
- Primary domain: {primary_domain}
- Secondary domains: {secondary_domains}
- Reasoning: {router_reasoning}

Available tools (by relevance):

## {primary_domain} Tools (recommended)
{primary_tools}

## Other Tools (available if needed)
{other_tools}

Previous reasoning steps:
{reasoning_trace}

User question: {question}

Decide your next action. Respond in JSON:
{
  "reasoning": "What I'm thinking and why...",
  "action": "tool" | "answer",
  "tool": "tool_name (if action=tool)",
  "args": { ... (if action=tool) },
  "response": "final answer (if action=answer)"
}
```

### 2. State Changes

**Location:** `agents/state.py`

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    current_agent: str
    tool_calls: int
    confidence: float
    context: dict
    plan: list
    step: int
    plugin_context: dict
    # NEW
    reasoning_trace: List[ReasoningStep]
    session_id: Optional[str]
```

### 3. Hybrid Router

**Location:** `agents/router.py`

```python
class RouteDecision(BaseModel):
    primary_domain: str          # "erp", "crm", "itops", "oa", "general"
    secondary_domains: List[str] # Other relevant domains
    confidence: float
    reasoning: str               # Why this routing decision

# Router prompt addition:
"""
Analyze the user's question and determine:
1. Primary domain (most relevant)
2. Secondary domains (might also be needed)
3. Your reasoning

Example: "Why is Q4 procurement high and what's the IT policy?"
→ Primary: erp (procurement data)
→ Secondary: ["itops"] (policy documents)
"""
```

### 4. Session Storage

**Location:** `services/session_store.py`

**PostgreSQL Schema:**

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    channel VARCHAR(50),  -- 'web', 'api', etc.
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    message_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'completed', 'error'
    metadata JSONB
);

CREATE TABLE session_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id),
    role VARCHAR(20),  -- 'user', 'assistant', 'tool'
    content TEXT,
    reasoning_trace JSONB,  -- ReAct steps for assistant messages
    tool_calls JSONB,
    tokens_prompt INT,
    tokens_completion INT,
    latency_ms INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_started ON sessions(started_at DESC);
CREATE INDEX idx_messages_session ON session_messages(session_id);
```

**Session Store Interface:**

```python
class SessionStore:
    async def create_session(self, user_id: str, channel: str) -> str:
        """Create new session, return session_id."""

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        reasoning_trace: List[dict] = None,
        tool_calls: List[dict] = None,
        metrics: dict = None
    ):
        """Add message to session."""

    async def get_session(self, session_id: str) -> dict:
        """Get session with all messages."""

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: str = None,
        status: str = None
    ) -> List[dict]:
        """List sessions for admin view."""

    async def update_session_status(self, session_id: str, status: str):
        """Mark session completed/error."""
```

### 5. Context Compression

**Location:** `agents/context_manager.py`

```python
async def compress_if_needed(
    messages: List[Message],
    token_budget: int = 6000,
    keep_recent: int = 4
) -> List[Message]:
    """
    If history exceeds budget, summarize older turns.
    Keeps last `keep_recent` turns intact.
    """
    current_tokens = estimate_tokens(messages)

    if current_tokens <= token_budget:
        return messages

    # Split old vs recent
    if len(messages) <= keep_recent:
        return messages  # Can't compress further

    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]

    # Summarize old messages
    summary = await llm.ainvoke(
        COMPRESSION_PROMPT.format(messages=format_messages(old_messages))
    )

    # Return summary + recent
    return [
        SystemMessage(content=f"Previous conversation summary:\n{summary}"),
        *recent_messages
    ]

COMPRESSION_PROMPT = """
Summarize this conversation history concisely.
Preserve key facts, decisions, and context needed to continue the conversation.

Conversation:
{messages}

Summary:
"""
```

### 6. Admin API Endpoints

**Location:** `services/agent_api.py`

```python
@app.get("/admin/sessions")
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    user_id: str = None,
    status: str = None,
    admin_token: str = Header(...)
):
    """List sessions for admin review."""
    verify_admin_token(admin_token)
    return await session_store.list_sessions(limit, offset, user_id, status)

@app.get("/admin/sessions/{session_id}")
async def get_session(session_id: str, admin_token: str = Header(...)):
    """Get full session with messages and reasoning traces."""
    verify_admin_token(admin_token)
    return await session_store.get_session(session_id)

@app.post("/admin/sessions/{session_id}/rating")
async def rate_session(
    session_id: str,
    rating: Literal["good", "bad"],
    note: str = None,
    admin_token: str = Header(...)
):
    """Admin rates a session for quality tracking."""
    verify_admin_token(admin_token)
    return await session_store.add_rating(session_id, rating, note)
```

### 7. Frontend Components

**ReAct Trace Display:** `frontend/copilot-demo/components/ReasoningTrace.tsx`

```tsx
interface ReasoningStep {
  type: 'think' | 'act' | 'observe' | 'answer';
  content: string;
  tool_name?: string;
  tool_args?: Record<string, any>;
  timestamp: number;
}

export function ReasoningTrace({ steps }: { steps: ReasoningStep[] }) {
  return (
    <div className="reasoning-trace">
      {steps.map((step, i) => (
        <div key={i} className={`step step-${step.type}`}>
          {step.type === 'think' && (
            <><span className="icon">🤔</span> Thinking: {step.content}</>
          )}
          {step.type === 'act' && (
            <><span className="icon">🔧</span> Action: {step.tool_name}({formatArgs(step.tool_args)})</>
          )}
          {step.type === 'observe' && (
            <><span className="icon">📊</span> Observation: {truncate(step.content, 200)}</>
          )}
          {step.type === 'answer' && (
            <><span className="icon">💡</span> Answer: {step.content}</>
          )}
        </div>
      ))}
    </div>
  );
}
```

**Admin Page:** `frontend/copilot-demo/app/admin/page.tsx`

- Session list with filters (date, user, status)
- Expandable session detail with full ReAct trace
- Metrics display (latency, tokens, tool calls)
- Rating buttons (good/bad) with notes

### 8. Hybrid Search (from agentic-rag-for-dummies)

**Location:** `tools/rag_tools.py`

Enable BM25 sparse vectors in existing Qdrant setup:

```python
async def search_knowledge_base_hybrid(
    query: str,
    domain: str = "all",
    top_k: int = 5,
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3
) -> List[dict]:
    """
    Hybrid search combining dense (semantic) and sparse (BM25) vectors.
    """
    # Get dense embedding
    dense_vector = await get_embedding(query)

    # Get sparse (BM25) representation
    sparse_vector = get_bm25_vector(query)

    # Query Qdrant with both
    results = await qdrant.query_points(
        collection_name="bestbox_knowledge",
        query_vector=("dense", dense_vector),
        query_sparse_vector=("sparse", sparse_vector),
        score_weights={"dense": dense_weight, "sparse": sparse_weight},
        limit=top_k,
        query_filter=build_domain_filter(domain) if domain != "all" else None
    )

    return format_results(results)
```

**Seeding update:** `scripts/seed_knowledge_base.py`
- Add BM25 tokenization during ingestion
- Store sparse vectors alongside dense vectors

## File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `agents/react_node.py` | ReAct loop implementation |
| `services/session_store.py` | PostgreSQL session persistence |
| `frontend/.../components/ReasoningTrace.tsx` | Trace display component |
| `frontend/.../app/admin/page.tsx` | Admin session review page |

### Modified Files

| File | Changes |
|------|---------|
| `agents/state.py` | Add `reasoning_trace`, `session_id` fields |
| `agents/graph.py` | Add parallel ReAct graph, new endpoint |
| `agents/router.py` | Add `secondary_domains` to RouteDecision |
| `agents/context_manager.py` | Add compression logic |
| `services/agent_api.py` | Add `/chat/react`, `/admin/*` endpoints |
| `tools/rag_tools.py` | Add hybrid search function |
| `scripts/seed_knowledge_base.py` | Add BM25 vector generation |

### Unchanged

- All domain agents (ERP, CRM, IT Ops, OA)
- All existing tools
- Current `/chat` endpoint behavior
- Plugin hooks system
- ERPNext integration

## Database Migrations

```sql
-- migrations/001_add_sessions.sql

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    channel VARCHAR(50),
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    message_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    rating VARCHAR(10),  -- 'good', 'bad', NULL
    rating_note TEXT,
    metadata JSONB
);

CREATE TABLE session_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    reasoning_trace JSONB,
    tool_calls JSONB,
    tokens_prompt INT,
    tokens_completion INT,
    latency_ms INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_started ON sessions(started_at DESC);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_messages_session ON session_messages(session_id);
```

## Configuration

Add to `.env`:

```bash
# ReAct settings
REACT_MAX_ITERATIONS=5
REACT_ENABLED=true

# Session storage
SESSION_STORE_ENABLED=true

# Context compression
CONTEXT_TOKEN_BUDGET=6000
CONTEXT_KEEP_RECENT=4

# Hybrid search weights
RAG_DENSE_WEIGHT=0.7
RAG_SPARSE_WEIGHT=0.3

# Admin
ADMIN_TOKEN=your-secure-token-here
```

## Demo Scenarios

### Scenario 1: Cross-Domain Query

**User:** "Why is Q4 procurement cost higher than Q3?"

**ReAct Trace:**
1. 🤔 Think: Need Q3 and Q4 procurement data for comparison
2. 🔧 Act: `get_procurement_summary(period="Q3-2025")`
3. 📊 Observe: Q3 total ¥1,245,000
4. 🔧 Act: `get_procurement_summary(period="Q4-2025")`
5. 📊 Observe: Q4 total ¥1,890,000, new vendor added
6. 🤔 Think: 52% increase, new vendor is factor. Check if policy exists.
7. 🔧 Act: `search_knowledge_base("new vendor onboarding policy")`
8. 📊 Observe: Found policy about initial bulk orders
9. 💡 Answer: Q4 is 52% higher due to new vendor onboarding...

### Scenario 2: Drill-Down Query

**User:** "Is our main warehouse running low on anything?"

**ReAct Trace:**
1. 🤔 Think: Check WH-001 inventory for low stock
2. 🔧 Act: `get_inventory_levels(warehouse_id="WH-001")`
3. 📊 Observe: 3 items with LOW_STOCK alert
4. 🤔 Think: Found low stock items. Check if POs exist for these.
5. 🔧 Act: `get_purchase_orders(status="Draft")`
6. 📊 Observe: No pending POs for low stock items
7. 💡 Answer: Yes, 3 items are low. No purchase orders pending...

## Success Criteria

1. **Demo Impact**
   - Stakeholders can see agent "thinking" in real-time
   - Agent successfully combines ERP data + documents in answers
   - Agent drills down without user prompting

2. **Observability**
   - All sessions logged with full traces
   - Admin can review any session
   - Basic metrics visible (latency, tokens, tool calls)

3. **Safety**
   - Existing `/chat` endpoint unchanged
   - Can disable ReAct via config
   - Max iterations prevent runaway loops

## Implementation Order

| Phase | Tasks | Estimate |
|-------|-------|----------|
| 1 | ReAct node + state changes + parallel graph | 2 days |
| 2 | Hybrid router (secondary domains) | 0.5 day |
| 3 | Session storage (PostgreSQL) | 1 day |
| 4 | Frontend ReAct trace display | 1 day |
| 5 | Admin UI (session list + detail) | 1.5 days |
| 6 | Context compression | 0.5 day |
| 7 | Hybrid search (BM25) | 1 day |
| **Total** | | **~7-8 days** |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ReAct loops too long | Slow responses | Max iterations (5), timeout |
| LLM doesn't follow JSON format | Broken reasoning | Structured output, fallback parsing |
| Cross-domain confusion | Wrong tools called | Router hints + prioritized tool list |
| Session storage overhead | Latency | Async writes, batch inserts |

## Future Enhancements (Post-Demo)

- Parent-child chunking for better retrieval
- Query clarification (HITL) when ambiguous
- Analytics dashboard with quality metrics
- Multi-user session management
- Conversation export/replay

---

## References

- [agentic-rag-for-dummies](../plans/2026-02-04-agentic-rag-for-dummies-integration.md) — Source of hybrid search concepts
- [openclaw](../../) — Inspiration for session logging and context compression
- [ReAct Paper](https://arxiv.org/abs/2210.03629) — Original ReAct reasoning pattern
