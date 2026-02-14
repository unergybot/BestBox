# BestBox: Enterprise Agentic Applications Demonstration Kit
## System Design & Implementation Plan

**Version:** 1.1  
**Date:** January 22, 2026  
**Status:** Draft for Review  
**ROCm Status:** ✅ Verified Operational (7.2.0)

---

## Document Index

- **System Design**: This document
- **[ROCm Deployment Guide](rocm_deployment_guide.md)**: Complete ROCm 7.2.0 installation and verification
- **[Review Checklist](review_checklist.md)**: Stakeholder review items

---

## Executive Summary

BestBox is an enterprise-grade agentic applications demonstration kit designed to showcase how AI agents can transform traditional ERP/CRM/OA workflows. Built on AMD Ryzen AI Max +395 hardware with 128GB RAM and 2TB NVMe, the system demonstrates production-ready agentic architecture patterns using LangGraph, CopilotKit, and locally-deployed LLMs with ROCm support.

**Hardware Status:** ROCm 7.2.0 successfully installed and verified on AMD Radeon 8060S (gfx1151) with 98GB GPU-accessible memory. See [ROCm Deployment Guide](rocm_deployment_guide.md) for complete installation documentation.

### Key Differentiators
- **100% Local Deployment**: All models and data stay on-premise
- **AMD ROCm Native**: Optimized for AMD GPUs without CUDA dependency
- **Enterprise-Grade**: SLA-compliant agent architecture with observability
- **Non-Technical User Focus**: Natural language interface with mobile support

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  CopilotKit Chat UI (Web + Mobile)                               │   │
│  │  - Voice input/output support                                    │   │
│  │  - Image/document upload                                          │   │
│  │  - Generative UI components                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AGENT ORCHESTRATION LAYER                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    LangGraph Runtime                              │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │   │
│  │  │ ERP Copilot  │ │ CRM Agent    │ │ IT Ops Agent │             │   │
│  │  │ Agent        │ │              │ │              │             │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘             │   │
│  │  ┌──────────────┐ ┌──────────────┐                               │   │
│  │  │ OA Workflow  │ │ Classifier/  │                               │   │
│  │  │ Agent        │ │ Router Agent │                               │   │
│  │  └──────────────┘ └──────────────┘                               │   │
│  │                                                                    │   │
│  │  - State Machine Semantics (FSM)                                  │   │
│  │  - Memory Management (Short-term + Long-term)                     │   │
│  │  - Human-in-the-Loop Checkpoints                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      TOOL GATEWAY / MCP LAYER                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Tool Registry & Schema Validation                               │   │
│  │  - RBAC & Authorization                                           │   │
│  │  - Rate Limiting & Circuit Breaker                                │   │
│  │  - Request/Response Logging                                       │   │
│  │  - OpenTelemetry Tracing                                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       AI INFERENCE LAYER                                │
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐     │
│  │  Reasoning LLM    │ │  Embedding Model  │ │  Reranker Model   │     │
│  │  (Qwen3-14B)      │ │  (BGE-M3)         │ │  (BGE-Reranker)   │     │
│  │  via vLLM/ROCm    │ │  via TEI/ROCm     │ │  via TEI/ROCm     │     │
│  └───────────────────┘ └───────────────────┘ └───────────────────┘     │
│  ┌───────────────────┐                                                  │
│  │  Prediction Models│                                                  │
│  │  (XGBoost/FastAPI)│                                                  │
│  └───────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE SERVICES LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │   │
│  │  │  ERPNext    │ │  Mock CRM   │ │  Knowledge  │               │   │
│  │  │  (Docker)   │ │  Service    │ │  Base (RAG) │               │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘               │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │   │
│  │  │  PostgreSQL │ │  Redis      │ │  Minio (S3) │               │   │
│  │  │  Database   │ │  Cache      │ │  Storage    │               │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles Alignment

| Principle | Implementation |
|-----------|----------------|
| **Non-technical user focus** | CopilotKit chat UI with voice, natural language only |
| **Hide complexity** | Single conversational interface, auto-routing to specialized agents |
| **Enterprise reliability** | SLA contracts, timeouts, fallbacks, circuit breakers |
| **Agent reasoning** | LangGraph FSM with ReAct/Plan-Execute patterns |

---

## 2. Component Deep Dive

### 2.1 Model Stack (ROCm-Native)

#### 2.1.1 Reasoning Model

| Property | Specification |
|----------|---------------|
| **Model** | Qwen3-14B-Instruct (or 7B for faster responses) |
| **Backend** | vLLM with ROCm support |
| **Serving** | OpenAI-compatible API (localhost:8000) |
| **Quantization** | AWQ or GPTQ for 128GB RAM constraint |
| **Context Window** | 32K tokens |
| **Constraints** | MAX_TOKENS=2048, TIMEOUT=30s |

**Why Qwen3?**
- Strong instruction following
- Excellent tool calling capabilities
- Good multilingual support (Chinese enterprise scenarios)
- Actively maintained with ROCm compatibility

#### 2.1.2 Embedding Model

| Property | Specification |
|----------|---------------|
| **Model** | BAAI/bge-m3 or Qwen3-Embedding-0.6B |
| **Backend** | Huggingface Text Embeddings Inference (TEI) |
| **Serving** | localhost:8080/embed |
| **Dimensions** | 1024 (bge-m3) |
| **Features** | Multi-lingual, dense+sparse embeddings |

**TEI Docker Command (ROCm):**
```bash
docker run --device=/dev/kfd --device=/dev/dri \
  -p 8080:80 -v $PWD/models:/data \
  ghcr.io/huggingface/text-embeddings-inference:rocm \
  --model-id BAAI/bge-m3
```

#### 2.1.3 Reranker Model

| Property | Specification |
|----------|---------------|
| **Model** | BAAI/bge-reranker-large |
| **Backend** | TEI (same container, different endpoint) |
| **Serving** | localhost:8081/rerank |
| **Use Case** | Improve RAG retrieval precision |

#### 2.1.4 Prediction Models

| Use Case | Model | Serving |
|----------|-------|---------|
| Lead Scoring | XGBoost | FastAPI |
| Churn Prediction | LightGBM | FastAPI |
| Fault Diagnosis | PyTorch MLP | FastAPI |

### 2.2 Agent Framework (LangGraph)

#### 2.2.1 Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Router Agent                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Intent Classification → Domain Detection       │   │
│  │  "What's our Q4 procurement spend?" → ERP       │   │
│  │  "Which leads should I focus on?" → CRM        │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬────────────────┐
         ▼               ▼               ▼                ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ ERP Agent   │ │ CRM Agent   │ │ IT Ops Agent│ │ OA Agent    │
│             │ │             │ │             │ │             │
│ Tools:      │ │ Tools:      │ │ Tools:      │ │ Tools:      │
│ -query_po   │ │ -get_leads  │ │ -query_logs │ │ -gen_doc    │
│ -get_inv    │ │ -predict_   │ │ -get_alerts │ │ -draft_email│
│ -fin_report │ │  churn      │ │ -diag_fault │ │ -schedule   │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

#### 2.2.2 Agent State Machine (FSM Pattern)

```python
# Recommended LangGraph state definition
from langgraph.graph import StateGraph, MessagesState, START, END
from typing import TypedDict, Literal

class AgentState(TypedDict):
    messages: list          # Conversation history
    current_agent: str      # Active sub-agent
    tool_calls: int         # Counter for SLA
    confidence: float       # For fallback decisions
    context: dict           # Retrieved context (RAG)
    plan: list              # Plan-Execute pattern
    step: int               # Current plan step

# State machine transitions
graph = StateGraph(AgentState)
graph.add_node("intent_classifier", classify_intent)
graph.add_node("erp_agent", erp_agent_node)
graph.add_node("crm_agent", crm_agent_node)
graph.add_node("validator", validate_response)
graph.add_node("fallback", handle_fallback)

# Conditional routing
graph.add_conditional_edges(
    "intent_classifier",
    route_to_agent,
    {
        "erp": "erp_agent",
        "crm": "crm_agent",
        "unknown": "fallback"
    }
)
```

#### 2.2.3 SLA Configuration

```python
# Agent constraints for enterprise SLA
AGENT_SLA = {
    "max_tool_calls": 5,
    "max_reasoning_tokens": 2048,
    "timeout_seconds": 30,
    "confidence_threshold": 0.7,
    "fallback_behavior": "ask_clarification",
    
    # Response tiers
    "tier_0_cache_ttl": 300,     # 5 min cache for FAQ
    "tier_1_timeout": 5,         # Single tool call
    "tier_2_timeout": 15,        # Multi-step agent
    "tier_3_async": True         # Background workflow
}
```

### 2.3 Tool Design (MCP-Compatible)

#### 2.3.1 Tool Schema Best Practices

**❌ Bad Tool Design:**
```python
@tool
def query_database(query: str) -> str:
    """Execute arbitrary query"""  # Dangerous!
```

**✅ Good Tool Design:**
```python
@tool
def get_purchase_orders(
    vendor_id: str,
    start_date: date,
    end_date: date,
    status: Literal["pending", "approved", "completed"],
    limit: int = 100
) -> list[PurchaseOrder]:
    """
    Retrieve purchase orders from ERP with filters.
    
    Args:
        vendor_id: Vendor identifier (e.g., "VND-001")
        start_date: Start of date range
        end_date: End of date range  
        status: Order status filter
        limit: Maximum records to return
        
    Returns:
        List of PurchaseOrder objects with id, amount, date, items
    """
```

#### 2.3.2 Tool Registry

| Domain | Tool Name | Description | SLA Tier |
|--------|-----------|-------------|----------|
| ERP | `get_purchase_orders` | Query PO with filters | Tier 1 |
| ERP | `get_inventory_levels` | Current stock by warehouse | Tier 1 |
| ERP | `get_financial_summary` | P&L, cash flow reports | Tier 2 |
| CRM | `get_leads` | Lead list with scoring | Tier 1 |
| CRM | `predict_churn` | ML churn prediction | Tier 2 |
| CRM | `get_customer_360` | Full customer view | Tier 2 |
| IT Ops | `query_system_logs` | Log search with filters | Tier 1 |
| IT Ops | `get_active_alerts` | Current alert list | Tier 1 |
| IT Ops | `diagnose_fault` | AI fault analysis | Tier 2 |
| OA | `generate_document` | Template-based doc gen | Tier 2 |
| OA | `draft_email` | AI email composition | Tier 2 |
| RAG | `search_knowledge_base` | Semantic search | Tier 1 |

### 2.4 Frontend (CopilotKit)

#### 2.4.1 Integration Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Next.js Application                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │  <CopilotKit>                                    │   │
│  │    <CopilotPopup>                               │   │
│  │      - Chat interface                            │   │
│  │      - Generative UI (charts, tables)           │   │
│  │      - Human-in-the-loop approvals              │   │
│  │    </CopilotPopup>                              │   │
│  │                                                  │   │
│  │    useCopilotAction() ← Frontend actions        │   │
│  │    useCopilotReadable() ← App state sharing     │   │
│  │  </CopilotKit>                                   │   │
│  └─────────────────────────────────────────────────┘   │
│                          │                              │
│                          ▼                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │  CopilotRuntime (Backend)                        │   │
│  │    - AG-UI Protocol → LangGraph                 │   │
│  │    - Streaming responses                         │   │
│  │    - State synchronization                       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

#### 2.4.2 Key Features to Implement

| Feature | CopilotKit Component | Description |
|---------|---------------------|-------------|
| Chat UI | `<CopilotPopup>` | Floating chat interface |
| Voice Input | `useCopilotVoice()` | Speech-to-text integration |
| Generative UI | `<CopilotTask>` | Render charts, tables dynamically |
| Approvals | Human-in-the-Loop | Agent pauses for user confirmation |
| Context | `useCopilotReadable()` | Share app state with agent |
| Actions | `useCopilotAction()` | Agent triggers frontend actions |

### 2.5 Enterprise Backend Services

#### 2.5.1 ERPNext Deployment

```yaml
# docker-compose.yml (ERPNext)
version: "3.8"
services:
  erpnext:
    image: frappe/erpnext:v15
    ports:
      - "8001:8000"
    environment:
      - SITE_NAME=bestbox.local
    volumes:
      - erpnext-sites:/home/frappe/frappe-bench/sites
    depends_on:
      - mariadb
      - redis
      
  mariadb:
    image: mariadb:10.6
    environment:
      - MYSQL_ROOT_PASSWORD=admin
    volumes:
      - mariadb-data:/var/lib/mysql

volumes:
  erpnext-sites:
  mariadb-data:
```

#### 2.5.2 Mock CRM Service

For rapid prototyping, use a FastAPI mock service with realistic data:

```python
# mock_crm/main.py
from fastapi import FastAPI
from pydantic import BaseModel
import random

app = FastAPI(title="Mock CRM API")

class Lead(BaseModel):
    id: str
    name: str
    company: str
    score: float  # 0-100
    last_activity: str
    churn_risk: float

@app.get("/leads")
async def get_leads(status: str = "active", limit: int = 100):
    """Get leads with optional filtering"""
    return generate_mock_leads(status, limit)

@app.post("/predict-churn")
async def predict_churn(customer_id: str):
    """ML churn prediction endpoint"""
    return {"customer_id": customer_id, "churn_probability": random.uniform(0, 1)}
```

### 2.6 Knowledge Base (RAG Pipeline)

#### 2.6.1 RAG Architecture

```
Documents → Chunking → Embeddings → Vector Store → Retrieval → Reranking → LLM
    │           │           │            │             │           │         │
    ▼           ▼           ▼            ▼             ▼           ▼         ▼
 PDF/Word   1024 tok     BGE-M3      Qdrant      Hybrid      BGE-Reranker  Qwen3
 Markdown   50% overlap  (TEI)       (local)     BM25+Dense
```

#### 2.6.2 Vector Store Selection

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Qdrant** | Rust-native, fast, filtering | Docker required | ✅ Primary |
| Milvus | Feature-rich, scalable | Heavy, complex | For scale |
| ChromaDB | Simple, Python-native | Less performant | Prototyping |
| pgvector | PostgreSQL integration | Query complexity | If using PG |

---

## 3. Demo Scenarios Design

### 3.1 Scenario 1: ERP Copilot - Procurement Analysis

**User Journey:**
```
User: "Why did Q4 procurement cost increase 30%?"

Agent Flow:
1. Router → ERP Agent
2. Plan: [get_po_summary, get_vendor_analysis, summarize]
3. Tool: get_purchase_orders(Q4, all_vendors)
4. Tool: get_vendor_price_trends(Q4)
5. Analyze: Identify vendor X raised prices 25%
6. Response: "Q4 procurement increased 30% primarily due to:
   • Vendor X raised prices 25% (affecting $500K spend)
   • Emergency orders +15% due to supply chain delays
   Recommendation: Renegotiate with Vendor X or evaluate alternatives."
```

**Required Tools:**
- `get_purchase_orders(period, vendor, category)`
- `get_vendor_price_trends(period)`
- `get_inventory_turnover()`
- `generate_procurement_report()`

### 3.2 Scenario 2: CRM Sales Assistant - Lead Scoring

**User Journey:**
```
User: "Which leads should I focus on this week?"

Agent Flow:
1. Router → CRM Agent
2. Plan: [get_leads, score_leads, prioritize]
3. Tool: get_leads(status="active")
4. Tool: predict_conversion(leads)
5. Rank by: conversion_probability * deal_size
6. Response: "Top 5 leads for this week:
   1. Acme Corp - 85% likely, $50K deal (proposal review stage)
   2. GlobalTech - 78% likely, $120K deal (demo scheduled)
   [Generative UI: Priority lead table with actions]"
```

### 3.3 Scenario 3: IT Ops Agent - Fault Diagnosis

**User Journey:**
```
User: "Compressor unit A keeps failing, why?"

Agent Flow:
1. Router → IT Ops Agent
2. Plan: [query_history, correlate_faults, diagnose]
3. Tool: query_maintenance_logs(unit="compressor_A", period="6M")
4. Tool: get_fault_codes(unit="compressor_A")
5. Analysis: Pattern detection on fault codes
6. Response: "Compressor A failure analysis:
   • 80% of failures correlate with fault code E15 (overheating)
   • Peak failures occur after >8hr continuous operation
   • Coolant level drops detected 48hrs before failures
   
   Recommendation: Implement 6hr operation cycles, 
   add coolant level monitoring alert."
```

### 3.4 Scenario 4: OA Workflow Agent - Document Generation

**User Journey:**
```
User: "Draft an approval email for the Q4 budget increase request"

Agent Flow:
1. Router → OA Agent
2. Plan: [get_context, apply_template, draft]
3. Tool: search_knowledge_base("budget approval email template")
4. Tool: get_budget_request_details(request_id="REQ-2025-042")
5. Generate: Apply company tone, formal structure
6. Human-in-the-Loop: Show draft for approval
7. Response: "Draft email ready for review:
   [Generative UI: Email preview with Edit/Send buttons]"
```

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 1.1 | Setup Ubuntu 24.04, ROCm drivers | Working AMD GPU stack |
| 1.2 | Deploy vLLM with Qwen3-14B | localhost:8000 API |
| 1.3 | Deploy TEI with BGE-M3 | localhost:8080 embedding API |
| 1.4 | Setup PostgreSQL, Redis, Qdrant | Docker compose infrastructure |
| 1.5 | Deploy ERPNext in Docker | Working ERP at localhost:8001 |

### Phase 2: Agent Core (Weeks 3-4)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 2.1 | Implement LangGraph state machine | Base agent framework |
| 2.2 | Build Router Agent | Intent classification working |
| 2.3 | Build ERP Agent with 5 tools | ERP queries functional |
| 2.4 | Build CRM Agent with 4 tools | Lead scoring working |
| 2.5 | Implement SLA constraints | Timeouts, limits enforced |

### Phase 3: RAG & Intelligence (Weeks 5-6)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 3.1 | Build document ingestion pipeline | PDF/Word → Qdrant |
| 3.2 | Implement hybrid retrieval | BM25 + dense search |
| 3.3 | Add reranker stage | Improved retrieval precision |
| 3.4 | Train/deploy prediction models | Churn, lead scoring |
| 3.5 | Build IT Ops fault diagnosis | Pattern detection |

### Phase 4: Frontend & UX (Weeks 7-8)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 4.1 | Setup Next.js + CopilotKit | Chat UI working |
| 4.2 | Implement AG-UI → LangGraph | Streaming responses |
| 4.3 | Build Generative UI components | Charts, tables, forms |
| 4.4 | Add voice input/output | Speech integration |
| 4.5 | Mobile responsiveness | Touch-friendly UI |

### Phase 5: Production Hardening (Weeks 9-10)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 5.1 | OpenTelemetry instrumentation | Full observability |
| 5.2 | RBAC implementation | Role-based tool access |
| 5.3 | Human-in-the-loop workflows | Approval checkpoints |
| 5.4 | Load testing & optimization | SLA compliance verified |
| 5.5 | Documentation & demo scripts | Ready for showcase |

---

## 5. Technical Specifications

### 5.1 Hardware Requirements

| Component | Specification | Purpose |
|-----------|---------------|---------|
| CPU | AMD Ryzen AI Max +395 | Host workloads, inference fallback |
| RAM | 128GB DDR5 | Model loading, in-memory processing |
| Storage | 2TB NVMe | Models (~30GB), databases, documents |
| GPU | Integrated RDNA 3.5 | LLM inference via ROCm |
| Network | 1Gbps+ | Low-latency API responses |

### 5.2 Software Stack

| Layer | Technology | Version |
|-------|------------|---------|
| OS | Ubuntu 24.04 LTS | Kernel 6.8+ |
| GPU Runtime | ROCm | 7.2.0 (production) |
| Container | Docker + Docker Compose | 24.x |
| Python | Python 3.12+ | With uv package manager |
| LLM Serving | vLLM | 0.6+ (ROCm fork) |
| Embeddings | Text Embeddings Inference | 1.8+ |
| Agent Framework | LangGraph | 0.2+ |
| Frontend Framework | CopilotKit | 1.50+ |
| Vector Store | Qdrant | 1.10+ |
| ERP | ERPNext | v15 |
| Database | PostgreSQL | 16 |
| Cache | Redis | 7.x |

### 5.3 API Endpoints (Internal)

| Service | Endpoint | Port | Purpose |
|---------|----------|------|---------|
| LLM | localhost:8000/v1/chat/completions | 8000 | Reasoning model |
| Embeddings | localhost:8080/embed | 8080 | Dense embeddings |
| Reranker | localhost:8081/rerank | 8081 | Reranking |
| ERPNext | localhost:8001 | 8001 | ERP data |
| Qdrant | localhost:6333 | 6333 | Vector search |
| Agent API | localhost:3001/api/agent | 3001 | LangGraph runtime |
| Frontend | localhost:3000 | 3000 | CopilotKit UI |

### 5.4 Streaming Response Configuration

The Agent API supports progressive SSE streaming for CopilotKit-compatible chat endpoints.

**Environment variables:**

```bash
STREAMING_CHUNK_SIZE=1
STREAMING_TIMEOUT_SECONDS=60
```

**Runtime flow:**

```
CopilotKit OpenAIAdapter
  → /v1/chat/completions or /v1/responses
  → responses_api_stream()
  → response.output_text.delta SSE events
  → token/chunk-by-chunk rendering in chat UI
```

**Observability:**
- Streaming request verification logs via `[STREAMING CHECK]`
- TTFT, duration, total chunks, token throughput via `[STREAMING METRICS]`
- Timeout and stream failures via `[STREAMING ERROR]`

**Monitoring commands:**

```bash
tail -f ~/BestBox/logs/agent_api.log | grep "STREAMING CHECK"
tail -f ~/BestBox/logs/agent_api.log | grep "STREAMING METRICS" -A 7
```

---

## 6. Risk Assessment & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| ROCm model compatibility issues | High | Medium | Pre-test all models, have CPU fallback |
| LLM hallucination on enterprise data | High | Medium | Tool-only execution, no direct DB access |
| Response latency > SLA | Medium | Low | Tiered response strategy, caching |
| Memory exhaustion (128GB) | High | Low | Quantized models, batch limits |
| ERPNext API complexity | Medium | Medium | Start with mock services |
| Voice recognition accuracy | Low | Medium | Text fallback always available |

---

## 7. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Response Latency (P95) | < 6 seconds | OpenTelemetry traces |
| Tool Call Accuracy | > 90% | Manual review of logs |
| User Task Completion | > 85% | Demo session tracking |
| System Availability | > 99% | Uptime monitoring |
| User Satisfaction | > 4.0/5.0 | Post-demo survey |

---

## 8. Open Questions for Review

1. **Model Selection**: Should we prioritize Qwen3-7B (faster) or 14B (smarter)?
2. **ERP Choice**: Stick with ERPNext or also support Odoo for comparison?
3. **Voice Provider**: Use browser Web Speech API or dedicated service?
4. **Multi-language**: Priority for Chinese language support in demos?
5. **Security Scope**: Full RBAC or simplified demo auth?

---

## 9. Next Steps

1. **Review this document** with stakeholders
2. **Validate hardware** ROCm compatibility
3. **Benchmark models** on target hardware
4. **Finalize demo scenarios** based on priority
5. **Begin Phase 1** infrastructure setup

---

## Appendix A: Project Structure

```
BestBox/
├── docker-compose.yml           # All services orchestration
├── .env                         # Environment variables
├── docs/
│   ├── product_desc.md          # Original product description
│   └── system_design.md         # This document
├── models/                      # Downloaded model weights
│   ├── qwen3-14b-instruct/
│   ├── bge-m3/
│   └── bge-reranker-large/
├── agents/                      # LangGraph agent code
│   ├── router.py
│   ├── erp_agent.py
│   ├── crm_agent.py
│   ├── it_ops_agent.py
│   └── oa_agent.py
├── tools/                       # Tool implementations
│   ├── erp_tools.py
│   ├── crm_tools.py
│   ├── rag_tools.py
│   └── prediction_tools.py
├── services/                    # Backend services
│   ├── mock_crm/
│   ├── prediction_api/
│   └── rag_pipeline/
├── frontend/                    # CopilotKit Next.js app
│   ├── app/
│   ├── components/
│   └── lib/
├── scripts/                     # Setup and utility scripts
│   ├── setup_rocm.sh
│   ├── download_models.sh
│   └── seed_demo_data.py
└── tests/                       # Test suite
    ├── test_agents.py
    └── test_tools.py
```

---

## Appendix B: Docker Compose Reference

```yaml
version: "3.8"

services:
  # LLM Inference (vLLM + ROCm)
  vllm:
    image: vllm/vllm-openai:latest-rocm
    devices:
      - /dev/kfd
      - /dev/dri
    ports:
      - "8000:8000"
    volumes:
      - ./models:/models
    command: --model /models/qwen3-14b-instruct --dtype float16

  # Embeddings (TEI + ROCm)
  tei-embed:
    image: ghcr.io/huggingface/text-embeddings-inference:rocm
    devices:
      - /dev/kfd
      - /dev/dri
    ports:
      - "8080:80"
    volumes:
      - ./models:/data
    command: --model-id /data/bge-m3

  # Reranker (TEI + ROCm)
  tei-rerank:
    image: ghcr.io/huggingface/text-embeddings-inference:rocm
    devices:
      - /dev/kfd
      - /dev/dri
    ports:
      - "8081:80"
    volumes:
      - ./models:/data
    command: --model-id /data/bge-reranker-large

  # Vector Store
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant-data:/qdrant/storage

  # Database
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: bestbox
      POSTGRES_DB: bestbox
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

  # Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # Agent API
  agent-api:
    build: ./agents
    ports:
      - "3001:3001"
    environment:
      - LLM_URL=http://vllm:8000
      - EMBED_URL=http://tei-embed:80
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - vllm
      - tei-embed
      - qdrant

  # Frontend
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_AGENT_URL=http://agent-api:3001
    depends_on:
      - agent-api

volumes:
  qdrant-data:
  postgres-data:
```

---

*Document prepared for technical review. Please provide feedback on architecture decisions, component selections, and implementation priorities.*
