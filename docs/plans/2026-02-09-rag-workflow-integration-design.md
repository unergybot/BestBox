# RAG Pipeline Integration with Workflows and Pi Agent

**Date:** 2026-02-09
**Status:** Approved
**Goal:** Full RAG integration with workflow canvas system - add composable RAG nodes, enable Pi Agent RAG access, and provide pre-built RAG workflow templates

## Overview

This design adds comprehensive RAG (Retrieval-Augmented Generation) capabilities to the BestBox workflow canvas system. The integration provides three key capabilities:

1. **Composable RAG Nodes** - Multiple node types (Search, Rerank, Synthesize, Multi-Domain) that can be connected in workflows
2. **Pi Agent RAG Access** - Enable Pi Coding Agent to call `search_knowledge_base` tool directly
3. **Workflow Templates** - Pre-built RAG workflow patterns (Documentation assistant, Code+context, Multi-domain aggregator, Iterative research)

This builds on the existing RAG pipeline (`tools/rag_tools.py`) and LangGraph workflow system.

## Current System Analysis

**Existing RAG Infrastructure:**
- ✅ RAG tools: `search_knowledge_base`, `search_knowledge_base_hybrid` in `tools/rag_tools.py`
- ✅ Embeddings service (BGE-M3) on port 8004
- ✅ Reranker service (BGE-reranker-v2-m3) on port 8004
- ✅ Qdrant vector database on port 6333
- ✅ Knowledge base collection: `bestbox_knowledge`
- ✅ Domain filtering: erp, crm, it_ops, oa, hudson

**RAG Pipeline Flow:**
1. Embed query → dense vector (BGE-M3)
2. Optional: Build sparse vector (BM25-like hashing)
3. Hybrid search in Qdrant (dense + sparse vectors)
4. Rerank top 20 results → select top K
5. Format with source citations

**Current Usage:**
- Domain agents (ERP, CRM, IT Ops, OA) have `search_knowledge_base` tool
- Used in LangGraph tool nodes via `ToolNode(UNIQUE_TOOLS)`
- No RAG access in workflow canvas or Pi Agent yet

## Design Section 1: RAG Node Types Architecture

### New Node Types for Canvas

**1. RAG Search Node (`rag_search`)**

**Purpose:** Execute RAG search and return results

**Configuration Panel:**
- **Query Source:**
  - Static text input (default)
  - From previous node output
  - From user input variable
- **Domain Filter:** Dropdown
  - All (default)
  - ERP
  - CRM
  - IT Ops
  - OA
  - Hudson
- **Top-K Results:** Slider (1-20, default 5)
- **Search Mode:** Radio buttons
  - Dense only (default)
  - Dense + Sparse hybrid
- **Hybrid Weights** (if hybrid mode):
  - Dense weight: Slider (0-1, default 0.7)
  - Sparse weight: Slider (0-1, default 0.3)

**Output:**
```json
{
  "results": [
    {"text": "...", "source": "...", "section": "...", "score": 0.95},
    ...
  ],
  "query": "original query",
  "domain": "erp"
}
```

**Icon:** 🔍 Search magnifying glass

---

**2. RAG Rerank Node (`rag_rerank`)**

**Purpose:** Rerank search results using reranker service

**Configuration Panel:**
- **Query Source:** (same as search node)
- **Results Source:**
  - From previous RAG Search node (default)
  - From state variable
- **Top-K After Reranking:** Slider (1-10, default 5)

**Input Requirements:**
- Query string
- Array of search results with `text` field

**Output:**
```json
{
  "reranked_results": [
    {"text": "...", "source": "...", "score": 0.98},
    ...
  ],
  "original_count": 20,
  "final_count": 5
}
```

**Icon:** ⬆️ Sorting arrows

---

**3. RAG Synthesize Node (`rag_synthesize`)**

**Purpose:** Synthesize answer from RAG results using LLM

**Configuration Panel:**
- **Query Source:** (same as search node)
- **Results Source:** From previous RAG node
- **Synthesis Prompt Template:** Text area
  - Default: "Based on the following sources, provide a comprehensive answer to: {query}\n\nSources:\n{sources}\n\nAnswer:"
  - Variables: `{query}`, `{sources}`, `{domain}`
- **Include Citations:** Checkbox (default: true)
- **Max Output Length:** Slider (100-2000 tokens, default 500)

**Output:**
```json
{
  "synthesized_answer": "Based on the knowledge base...",
  "sources_used": ["source1.md", "source2.md"],
  "query": "original query"
}
```

**Icon:** ✨ Sparkle/synthesis

---

**4. RAG Multi-Domain Node (`rag_multi_domain`)**

**Purpose:** Search multiple domains in parallel and combine results

**Configuration Panel:**
- **Query Source:** (same as search node)
- **Domains to Search:** Checkboxes
  - ☑ ERP
  - ☑ CRM
  - ☑ IT Ops
  - ☑ OA
  - ☐ Hudson
- **Results per Domain:** Slider (1-10, default 3)
- **Merge Strategy:** Radio buttons
  - Interleave by score (default)
  - Group by domain
  - Best overall scores

**Output:**
```json
{
  "combined_results": [
    {"text": "...", "source": "...", "domain": "erp", "score": 0.95},
    {"text": "...", "source": "...", "domain": "crm", "score": 0.93},
    ...
  ],
  "domains_searched": ["erp", "crm", "it_ops"],
  "total_results": 15
}
```

**Icon:** 🌐 Globe/network

### Node Connection Patterns

**Classic RAG Pipeline:**
```
Start → RAG Search → RAG Rerank → RAG Synthesize → End
```

**RAG + Code Generation:**
```
Start → RAG Multi-Domain → Pi Coding Agent → End
```

**Parallel Domain Search:**
```
Start → [RAG Search (ERP) || RAG Search (CRM) || RAG Search (IT)] → RAG Synthesize → End
```

## Design Section 2: Pi Agent RAG Integration

### Adding RAG Tool to Pi

**Current Pi Tools:**
- `read` - Read files
- `grep` - Search in files
- `find` - Find files by name
- `ls` - List directory contents

**New Tool:**
- `search_knowledge_base` - Search BestBox documentation and knowledge base

### Implementation Approach

**1. Tool Registration in Pi RPC Protocol:**

Pi Coding Agent runs in subprocess with RPC communication. Add RAG tool to the RPC command set:

```python
# In plugins_contrib/pi_coding_agent/__init__.py

def _handle_search_kb_command(params: dict) -> dict:
    """Handle search_knowledge_base RPC command"""
    from tools.rag_tools import search_knowledge_base

    query = params.get("query", "")
    domain = params.get("domain")
    top_k = params.get("top_k", 5)

    try:
        result = search_knowledge_base(query=query, domain=domain, top_k=top_k)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Register in RPC command handlers
RPC_COMMANDS = {
    "read": _handle_read,
    "grep": _handle_grep,
    "find": _handle_find,
    "ls": _handle_ls,
    "search_knowledge_base": _handle_search_kb_command,  # NEW
}
```

**2. Canvas Compiler Update:**

Modify `_generate_pi_coding_agent_node` in `agents/canvas_compiler.py`:

```python
def _generate_pi_coding_agent_node(node: NodeDef) -> str:
    data = node.data
    tools_list = data.get("tools", "read,grep,find,ls,search_knowledge_base")  # NEW DEFAULT
    # ... rest of generation
```

**3. Node Configuration UI:**

Add to Pi Agent node config panel:

**Available Tools** (checkboxes):
- ☑ read - Read files from workspace
- ☑ grep - Search file contents
- ☑ find - Find files by name pattern
- ☑ ls - List directory contents
- ☑ search_knowledge_base - Search BestBox knowledge base (NEW)

### Usage Example

**Workflow:** Start → Pi Coding Agent → End

**Pi Agent Configuration:**
- Message: "Implement the purchase order approval workflow according to our ERP procedures"
- Tools: All enabled (including search_knowledge_base)
- Workspace: /home/apexai/BestBox
- Allow writes: true

**Pi Execution Flow:**
1. Pi receives task: "Implement purchase order approval workflow"
2. Pi calls: `search_knowledge_base("purchase order approval process", domain="erp")`
3. RAG pipeline returns: ERP procedures documentation
4. Pi uses documentation to generate correct implementation
5. Pi writes code to workspace
6. Returns result

### Data Flow

```
Workflow Canvas
    ↓ (send message to Pi node)
Pi Subprocess (RPC)
    ↓ (calls search_knowledge_base via RPC)
Pi RPC Handler
    ↓ (imports and calls)
tools.rag_tools.search_knowledge_base()
    ↓ (executes pipeline)
Embeddings Service → Qdrant → Reranker
    ↓ (returns results)
Pi Subprocess
    ↓ (uses results in code generation)
Workflow Result
```

## Design Section 3: Data Flow & State Management

### Workflow State Extension

Extend `AgentState` to include RAG context:

```python
# In agents/state.py
from typing import TypedDict, List, Dict, Any
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: List[BaseMessage]
    current_agent: str
    tool_calls: int
    confidence: float
    plugin_context: Dict[str, Any]
    rag_context: Dict[str, Any]  # NEW: Store RAG results between nodes
```

### RAG Context Structure

```python
rag_context = {
    # From RAG Search node
    "last_search_results": [
        {
            "text": "Purchase orders require two-level approval...",
            "source": "erp_procedures.md",
            "section": "Purchase Orders",
            "score": 0.95,
            "domain": "erp"
        },
        ...
    ],
    "last_query": "purchase order approval process",
    "last_domain": "erp",
    "last_search_mode": "hybrid",

    # From RAG Rerank node
    "reranked_results": [...],
    "rerank_scores": [0.98, 0.95, 0.92, ...],

    # From RAG Synthesize node
    "synthesized_answer": "Based on the knowledge base, purchase orders require...",
    "synthesis_sources": ["erp_procedures.md", "approval_workflows.md"],

    # From RAG Multi-Domain node
    "multi_domain_results": {
        "erp": [...],
        "crm": [...],
        "it_ops": [...]
    }
}
```

### Node Data Passing Pattern

**State-based Approach (Recommended):**

Each RAG node reads from and writes to `state["rag_context"]`:

```python
def rag_search_node_{node_id}(state: AgentState) -> dict:
    """RAG Search node - stores results in state"""
    # Extract configuration
    query = node_config.get("query") or state["messages"][-1].content
    domain = node_config.get("domain")
    top_k = node_config.get("top_k", 5)

    # Execute search
    from tools.rag_tools import search_knowledge_base
    results = search_knowledge_base(query=query, domain=domain, top_k=top_k)

    # Parse results (formatted string → structured data)
    parsed_results = _parse_rag_output(results)

    # Update state
    return {
        "rag_context": {
            "last_search_results": parsed_results,
            "last_query": query,
            "last_domain": domain,
        }
    }
```

**Inter-node References:**

Downstream nodes read from `state["rag_context"]`:

```python
def rag_rerank_node_{node_id}(state: AgentState) -> dict:
    """RAG Rerank node - reads from and writes to state"""
    # Get results from previous search
    results = state["rag_context"]["last_search_results"]
    query = state["rag_context"]["last_query"]
    top_k = node_config.get("top_k", 5)

    # Rerank
    passages = [r["text"] for r in results]
    ranked_indices = _rerank_results(query, passages)
    reranked = [results[i] for i in ranked_indices[:top_k]]

    # Update state
    return {
        "rag_context": {
            **state["rag_context"],  # Preserve previous data
            "reranked_results": reranked,
            "rerank_scores": [results[i]["score"] for i in ranked_indices[:top_k]]
        }
    }
```

### Passing RAG Context to Pi Agent

Two approaches:

**1. Inject in Message (Recommended):**
```python
def pi_node_{node_id}(state: AgentState) -> dict:
    """Pi node with RAG context injection"""
    base_message = node_config.get("message", "")

    # Check if RAG context exists
    if state.get("rag_context", {}).get("last_search_results"):
        rag_results = state["rag_context"]["last_search_results"]
        context_text = "\n\n".join([
            f"[{r['source']}] {r['text']}"
            for r in rag_results[:3]  # Top 3 results
        ])
        message = f"{base_message}\n\nRelevant documentation:\n{context_text}"
    else:
        message = base_message

    # Execute Pi
    result = pi_coding_agent(message=message, ...)
    return {"messages": [...]}
```

**2. Pi Fetches On-Demand:**
Pi can call `search_knowledge_base` tool directly when it needs more context (already covered in Section 2).

## Design Section 4: Pre-built RAG Workflow Templates

### Template Storage

**Location:** `data/workflow_templates/rag/`

**Template Structure:**
```json
{
  "id": "template-doc-assistant",
  "name": "Documentation Assistant",
  "description": "Answer questions using knowledge base",
  "category": "rag",
  "tags": ["rag", "documentation", "qa"],
  "canvas": {
    "nodes": [...],
    "edges": [...]
  },
  "metadata": {
    "created_at": "2026-02-09",
    "version": "1.0.0"
  }
}
```

### Template 1: Documentation Assistant

**Use Case:** Answer user questions from knowledge base

**Flow:**
```
Start → RAG Search (all domains, top-K=10)
      → RAG Rerank (top-K=5)
      → RAG Synthesize
      → End
```

**Node Configurations:**

1. **Start Node:** Passes user question
2. **RAG Search:**
   - Query: From start node input
   - Domain: All
   - Top-K: 10
   - Mode: Dense + Sparse hybrid
3. **RAG Rerank:**
   - Results: From search node
   - Top-K: 5
4. **RAG Synthesize:**
   - Query: From start
   - Results: From rerank node
   - Prompt: "Based on these sources, provide a comprehensive answer. Include relevant citations."
   - Include citations: true
5. **End Node:** Returns synthesized answer

**Example Input:** "How do I approve a purchase order?"

**Example Output:**
```
Based on the knowledge base:

To approve a purchase order, follow these steps:
1. Navigate to ERP > Procurement > Pending POs
2. Select the purchase order to review
3. Verify budget availability in the summary panel
4. Click "Approve" button

[Source: erp_procedures.md, Purchase Orders]
[Source: approval_workflows.md, Two-Level Approval]

Retrieved 5 relevant passage(s).
```

---

### Template 2: Code + Context

**Use Case:** Generate code using documentation context

**Flow:**
```
Start → RAG Multi-Domain (ERP, CRM, IT)
      → Pi Coding Agent (with RAG results as context)
      → End
```

**Node Configurations:**

1. **Start Node:** Task description
2. **RAG Multi-Domain:**
   - Query: From start
   - Domains: ERP, CRM, IT Ops
   - Results per domain: 3
   - Merge: Best overall scores
3. **Pi Coding Agent:**
   - Message: "{start_message}\n\nRelevant documentation:\n{rag_results}"
   - Tools: read, grep, find, ls, search_knowledge_base
   - Workspace: /home/apexai/BestBox
   - Allow writes: true
4. **End Node:** Returns generated code

**Example Input:** "Implement purchase order approval workflow with two-level authorization"

**Example Flow:**
1. RAG searches ERP, CRM, IT domains for "purchase order approval"
2. Returns 9 relevant passages (3 per domain)
3. Pi Agent receives task + documentation context
4. Pi generates code following documented procedures
5. Returns implementation

---

### Template 3: Multi-Domain Aggregator

**Use Case:** Cross-functional queries requiring multiple domain knowledge

**Flow:**
```
Start → [RAG Search ERP || RAG Search CRM || RAG Search IT] (parallel)
      → RAG Synthesize (combines all domains)
      → End
```

**Node Configurations:**

1. **Start Node:** Cross-domain question
2. **RAG Search (ERP):**
   - Query: From start
   - Domain: ERP
   - Top-K: 5
3. **RAG Search (CRM):**
   - Query: From start
   - Domain: CRM
   - Top-K: 5
4. **RAG Search (IT):**
   - Query: From start
   - Domain: IT Ops
   - Top-K: 5
5. **RAG Synthesize:**
   - Query: From start
   - Results: Merged from all 3 search nodes
   - Prompt: "Compare and synthesize information from ERP, CRM, and IT domains. Highlight connections and dependencies."
6. **End Node:** Returns synthesized answer

**Example Input:** "How does customer data flow from CRM to ERP to IT systems?"

**Example Output:**
```
Based on knowledge from multiple domains:

Customer data flows through three main systems:

1. CRM (Source): Customer information is captured in Salesforce, including contact details, purchase history, and support tickets. [Source: crm_architecture.md]

2. ERP (Integration): CRM data syncs to ERP via nightly batch jobs, creating customer master records for invoicing and order processing. [Source: erp_integration_guide.md]

3. IT Systems (Distribution): IT provisions user accounts and access based on ERP customer records. SSO integration links all systems. [Source: it_user_management.md]

Key integration points:
- CRM → ERP: Customer sync API (runs 2 AM daily)
- ERP → IT: User provisioning webhook (real-time)
- Bi-directional: Support ticket linking between CRM and IT

Retrieved 15 relevant passages across 3 domains.
```

---

### Template 4: Iterative Research

**Use Case:** Deep research requiring multiple search refinements

**Flow:**
```
Start → RAG Search (broad)
      → Router (confidence check)
      → [Low confidence: RAG Search (refined) → Router]
      → [High confidence: RAG Synthesize]
      → End
```

**Node Configurations:**

1. **Start Node:** Research question
2. **RAG Search (Initial):**
   - Query: From start
   - Domain: All
   - Top-K: 10
   - Mode: Hybrid
3. **Router (Confidence Check):**
   - Condition: Check average result score
   - Threshold: 0.75
   - Routes:
     - Score < 0.75 → Refine search
     - Score ≥ 0.75 → Proceed to synthesis
4. **RAG Search (Refined):**
   - Query: Extract key terms from initial results
   - Domain: Best domain from initial search
   - Top-K: 10
   - Mode: Dense only (more specific)
5. **Router (Second Check):**
   - Same logic, max 2 iterations
6. **RAG Synthesize:**
   - Combines results from all search iterations
7. **End Node:** Returns research summary

**Example Input:** "What are the security implications of integrating third-party payment processors?"

**Example Flow:**
1. Initial broad search returns mixed results (avg score: 0.68)
2. Router detects low confidence
3. Refined search focuses on "payment security" in IT domain
4. Second search returns better results (avg score: 0.82)
5. Proceeds to synthesis with combined results
6. Returns comprehensive security analysis

---

### Template Loading UI

**Admin Dashboard Integration:**

Add to `/admin/workflows`:
- New tab: **"Templates"** (alongside Dashboard, Designer)
- Gallery view with template cards
- Each card shows:
  - Template name
  - Description
  - Preview image (mini canvas thumbnail)
  - Tags (rag, documentation, code-gen, etc.)
  - "Use Template" button

**User Flow:**
1. User clicks "Templates" tab
2. Browses template gallery
3. Clicks "Use Template" on desired template
4. System creates new workflow from template
5. Redirects to designer with pre-configured nodes
6. User can customize and save

## Design Section 5: Implementation Details

### Database Schema Updates

**1. Add RAG Configuration to Workflows:**

```sql
-- Migration: 008_workflow_rag.sql
ALTER TABLE workflows
ADD COLUMN rag_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN rag_config JSONB DEFAULT '{}';

COMMENT ON COLUMN workflows.rag_enabled IS 'Whether workflow uses RAG nodes';
COMMENT ON COLUMN workflows.rag_config IS 'RAG-specific configuration (default domains, search params)';
```

**2. Track RAG Usage in Executions:**

```sql
ALTER TABLE workflow_executions
ADD COLUMN rag_queries JSONB DEFAULT '[]',
ADD COLUMN rag_results_count INTEGER DEFAULT 0,
ADD COLUMN rag_domains_used TEXT[] DEFAULT '{}';

COMMENT ON COLUMN workflow_executions.rag_queries IS 'Array of RAG search queries executed';
COMMENT ON COLUMN workflow_executions.rag_results_count IS 'Total RAG results retrieved';
COMMENT ON COLUMN workflow_executions.rag_domains_used IS 'Array of domains searched';

-- Index for RAG analytics
CREATE INDEX idx_workflow_executions_rag_domains ON workflow_executions USING GIN (rag_domains_used);
```

**Example rag_queries JSON:**
```json
[
  {
    "query": "purchase order approval",
    "domain": "erp",
    "top_k": 5,
    "mode": "hybrid",
    "results_count": 5,
    "avg_score": 0.87,
    "timestamp": "2026-02-09T14:30:00Z"
  }
]
```

### Canvas Compiler Changes

**Add RAG Node Generators:**

```python
# In agents/canvas_compiler.py

def _generate_rag_search_node(node: NodeDef) -> str:
    """Generate RAG Search node code"""
    sid = _sanitize_id(node.id)
    data = node.data
    domain = data.get("domain", None)
    top_k = data.get("top_k", 5)
    mode = data.get("mode", "hybrid")

    return textwrap.dedent(f"""\
        def rag_search_node_{sid}(state: AgentState) -> dict:
            \\\"\\\"\\\"RAG Search node - execute knowledge base search.\\\"\\\"\\\"
            from tools.rag_tools import search_knowledge_base

            # Extract query from config or last message
            query = {repr(data.get("query"))} or state["messages"][-1].content
            domain = {repr(domain)}
            top_k = {top_k}

            # Execute search
            results_text = search_knowledge_base(query=query, domain=domain, top_k=top_k)

            # Parse formatted results back to structured data
            # (Implementation detail: extract passages, sources, scores)
            parsed_results = _parse_rag_results(results_text)

            # Store in RAG context
            rag_context = state.get("rag_context", {{}})
            rag_context.update({{
                "last_search_results": parsed_results,
                "last_query": query,
                "last_domain": domain,
            }})

            from langchain_core.messages import AIMessage
            return {{
                "rag_context": rag_context,
                "messages": state["messages"] + [AIMessage(content=f"Found {{len(parsed_results)}} results for: {{query}}")]
            }}
    """)

def _generate_rag_rerank_node(node: NodeDef) -> str:
    """Generate RAG Rerank node code"""
    sid = _sanitize_id(node.id)
    top_k = node.data.get("top_k", 5)

    return textwrap.dedent(f"""\
        def rag_rerank_node_{sid}(state: AgentState) -> dict:
            \\\"\\\"\\\"RAG Rerank node - rerank search results.\\\"\\\"\\\"
            from tools.rag_tools import _rerank_results

            # Get results from state
            rag_context = state.get("rag_context", {{}})
            results = rag_context.get("last_search_results", [])
            query = rag_context.get("last_query", "")

            if not results:
                return {{"rag_context": rag_context}}

            # Rerank
            passages = [r.get("text", "") for r in results]
            ranked_indices = _rerank_results(query, passages)

            if ranked_indices:
                reranked = [results[i] for i in ranked_indices[:{top_k}]]
            else:
                reranked = results[:{top_k}]

            # Update context
            rag_context["reranked_results"] = reranked

            from langchain_core.messages import AIMessage
            return {{
                "rag_context": rag_context,
                "messages": state["messages"] + [AIMessage(content=f"Reranked to top {{len(reranked)}} results")]
            }}
    """)

def _generate_rag_synthesize_node(node: NodeDef) -> str:
    """Generate RAG Synthesize node code"""
    sid = _sanitize_id(node.id)
    prompt_template = node.data.get("prompt_template", "Based on these sources, answer: {query}")

    return textwrap.dedent(f"""\
        def rag_synthesize_node_{sid}(state: AgentState) -> dict:
            \\\"\\\"\\\"RAG Synthesize node - generate answer from results.\\\"\\\"\\\"
            from agents.graph import llm  # Use same LLM as agents

            # Get results and query from state
            rag_context = state.get("rag_context", {{}})
            results = rag_context.get("reranked_results") or rag_context.get("last_search_results", [])
            query = rag_context.get("last_query", "")

            if not results:
                answer = "No results available to synthesize."
            else:
                # Build sources text
                sources_text = "\\n\\n".join([
                    f"[{{r.get('source', 'unknown')}}] {{r.get('text', '')}}"
                    for r in results
                ])

                # Generate synthesis prompt
                prompt = {repr(prompt_template)}.format(
                    query=query,
                    sources=sources_text
                )

                # Call LLM
                response = llm.invoke(prompt)
                answer = response.content

            # Update context
            rag_context["synthesized_answer"] = answer
            rag_context["sources_used"] = [r.get("source") for r in results]

            from langchain_core.messages import AIMessage
            return {{
                "rag_context": rag_context,
                "messages": state["messages"] + [AIMessage(content=answer)]
            }}
    """)

def _generate_rag_multi_domain_node(node: NodeDef) -> str:
    """Generate RAG Multi-Domain node code"""
    sid = _sanitize_id(node.id)
    domains = node.data.get("domains", ["erp", "crm", "it_ops"])
    results_per_domain = node.data.get("results_per_domain", 3)

    return textwrap.dedent(f"""\
        def rag_multi_domain_node_{sid}(state: AgentState) -> dict:
            \\\"\\\"\\\"RAG Multi-Domain node - search multiple domains.\\\"\\\"\\\"
            from tools.rag_tools import search_knowledge_base

            query = state["messages"][-1].content
            domains = {repr(domains)}
            results_per_domain = {results_per_domain}

            # Search each domain
            combined_results = []
            for domain in domains:
                results_text = search_knowledge_base(
                    query=query,
                    domain=domain,
                    top_k=results_per_domain
                )
                parsed = _parse_rag_results(results_text)
                # Add domain tag
                for r in parsed:
                    r["domain"] = domain
                combined_results.extend(parsed)

            # Sort by score
            combined_results.sort(key=lambda x: x.get("score", 0), reverse=True)

            # Update context
            rag_context = state.get("rag_context", {{}})
            rag_context.update({{
                "last_search_results": combined_results,
                "last_query": query,
                "domains_searched": domains,
            }})

            from langchain_core.messages import AIMessage
            return {{
                "rag_context": rag_context,
                "messages": state["messages"] + [AIMessage(content=f"Found {{len(combined_results)}} results across {{len(domains)}} domains")]
            }}
    """)

# Add to NODE_GENERATORS dict
_NODE_GENERATORS = {
    # Existing nodes...
    "rag_search": _generate_rag_search_node,
    "rag_rerank": _generate_rag_rerank_node,
    "rag_synthesize": _generate_rag_synthesize_node,
    "rag_multi_domain": _generate_rag_multi_domain_node,
}
```

### Frontend Components

**1. Node Palette Update:**

```tsx
// In components/workflow/NodePalette.tsx

const nodeTypes = [
  // Existing categories...
  {
    category: "RAG",
    nodes: [
      { type: "rag_search", label: "RAG Search", icon: "🔍" },
      { type: "rag_rerank", label: "RAG Rerank", icon: "⬆️" },
      { type: "rag_synthesize", label: "RAG Synthesize", icon: "✨" },
      { type: "rag_multi_domain", label: "Multi-Domain Search", icon: "🌐" },
    ]
  }
];
```

**2. Node Config Panel:**

```tsx
// In components/workflow/NodeConfigPanel.tsx

// RAG Search Node Config
function RagSearchConfig({ node, onChange }) {
  return (
    <div className="space-y-4">
      <label>Query Source</label>
      <input type="text" value={node.data.query} onChange={...} />

      <label>Domain Filter</label>
      <select value={node.data.domain} onChange={...}>
        <option value="">All</option>
        <option value="erp">ERP</option>
        <option value="crm">CRM</option>
        <option value="it_ops">IT Ops</option>
        <option value="oa">Office Automation</option>
        <option value="hudson">Hudson</option>
      </select>

      <label>Top-K Results: {node.data.top_k}</label>
      <input type="range" min="1" max="20" value={node.data.top_k} onChange={...} />

      <label>Search Mode</label>
      <div>
        <input type="radio" value="dense" checked={node.data.mode === "dense"} onChange={...} />
        <label>Dense Only</label>
      </div>
      <div>
        <input type="radio" value="hybrid" checked={node.data.mode === "hybrid"} onChange={...} />
        <label>Dense + Sparse Hybrid</label>
      </div>

      {node.data.mode === "hybrid" && (
        <div>
          <label>Dense Weight: {node.data.dense_weight}</label>
          <input type="range" min="0" max="1" step="0.1" value={node.data.dense_weight} onChange={...} />

          <label>Sparse Weight: {node.data.sparse_weight}</label>
          <input type="range" min="0" max="1" step="0.1" value={node.data.sparse_weight} onChange={...} />
        </div>
      )}
    </div>
  );
}

// Similar for other RAG node types...
```

**3. Template Gallery:**

```tsx
// New file: app/[locale]/admin/workflows/templates/page.tsx

export default function TemplatesPage() {
  const templates = useTemplates(); // Fetch from API

  return (
    <div className="p-8">
      <h1>Workflow Templates</h1>

      <div className="grid grid-cols-3 gap-6 mt-6">
        {templates.map(template => (
          <TemplateCard
            key={template.id}
            template={template}
            onUse={() => createFromTemplate(template.id)}
          />
        ))}
      </div>
    </div>
  );
}

function TemplateCard({ template, onUse }) {
  return (
    <div className="border rounded-lg p-4">
      <h3>{template.name}</h3>
      <p className="text-sm text-gray-600">{template.description}</p>

      {/* Mini canvas preview */}
      <div className="bg-gray-100 h-32 rounded mt-3">
        <MiniCanvasPreview nodes={template.canvas.nodes} />
      </div>

      <div className="mt-3 flex gap-2">
        {template.tags.map(tag => (
          <span key={tag} className="px-2 py-1 bg-blue-100 text-xs rounded">
            {tag}
          </span>
        ))}
      </div>

      <button
        onClick={onUse}
        className="mt-4 w-full px-4 py-2 bg-blue-600 text-white rounded"
      >
        Use Template
      </button>
    </div>
  );
}
```

### API Endpoints

**1. Template Management:**

```python
# In services/workflow_endpoints.py

@router.get("/templates")
async def list_templates():
    """List available workflow templates"""
    template_dir = Path("data/workflow_templates/rag")
    templates = []

    for template_file in template_dir.glob("*.json"):
        with open(template_file) as f:
            template = json.load(f)
            templates.append(template)

    return {"templates": templates}

@router.post("/workflows/from-template/{template_id}")
async def create_from_template(template_id: str, name: str = None):
    """Create new workflow from template"""
    # Load template
    template_path = Path(f"data/workflow_templates/rag/{template_id}.json")
    with open(template_path) as f:
        template = json.load(f)

    # Create new workflow
    workflow_name = name or f"{template['name']} (Copy)"
    workflow_data = {
        "name": workflow_name,
        "canvas_json": template["canvas"],
        "rag_enabled": True,
        "created_by": "admin",  # From JWT
    }

    # Save to database
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            "INSERT INTO workflows (name, canvas_json, rag_enabled, created_by) "
            "VALUES ($1, $2, $3, $4) RETURNING *",
            workflow_data["name"],
            json.dumps(workflow_data["canvas_json"]),
            workflow_data["rag_enabled"],
            workflow_data["created_by"]
        )

    return _row_to_dict(row)
```

**2. RAG Metrics:**

```python
@router.get("/workflows/{workflow_id}/rag-metrics")
async def get_rag_metrics(workflow_id: str):
    """Get RAG usage metrics for a workflow"""
    async with get_db_connection() as conn:
        # Aggregate RAG usage
        metrics = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_executions,
                SUM(rag_results_count) as total_results,
                AVG(rag_results_count) as avg_results_per_execution,
                jsonb_agg(DISTINCT domain) as domains_used
            FROM workflow_executions,
                 jsonb_array_elements_text(rag_domains_used) as domain
            WHERE workflow_id = $1
        """, workflow_id)

        # Get query frequency
        query_stats = await conn.fetch("""
            SELECT
                query->>'query' as query_text,
                COUNT(*) as frequency
            FROM workflow_executions,
                 jsonb_array_elements(rag_queries) as query
            WHERE workflow_id = $1
            GROUP BY query->>'query'
            ORDER BY frequency DESC
            LIMIT 10
        """, workflow_id)

    return {
        "total_executions": metrics["total_executions"],
        "total_results": metrics["total_results"],
        "avg_results_per_execution": float(metrics["avg_results_per_execution"] or 0),
        "domains_used": metrics["domains_used"],
        "top_queries": [{"query": q["query_text"], "frequency": q["frequency"]} for q in query_stats]
    }
```

### Services Required

All existing services - no new infrastructure needed:

- ✅ **Embeddings service** (localhost:8004) - Already running BGE-M3
- ✅ **Reranker service** (localhost:8004) - Already running BGE-reranker-v2-m3
- ✅ **Qdrant vector DB** (localhost:6333) - Already running with bestbox_knowledge collection
- ✅ **Agent API** (localhost:8000) - Will be extended with new endpoints
- ✅ **PostgreSQL** - Will add new columns to existing tables

### Error Handling

**1. RAG Service Unavailable:**
```python
def rag_search_node_{id}(state: AgentState) -> dict:
    try:
        results = search_knowledge_base(...)
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        from langchain_core.messages import AIMessage
        return {
            "messages": state["messages"] + [AIMessage(content=f"⚠️ RAG search unavailable: {str(e)}")],
            "rag_context": {"error": str(e)}
        }
```

**2. Empty Search Results:**
- Node continues with empty results array
- Downstream nodes check for empty results
- Workflow completes but with "No results found" message

**3. Pi Agent RAG Tool Failure:**
```python
def _handle_search_kb_command(params: dict) -> dict:
    try:
        result = search_knowledge_base(...)
        return {"success": True, "result": result}
    except Exception as e:
        return {
            "success": False,
            "error": f"Knowledge base search failed: {str(e)}"
        }
```

Pi receives error message and can:
- Retry with different query
- Proceed without RAG context
- Report failure to user

### Testing Strategy

**1. Unit Tests:**
```python
# tests/test_rag_nodes.py

def test_rag_search_node_generation():
    """Test RAG search node code generation"""
    node = NodeDef(
        id="search-1",
        type="rag_search",
        data={"domain": "erp", "top_k": 5}
    )
    code = _generate_rag_search_node(node)
    assert "def rag_search_node_search_1" in code
    assert "domain = 'erp'" in code

def test_rag_context_state_updates():
    """Test RAG context state management"""
    state = AgentState(
        messages=[],
        rag_context={}
    )
    # Simulate search node
    state["rag_context"]["last_search_results"] = [{"text": "..."}]
    # Simulate rerank node
    assert "last_search_results" in state["rag_context"]
```

**2. Integration Tests:**
```python
# tests/test_rag_workflow_integration.py

async def test_full_rag_pipeline_workflow():
    """Test complete RAG workflow execution"""
    workflow = create_workflow({
        "nodes": [
            {"type": "start"},
            {"type": "rag_search", "data": {"domain": "erp", "top_k": 5}},
            {"type": "rag_rerank", "data": {"top_k": 3}},
            {"type": "rag_synthesize"},
            {"type": "end"}
        ]
    })

    result = await execute_workflow(
        workflow_id=workflow.id,
        message="How do I approve a purchase order?"
    )

    assert "synthesized_answer" in result["rag_context"]
    assert len(result["messages"]) > 0

async def test_pi_agent_with_rag_tool():
    """Test Pi Agent calling search_knowledge_base"""
    workflow = create_workflow({
        "nodes": [
            {"type": "start"},
            {"type": "pi_coding_agent", "data": {
                "message": "Implement PO approval using our procedures",
                "tools": "read,grep,find,ls,search_knowledge_base"
            }},
            {"type": "end"}
        ]
    })

    result = await execute_workflow(workflow_id=workflow.id)

    # Pi should have called RAG tool
    assert result["rag_context"]["rag_queries"]
    assert "purchase order" in result["rag_context"]["rag_queries"][0]["query"]
```

**3. Template Tests:**
```python
def test_load_all_templates():
    """Test all templates load without errors"""
    templates = load_templates()
    assert len(templates) >= 4  # 4 pre-built templates

    for template in templates:
        assert "name" in template
        assert "canvas" in template
        validate_canvas(template["canvas"])
```

### Metrics to Track

**Dashboard Metrics:**
- Total RAG queries executed across all workflows
- Most queried domains (ERP, CRM, IT, etc.)
- Average results per query
- RAG query success rate
- Top 10 most frequent queries

**Per-Workflow Metrics:**
- RAG queries per execution
- Domains used
- Average result count
- Query patterns over time

**Template Usage:**
- Most popular templates
- Template success rates
- Customization frequency

## Implementation Order

**Phase 1: Backend Foundation (Days 1-2)**
1. Database migration: Add RAG columns to workflows and workflow_executions
2. Extend `AgentState` with `rag_context` field
3. Create RAG node generators in canvas_compiler.py
4. Add Pi Agent RAG tool handler

**Phase 2: RAG Nodes (Days 3-4)**
1. Implement RAG Search node
2. Implement RAG Rerank node
3. Implement RAG Synthesize node
4. Implement RAG Multi-Domain node
5. Test node generation and compilation

**Phase 3: Frontend Integration (Days 5-6)**
1. Add RAG nodes to palette
2. Create RAG node config panels
3. Add Pi Agent tool checkboxes
4. Test canvas with RAG nodes

**Phase 4: Templates (Days 7-8)**
1. Create template JSON files (4 templates)
2. Build template gallery page
3. Implement template loading API
4. Test workflow creation from templates

**Phase 5: Testing & Polish (Days 9-10)**
1. Integration testing: Full RAG workflows
2. Test Pi Agent with RAG tool
3. Test all 4 templates
4. Add metrics tracking
5. Documentation and examples

## Success Criteria

✅ **RAG Nodes Functional:**
- All 4 RAG node types work in canvas
- Nodes can be connected in pipelines
- Configuration panels work correctly

✅ **Pi Agent Integration:**
- Pi can call search_knowledge_base tool
- Tool returns formatted results
- Pi can use RAG context in code generation

✅ **Templates Working:**
- All 4 templates load correctly
- Templates can be instantiated and customized
- Templates execute successfully

✅ **State Management:**
- RAG context persists between nodes
- Results passed correctly in workflows
- Execution history tracked in database

✅ **Error Handling:**
- Graceful failures when services unavailable
- Clear error messages to users
- Workflows continue despite RAG failures

## Future Enhancements (Out of Scope)

- **Streaming RAG results** - Stream search results as they're found
- **Custom reranking models** - Allow users to choose reranker
- **RAG caching** - Cache frequent queries
- **Vector index management** - UI for managing Qdrant collections
- **RAG analytics dashboard** - Dedicated dashboard for RAG metrics
- **Multi-modal RAG** - Search images, diagrams in knowledge base
- **Agentic RAG** - Autonomous iterative refinement (ReAct-based)
- **RAG prompt templates** - Library of synthesis prompts
- **Domain-specific RAG** - Pre-configured nodes per domain
- **RAG validation** - Verify result quality automatically
