# BestBox Observability & Admin Dashboard Design

**Version:** 1.0
**Date:** January 24, 2026
**Author:** BestBox Development Team
**Status:** Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Key Metrics & KPIs](#key-metrics--kpis)
4. [Implementation - Instrumentation Layer](#implementation---instrumentation-layer)
5. [Docker Compose Configuration](#docker-compose-configuration)
6. [Grafana Dashboard Configuration](#grafana-dashboard-configuration)
7. [Frontend Integration](#frontend-integration)
8. [Deployment & Operations](#deployment--operations)
9. [Continuous Improvement Process](#continuous-improvement-process)
10. [Appendix](#appendix)

---

## Executive Summary

### Purpose

This design document outlines a comprehensive observability and admin dashboard system for BestBox. The system enables administrators to:

- **Track user sessions and behavior** - Understand how users interact with agents
- **Monitor system performance** - Ensure SLA compliance (TTFT, throughput, error rates)
- **Audit all conversations** - Full logging for compliance and debugging
- **Continuously improve** - Data-driven optimization of agent quality and system performance

### Key Design Decisions

1. **OpenTelemetry-based architecture** - Industry-standard telemetry pipeline, future-proof
2. **Multi-store approach** - Prometheus for metrics, Jaeger for traces, PostgreSQL for audit logs
3. **Grafana as unified UI** - Single pane of glass for all observability data
4. **Minimal code changes** - Auto-instrumentation via OpenLLMetry library
5. **Production-ready from day 1** - SLA alerts, automated reports, incident playbooks

### Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Admin can view real-time system health | <5 sec to load dashboard | Grafana load time |
| Admin can track individual user sessions | 100% conversation coverage | PostgreSQL audit log completeness |
| Admin receives alerts for SLA violations | <2 min detection time | Prometheus alert firing time |
| System performance overhead | <5% latency increase | Before/after instrumentation comparison |

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   ADMIN DASHBOARD                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Grafana (Port 3001)                             │    │
│  │  - System Health Dashboard                        │    │
│  │  - User Analytics Dashboard                       │    │
│  │  - Agent Performance Dashboard                    │    │
│  │  - Conversation Audit Dashboard                   │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────────────────────────────────────┐
│              TELEMETRY COLLECTION LAYER                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ OpenTelemetry│  │  Prometheus  │  │    Jaeger    │  │
│  │  Collector   │  │  (Metrics)   │  │   (Traces)   │  │
│  │  (Port 4318) │  │ (Port 9090)  │  │ (Port 16686) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────────────────────────────────────┐
│           INSTRUMENTATION LAYER (NEW CODE)               │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Agent API (services/agent_api.py)               │    │
│  │  - OpenLLMetry auto-instrumentation              │    │
│  │  - Prometheus custom metrics                     │    │
│  │  - PostgreSQL session tracking                   │    │
│  │  - Conversation audit logging                    │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
                    (existing traffic)
                          │
┌─────────────────────────────────────────────────────────┐
│                   USER INTERFACE                         │
│  - Main Chat (localhost:3000)                            │
│  - Admin Panel (localhost:3000/admin)                    │
│  - Feedback buttons (thumbs up/down)                     │
└─────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Data Type |
|-----------|---------------|-----------|
| **OpenTelemetry Collector** | Central telemetry hub, routes traces to Jaeger and metrics to Prometheus | Traces, Metrics |
| **Jaeger** | Distributed tracing storage and UI, shows agent reasoning workflows | Traces |
| **Prometheus** | Time-series metrics storage, powers Grafana dashboards and alerts | Metrics |
| **Grafana** | Unified visualization layer, embeds in admin panel | Dashboards |
| **PostgreSQL** | Audit log storage, user session tracking, conversation history | Structured logs |
| **Agent API** | Instrumentation point, emits telemetry during agent execution | Source |

### Design Principles

1. **Separation of Concerns** - Observability stack runs independently, system degrades gracefully if telemetry fails
2. **Standards-Based** - OpenTelemetry ensures vendor portability (can switch Jaeger → Tempo, Prometheus → VictoriaMetrics)
3. **Auto-Instrumentation First** - Minimize manual instrumentation, leverage OpenLLMetry for LangGraph
4. **Privacy-Aware** - User messages logged only in PostgreSQL (admin-only access), not in Prometheus/Jaeger labels
5. **Performance-First** - Async logging, batched exports, <5% overhead target

---

## Key Metrics & KPIs

### Performance Metrics (SLA Tracking)

These metrics measure system responsiveness and ensure user experience quality:

| Metric | Definition | Target | Measurement Method |
|--------|-----------|--------|-------------------|
| **TTFT (Time to First Token)** | Time from user message to first LLM response character appearing | < 2.0s | Prometheus histogram: `agent_latency_seconds` P50/P95/P99 |
| **Token Generation Speed** | Tokens per second during streaming response | > 20 tok/s | Prometheus counter: `llm_tokens_total` / time |
| **End-to-End Latency** | Complete user query → final answer with all tool calls | Simple: < 10s<br>Complex: < 60s | Prometheus histogram: `agent_latency_seconds` by `agent_type` |
| **Embedding Latency** | Time to generate embeddings for RAG query | < 100ms | Manual instrumentation in embeddings service |
| **Agent Routing Time** | Time for router to classify intent and select agent | < 500ms | Jaeger span duration for router node |

**Why These Metrics Matter:**
- TTFT is user perception of responsiveness (most critical UX metric)
- Token speed affects conversation flow quality
- End-to-end latency measures total task completion time
- Embedding latency impacts RAG quality (slow = user frustration)
- Router latency should be negligible (CPU-bound classification)

### Accuracy & Quality Metrics

These metrics measure agent intelligence and correctness:

| Metric | Definition | Target | Measurement Method |
|--------|-----------|--------|-------------------|
| **Router Accuracy** | % of queries routed to correct agent (first try) | > 90% | Estimated: (1 - error_rate) × continued_engagement_rate |
| **Tool Selection Success** | % of tool calls that complete without exceptions | > 95% | Prometheus counter: `tool_executions_total{status="success"}` / total |
| **RAG Relevance Score** | Average reranker confidence score for retrieved documents | > 0.7 | Log reranker scores to PostgreSQL, query AVG |
| **User Satisfaction** | Thumbs up / (thumbs up + thumbs down) ratio | > 80% | Prometheus counter: `user_feedback_total` by `rating` |

**Why These Metrics Matter:**
- Router accuracy indicates if users get the right agent immediately
- Tool success rate shows reliability of integrations
- RAG relevance prevents hallucinations (high relevance = grounded answers)
- User satisfaction is the ultimate quality metric (direct feedback)

### Engagement Metrics

These metrics understand user behavior and guide product development:

| Metric | Definition | Insight | Storage |
|--------|-----------|---------|---------|
| **Session Length** | Number of messages per conversation | Task complexity indicator | PostgreSQL: `user_sessions.total_messages` |
| **Agent Usage Distribution** | % of requests handled by each agent | Which domains get most use | Prometheus: `agent_requests_total` by `agent_type` |
| **Peak Concurrency** | Maximum simultaneous active sessions | Capacity planning | Prometheus gauge: `active_sessions` |
| **Repeat User Rate** | % users who return for 2+ sessions | Product stickiness | PostgreSQL: count distinct users by session count |

### System Health Metrics

These metrics ensure infrastructure reliability:

| Metric | Definition | Alert Threshold | Impact |
|--------|-----------|----------------|--------|
| **LLM Server Uptime** | % time llama-server responds to health checks | < 99% uptime | System unusable |
| **Memory Utilization** | GPU VRAM + System RAM usage | > 90% for 10+ min | Performance degradation |
| **Qdrant Query Time** | Vector search latency (P95) | > 200ms | RAG becomes bottleneck |
| **Agent API Error Rate** | HTTP 5xx errors per minute | > 5/min | User-facing failures |

---

## Implementation - Instrumentation Layer

### Step 1: Install Dependencies

Add observability libraries to your Python environment:

```bash
# Activate BestBox environment
source ~/BestBox/activate.sh

# Install OpenTelemetry core
pip install opentelemetry-api \
            opentelemetry-sdk \
            opentelemetry-exporter-otlp-proto-grpc

# Install auto-instrumentation for LangChain/LangGraph
pip install openinference-instrumentation-langchain

# Install Prometheus client
pip install prometheus-client

# For async PostgreSQL (if not already installed)
pip install asyncpg
```

### Step 2: Auto-Instrument Agent API

Modify `services/agent_api.py` to enable OpenTelemetry tracing:

```python
# services/agent_api.py - ADD AT TOP (BEFORE OTHER IMPORTS)

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from openinference.instrumentation.langchain import LangChainInstrumentor

# Initialize OpenTelemetry
resource = Resource.create({
    "service.name": "bestbox-agent-api",
    "service.version": "1.0.0",
    "deployment.environment": "production"
})

tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

# Export traces to OpenTelemetry Collector
otlp_exporter = OTLPSpanExporter(
    endpoint="http://localhost:4317",  # OTel Collector gRPC endpoint
    insecure=True  # Use TLS in production
)

tracer_provider.add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)

# Auto-instrument LangGraph (ONE LINE!)
LangChainInstrumentor().instrument()

# Now import your existing FastAPI app and LangGraph code
from fastapi import FastAPI, HTTPException, Header
# ... rest of your imports
```

**What This Does:**
- Every agent invocation creates a trace "Span" automatically
- Every LLM call is logged with prompt/response (configurable)
- Every tool execution is captured with arguments and results
- Spans are linked into a "Trace" showing the entire reasoning flow
- All data exports to OpenTelemetry Collector → Jaeger for visualization

### Step 3: Add Prometheus Metrics

Create a new observability module:

```python
# services/observability.py - NEW FILE

"""
Prometheus metrics definitions for BestBox.
Import and use these counters/histograms in your agent code.
"""

from prometheus_client import Counter, Histogram, Gauge

# Agent request tracking
agent_requests = Counter(
    'agent_requests_total',
    'Total agent requests received',
    ['agent_type', 'user_id']
)

# Latency tracking (with SLA-aligned buckets)
agent_latency = Histogram(
    'agent_latency_seconds',
    'Agent response latency in seconds',
    ['agent_type'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]  # Aligned with SLA targets
)

# LLM token generation tracking
llm_tokens_generated = Counter(
    'llm_tokens_total',
    'Total tokens generated by LLM',
    ['model']
)

# Tool execution tracking
tool_execution_success = Counter(
    'tool_executions_total',
    'Tool execution results',
    ['tool_name', 'status']  # status: success | error
)

# User feedback tracking
user_satisfaction = Counter(
    'user_feedback_total',
    'User thumbs up/down feedback',
    ['rating']  # rating: positive | negative
)

# Active session tracking
active_sessions = Gauge(
    'active_sessions',
    'Currently active user sessions'
)

# RAG-specific metrics
rag_retrieval_latency = Histogram(
    'rag_retrieval_seconds',
    'Time to retrieve documents from Qdrant',
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0]
)

rag_relevance_score = Histogram(
    'rag_relevance_score',
    'Reranker confidence scores',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)
```

### Step 4: Instrument Agent Endpoint

Modify your chat endpoint to record metrics:

```python
# services/agent_api.py - MODIFY EXISTING /chat ENDPOINT

import time
from observability import (
    agent_requests,
    agent_latency,
    llm_tokens_generated,
    tool_execution_success,
    active_sessions
)
from opentelemetry import trace

@app.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: str = Header(default="anonymous")
):
    """
    Main chat endpoint with full observability instrumentation.
    """
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())

    # Get current trace context (for linking to Jaeger)
    current_span = trace.get_current_span()
    trace_id = format(current_span.get_span_context().trace_id, '032x')

    # Track request
    agent_requests.labels(
        agent_type=request.agent or "router",
        user_id=user_id
    ).inc()

    # Track active sessions
    active_sessions.inc()

    try:
        # Your existing agent logic
        result = await run_agent(
            message=request.message,
            session_id=session_id,
            user_id=user_id
        )

        # Calculate latency
        latency_seconds = time.time() - start_time
        latency_ms = int(latency_seconds * 1000)

        # Track latency metric
        agent_latency.labels(
            agent_type=result.get('agent_used', 'unknown')
        ).observe(latency_seconds)

        # Track tokens (if llama.cpp returns usage stats)
        if 'usage' in result:
            llm_tokens_generated.labels(
                model="qwen2.5-14b"
            ).inc(result['usage']['completion_tokens'])

        # Track tool executions
        for tool_call in result.get('tool_calls', []):
            status = "success" if tool_call.get('error') is None else "error"
            tool_execution_success.labels(
                tool_name=tool_call['name'],
                status=status
            ).inc()

        # Log conversation to PostgreSQL
        await log_conversation(
            session_id=session_id,
            user_id=user_id,
            user_message=request.message,
            agent_response=result['response'],
            agent_type=result.get('agent_used', 'unknown'),
            tool_calls=result.get('tool_calls', []),
            latency_ms=latency_ms,
            confidence=result.get('confidence', 0.0),
            trace_id=trace_id
        )

        return result

    except Exception as e:
        # Track error
        tool_execution_success.labels(
            tool_name="agent_execution",
            status="error"
        ).inc()

        # Log error to PostgreSQL
        await log_conversation(
            session_id=session_id,
            user_id=user_id,
            user_message=request.message,
            agent_response=f"ERROR: {str(e)}",
            agent_type="error",
            tool_calls=[],
            latency_ms=int((time.time() - start_time) * 1000),
            confidence=0.0,
            trace_id=trace_id
        )

        raise HTTPException(status_code=500, detail=str(e))

    finally:
        active_sessions.dec()
```

### Step 5: Add Metrics Endpoint

Expose Prometheus scrape endpoint:

```python
# services/agent_api.py - ADD NEW ENDPOINT

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Scraped by Prometheus every 15 seconds.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### Step 6: PostgreSQL Audit Log Schema

Create database migration for conversation logging:

```sql
-- migrations/003_observability_tables.sql - NEW FILE

-- User session tracking
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id UUID PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    last_active_at TIMESTAMP DEFAULT NOW(),
    total_messages INT DEFAULT 0,
    agents_used JSONB DEFAULT '{}',  -- {"erp": 5, "crm": 2}
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_started ON user_sessions(started_at DESC);

-- Conversation audit log
CREATE TABLE IF NOT EXISTS conversation_log (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES user_sessions(session_id),
    timestamp TIMESTAMP DEFAULT NOW(),
    user_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    tool_calls JSONB DEFAULT '[]',  -- [{"tool": "search_kb", "args": {...}, "result": {...}}]
    latency_ms INT NOT NULL,
    confidence FLOAT,
    user_feedback VARCHAR(20),  -- 'positive', 'negative', null
    trace_id VARCHAR(255)  -- Links to Jaeger trace for debugging
);

CREATE INDEX idx_conversations_session ON conversation_log(session_id);
CREATE INDEX idx_conversations_timestamp ON conversation_log(timestamp DESC);
CREATE INDEX idx_conversations_agent ON conversation_log(agent_type);
CREATE INDEX idx_conversations_feedback ON conversation_log(user_feedback) WHERE user_feedback IS NOT NULL;

-- Apply migration
-- Run: psql -U bestbox -d bestbox -f migrations/003_observability_tables.sql
```

### Step 7: Conversation Logging Function

Implement the database logging function:

```python
# services/agent_api.py - ADD DATABASE LOGGING FUNCTION

import asyncpg
import json

# Initialize connection pool at startup
db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        host='localhost',
        port=5432,
        user='bestbox',
        password='bestbox_secure_2026',  # Use environment variable in production
        database='bestbox',
        min_size=2,
        max_size=10
    )

@app.on_event("shutdown")
async def shutdown():
    await db_pool.close()

async def log_conversation(
    session_id: str,
    user_id: str,
    user_message: str,
    agent_response: str,
    agent_type: str,
    tool_calls: list,
    latency_ms: int,
    confidence: float,
    trace_id: str
):
    """
    Log conversation to PostgreSQL for audit trail.
    Runs asynchronously to not block API response.
    """
    async with db_pool.acquire() as conn:
        # Upsert session record
        await conn.execute("""
            INSERT INTO user_sessions (session_id, user_id, total_messages, last_active_at)
            VALUES ($1, $2, 1, NOW())
            ON CONFLICT (session_id) DO UPDATE
            SET total_messages = user_sessions.total_messages + 1,
                last_active_at = NOW(),
                agents_used = user_sessions.agents_used || jsonb_build_object($3,
                    COALESCE((user_sessions.agents_used->>$3)::int, 0) + 1
                )
        """, session_id, user_id, agent_type)

        # Insert conversation record
        await conn.execute("""
            INSERT INTO conversation_log (
                session_id, user_message, agent_response, agent_type,
                tool_calls, latency_ms, confidence, trace_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
            session_id,
            user_message,
            agent_response,
            agent_type,
            json.dumps(tool_calls),
            latency_ms,
            confidence,
            trace_id
        )
```

**Implementation Complete!** Your Agent API now emits:
- ✅ Distributed traces to Jaeger (via OpenTelemetry)
- ✅ Time-series metrics to Prometheus
- ✅ Audit logs to PostgreSQL

---

## Docker Compose Configuration

### Update docker-compose.yml

Add observability services to your existing stack:

```yaml
# docker-compose.yml - ADD THESE SERVICES

version: '3.8'

services:
  # ... your existing services (qdrant, postgres, redis) ...

  # OpenTelemetry Collector - Central telemetry hub
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.96.0
    container_name: bestbox-otel-collector
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./config/otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC receiver
      - "4318:4318"   # OTLP HTTP receiver
      - "8888:8888"   # Prometheus metrics endpoint (collector's own metrics)
    networks:
      - bestbox
    restart: unless-stopped

  # Jaeger - Distributed tracing UI
  jaeger:
    image: jaegertracing/all-in-one:1.54
    container_name: bestbox-jaeger
    environment:
      - COLLECTOR_OTLP_ENABLED=true
      - SPAN_STORAGE_TYPE=memory
    ports:
      - "16686:16686"  # Jaeger UI
      - "14268:14268"  # Jaeger collector HTTP
    networks:
      - bestbox
    restart: unless-stopped

  # Prometheus - Metrics storage
  prometheus:
    image: prom/prometheus:v2.50.0
    container_name: bestbox-prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    volumes:
      - ./config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./config/prometheus/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - bestbox
    restart: unless-stopped

  # Grafana - Unified dashboard
  grafana:
    image: grafana/grafana:10.3.3
    container_name: bestbox-grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-bestbox2026}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=http://localhost:3001
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_NAME=Main Org.
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
      - GF_SECURITY_ALLOW_EMBEDDING=true
    volumes:
      - ./config/grafana/provisioning:/etc/grafana/provisioning
      - ./config/grafana/dashboards:/etc/grafana/dashboards
      - grafana-data:/var/lib/grafana
    ports:
      - "3001:3000"  # Port 3001 to avoid conflict with Next.js
    depends_on:
      - prometheus
      - jaeger
    networks:
      - bestbox
    restart: unless-stopped

volumes:
  # ... your existing volumes ...
  prometheus-data:
    driver: local
  grafana-data:
    driver: local

networks:
  bestbox:
    driver: bridge
```

### OpenTelemetry Collector Configuration

```yaml
# config/otel-collector-config.yaml - NEW FILE

receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024

  # Add resource attributes to all telemetry
  resource:
    attributes:
      - key: service.namespace
        value: "bestbox"
        action: insert
      - key: deployment.environment
        value: "production"
        action: insert

exporters:
  # Send traces to Jaeger
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

  # Export metrics for Prometheus to scrape
  prometheus:
    endpoint: "0.0.0.0:8889"
    namespace: "bestbox"

  # Debug logging (disable in production for performance)
  logging:
    loglevel: info
    sampling_initial: 5
    sampling_thereafter: 200

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [otlp/jaeger, logging]

    metrics:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [prometheus, logging]
```

### Prometheus Configuration

```yaml
# config/prometheus/prometheus.yml - NEW FILE

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'bestbox-local'
    environment: 'production'

# Load alert rules
rule_files:
  - /etc/prometheus/alerts.yml

scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # OpenTelemetry Collector metrics
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8888']

  # BestBox Agent API metrics
  - job_name: 'agent-api'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s  # More frequent for real-time dashboards

  # LLM Server health (add /metrics endpoint if available)
  - job_name: 'llm-server'
    static_configs:
      - targets: ['host.docker.internal:8080']
    metrics_path: '/health'
    scrape_interval: 30s

  # Embeddings service
  - job_name: 'embeddings'
    static_configs:
      - targets: ['host.docker.internal:8081']
    metrics_path: '/health'
    scrape_interval: 30s
```

### Prometheus Alert Rules

```yaml
# config/prometheus/alerts.yml - NEW FILE

groups:
  - name: bestbox_sla_alerts
    interval: 30s
    rules:
      # TTFT SLA Violation
      - alert: HighLatencyP95
        expr: histogram_quantile(0.95, rate(agent_latency_seconds_bucket[5m])) > 2.0
        for: 5m
        labels:
          severity: warning
          component: llm
          sla: ttft
        annotations:
          summary: "P95 latency exceeds 2s SLA target"
          description: "Agent P95 response latency is {{ $value | humanizeDuration }} (SLA target: <2s)"
          dashboard: "http://localhost:3001/d/system-health"

      # Critical latency (P95 > 5s)
      - alert: CriticalLatency
        expr: histogram_quantile(0.95, rate(agent_latency_seconds_bucket[5m])) > 5.0
        for: 2m
        labels:
          severity: critical
          component: llm
        annotations:
          summary: "Critical latency degradation"
          description: "P95 latency is {{ $value | humanizeDuration }} - immediate investigation required"

      # High Error Rate
      - alert: HighErrorRate
        expr: rate(tool_executions_total{status="error"}[1m]) > 0.083
        for: 2m
        labels:
          severity: critical
          component: agents
        annotations:
          summary: "Error rate exceeds 5 errors/minute threshold"
          description: "Current error rate: {{ $value | humanize }} errors/sec"

      # Service Down
      - alert: ServiceDown
        expr: up{job=~"agent-api|llm-server|embeddings"} == 0
        for: 1m
        labels:
          severity: critical
          component: infrastructure
        annotations:
          summary: "Critical service is down"
          description: "{{ $labels.job }} has been unreachable for 1+ minutes"

      # Memory Pressure (>90% for 10+ minutes)
      - alert: HighMemoryUsage
        expr: (process_resident_memory_bytes{job="agent-api"} / (128 * 1024 * 1024 * 1024)) > 0.9
        for: 10m
        labels:
          severity: warning
          component: infrastructure
        annotations:
          summary: "System memory usage critically high"
          description: "Memory usage at {{ $value | humanizePercentage }}"

      # Low User Satisfaction
      - alert: LowUserSatisfaction
        expr: sum(user_feedback_total{rating="positive"}) / sum(user_feedback_total) < 0.7
        for: 1h
        labels:
          severity: warning
          component: ux
        annotations:
          summary: "User satisfaction below 70% target"
          description: "Current satisfaction: {{ $value | humanizePercentage }} (target: >80%)"

  - name: bestbox_capacity_alerts
    interval: 60s
    rules:
      # Approaching concurrent user limit
      - alert: HighConcurrentSessions
        expr: active_sessions > 8
        for: 5m
        labels:
          severity: warning
          component: capacity
        annotations:
          summary: "Approaching concurrent user capacity limit"
          description: "{{ $value }} active sessions (designed capacity: 5-8 users)"

      # Very high concurrency (system overload)
      - alert: SystemOverload
        expr: active_sessions > 12
        for: 1m
        labels:
          severity: critical
          component: capacity
        annotations:
          summary: "System is overloaded - user experience degraded"
          description: "{{ $value }} concurrent sessions exceeds safe operating limit"
```

---

## Grafana Dashboard Configuration

### Provisioning Structure

Create the Grafana provisioning directory structure:

```bash
mkdir -p config/grafana/provisioning/datasources
mkdir -p config/grafana/provisioning/dashboards
mkdir -p config/grafana/dashboards
```

### Configure Data Sources

```yaml
# config/grafana/provisioning/datasources/datasources.yaml - NEW FILE

apiVersion: 1

datasources:
  # Prometheus - Primary metrics source
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
      queryTimeout: "60s"

  # Jaeger - Distributed tracing
  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686
    editable: false
    jsonData:
      tracesToLogs:
        datasourceUid: 'postgres'

  # PostgreSQL - Audit logs and conversation history
  - name: BestBox PostgreSQL
    type: postgres
    access: proxy
    url: postgres:5432
    database: bestbox
    user: bestbox
    secureJsonData:
      password: bestbox_secure_2026
    jsonData:
      sslmode: disable
      postgresVersion: 1600
      timescaledb: false
```

### Dashboard Provisioning Config

```yaml
# config/grafana/provisioning/dashboards/dashboards.yaml - NEW FILE

apiVersion: 1

providers:
  - name: 'BestBox Dashboards'
    orgId: 1
    folder: 'BestBox'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/dashboards
```

### Dashboard 1: System Health

This dashboard provides real-time system status and SLA monitoring.

*Note: Full JSON dashboard definitions are available in Appendix A. Key panels include:*

**Panels:**
1. **Service Status** (Stat panel) - Up/Down indicators for all services
2. **Active Sessions** (Gauge) - Current concurrent users with capacity thresholds
3. **Time to First Token (TTFT)** (Time series) - P50/P95/P99 latency trends
4. **Request Rate by Agent** (Time series) - Requests per second by agent type
5. **Error Rate** (Time series) - Errors per minute with SLA threshold line
6. **Memory Utilization** (Time series) - RAM usage over time

**Alerts Configured:**
- TTFT P95 > 2s for 5 minutes
- Error rate > 5/min for 2 minutes

### Dashboard 2: User Analytics

This dashboard tracks user behavior and engagement patterns.

**Panels:**
1. **Total Sessions (24h)** (Stat) - Count of unique sessions
2. **Unique Users (24h)** (Stat) - Count of distinct user IDs
3. **User Satisfaction Score** (Gauge) - Thumbs up percentage with color thresholds
4. **Most Active Users** (Table) - Top 10 users by message count
5. **Agent Usage Distribution** (Pie chart) - Which agents get used most
6. **Session Length Trend** (Time series) - Average messages per session over time

**Data Source:** Mix of Prometheus (real-time) and PostgreSQL (detailed user data)

### Dashboard 3: Agent Performance

This dashboard measures agent intelligence and routing accuracy.

**Panels:**
1. **Router Accuracy (Estimated)** (Stat) - Based on low error rates + continued engagement
2. **Tool Success Rate** (Stat) - Percentage of successful tool executions
3. **Tokens Generated per Minute** (Time series) - LLM throughput
4. **Tool Execution Frequency** (Bar gauge) - Which tools are most used
5. **Agent Response Time by Type** (Heatmap) - Latency distribution across agents
6. **Failed Tool Calls** (Table) - Recent errors for debugging

**Filtering:** Time range selector, agent type filter

### Dashboard 4: Conversation Audit

This dashboard provides searchable conversation history with Jaeger integration.

**Panels:**
1. **Recent Conversations** (Table) - Last 50 conversations with:
   - Timestamp, User ID, Agent Type
   - User Query (first 100 chars)
   - Agent Response (first 100 chars)
   - Latency, Confidence, Feedback
   - **Trace ID** (clickable link to Jaeger)

2. **User Session Details** (Table) - Aggregated per-user statistics:
   - Total sessions, Total messages
   - Average messages per session
   - Last seen timestamp

3. **Search Filters** (Variables):
   - User ID (text input)
   - Agent Type (dropdown)
   - Date Range (time picker)
   - Feedback Filter (positive/negative/all)

**Data Source:** PostgreSQL exclusively (sensitive conversation data)

**Key Feature:** Clicking a Trace ID opens Jaeger UI showing the full waterfall view of that conversation's agent reasoning process.

---

## Frontend Integration

### User Feedback Component

Create reusable feedback buttons for message ratings:

```typescript
// frontend/copilot-demo/components/FeedbackButtons.tsx - NEW FILE

'use client';

import { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';

interface FeedbackButtonsProps {
  messageId: string;
  sessionId: string;
  onFeedbackSubmitted?: (rating: 'positive' | 'negative') => void;
}

export function FeedbackButtons({
  messageId,
  sessionId,
  onFeedbackSubmitted
}: FeedbackButtonsProps) {
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFeedback = async (rating: 'positive' | 'negative') => {
    if (feedback) return; // Already submitted

    setIsSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_id: messageId,
          session_id: sessionId,
          rating: rating
        })
      });

      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }

      setFeedback(rating);
      onFeedbackSubmitted?.(rating);

    } catch (error) {
      console.error('Failed to submit feedback:', error);
      alert('Failed to submit feedback. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex items-center gap-2 mt-2">
      <button
        onClick={() => handleFeedback('positive')}
        disabled={isSubmitting || feedback !== null}
        className={`p-1.5 rounded-md transition-all ${
          feedback === 'positive'
            ? 'bg-green-100 text-green-700 ring-2 ring-green-300'
            : 'hover:bg-gray-100 text-gray-500 hover:text-gray-700'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
        aria-label="Good response"
        title="This response was helpful"
      >
        <ThumbsUp size={16} className={feedback === 'positive' ? 'fill-current' : ''} />
      </button>

      <button
        onClick={() => handleFeedback('negative')}
        disabled={isSubmitting || feedback !== null}
        className={`p-1.5 rounded-md transition-all ${
          feedback === 'negative'
            ? 'bg-red-100 text-red-700 ring-2 ring-red-300'
            : 'hover:bg-gray-100 text-gray-500 hover:text-gray-700'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
        aria-label="Bad response"
        title="This response was not helpful"
      >
        <ThumbsDown size={16} className={feedback === 'negative' ? 'fill-current' : ''} />
      </button>

      {feedback && (
        <span className="text-xs text-gray-500 ml-2 animate-fade-in">
          Thank you for your feedback!
        </span>
      )}
    </div>
  );
}
```

### Feedback API Endpoint

Add feedback submission handler to Agent API:

```python
# services/agent_api.py - ADD NEW ENDPOINT

from pydantic import BaseModel

class FeedbackRequest(BaseModel):
    message_id: str  # Currently unused (could link to specific message ID in future)
    session_id: str
    rating: str  # 'positive' or 'negative'

@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Record user feedback for the most recent message in a session.
    """
    # Validate rating
    if request.rating not in ['positive', 'negative']:
        raise HTTPException(status_code=400, detail="Rating must be 'positive' or 'negative'")

    # Update Prometheus counter (real-time metrics)
    from observability import user_satisfaction
    user_satisfaction.labels(rating=request.rating).inc()

    # Update PostgreSQL (audit trail)
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            UPDATE conversation_log
            SET user_feedback = $1
            WHERE session_id = $2
              AND id = (
                  SELECT id
                  FROM conversation_log
                  WHERE session_id = $2
                  ORDER BY timestamp DESC
                  LIMIT 1
              )
            RETURNING id, agent_type, latency_ms
        """, request.rating, request.session_id)

        if not result:
            raise HTTPException(
                status_code=404,
                detail="No conversation found for this session"
            )

    return {
        "status": "success",
        "message": "Feedback recorded",
        "conversation_id": result['id']
    }
```

### Admin Panel Page

Create the admin dashboard interface:

```typescript
// frontend/copilot-demo/app/admin/page.tsx - NEW FILE

'use client';

import { useState } from 'react';
import { Activity, Users, BarChart3, MessageSquare, Settings, LogOut } from 'lucide-react';
import { SystemStatus } from '@/components/SystemStatus';

type DashboardView = 'system' | 'users' | 'agents' | 'conversations';

export default function AdminPage() {
  const [activeView, setActiveView] = useState<DashboardView>('system');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');

  // Simple password protection (replace with proper auth in production)
  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();

    // TODO: Replace with environment variable or proper auth
    if (password === process.env.NEXT_PUBLIC_ADMIN_PASSWORD || password === 'bestbox2026') {
      setIsAuthenticated(true);
      localStorage.setItem('admin_authenticated', 'true');
    } else {
      alert('Invalid password');
    }
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    localStorage.removeItem('admin_authenticated');
  };

  // Check localStorage on mount
  React.useEffect(() => {
    if (localStorage.getItem('admin_authenticated') === 'true') {
      setIsAuthenticated(true);
    }
  }, []);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-xl shadow-lg w-full max-w-md">
          <div className="flex items-center justify-center mb-6">
            <Settings className="text-blue-600 mr-2" size={32} />
            <h1 className="text-2xl font-bold text-gray-900">Admin Login</h1>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Admin Password
              </label>
              <input
                type="password"
                placeholder="Enter admin password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
              />
            </div>

            <button
              type="submit"
              className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Login
            </button>
          </form>

          <p className="text-xs text-gray-500 mt-4 text-center">
            Access restricted to authorized administrators only
          </p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'system' as const, label: 'System Health', icon: Activity },
    { id: 'users' as const, label: 'User Analytics', icon: Users },
    { id: 'agents' as const, label: 'Agent Performance', icon: BarChart3 },
    { id: 'conversations' as const, label: 'Conversation Audit', icon: MessageSquare },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">BestBox Admin Dashboard</h1>
            <p className="text-sm text-gray-500 mt-1">
              System observability and user analytics
            </p>
          </div>

          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <LogOut size={16} />
            Logout
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white border-b border-gray-200">
        <div className="px-6">
          <div className="flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveView(tab.id)}
                  className={`flex items-center gap-2 py-4 border-b-2 transition-colors font-medium ${
                    activeView === tab.id
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon size={18} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Dashboard Content */}
      <main className="p-6 space-y-6">
        {/* System Status Widget (always visible) */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity size={20} className="text-blue-600" />
            Service Health
          </h2>
          <SystemStatus />
        </div>

        {/* Main Dashboard Content */}
        <DashboardContent view={activeView} />
      </main>
    </div>
  );
}

function DashboardContent({ view }: { view: DashboardView }) {
  // Map view to Grafana dashboard UID (set in dashboard JSON)
  const dashboardUrls: Record<DashboardView, string> = {
    system: 'http://localhost:3001/d/system-health/bestbox-system-health',
    users: 'http://localhost:3001/d/user-analytics/bestbox-user-analytics',
    agents: 'http://localhost:3001/d/agent-performance/bestbox-agent-performance',
    conversations: 'http://localhost:3001/d/conversation-audit/bestbox-conversation-audit',
  };

  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      {/* Embedded Grafana Dashboard */}
      <iframe
        src={`${dashboardUrls[view]}?orgId=1&kiosk=tv&theme=light`}
        className="w-full h-[calc(100vh-400px)] min-h-[600px]"
        frameBorder="0"
        title={`${view} dashboard`}
        allow="fullscreen"
      />

      {/* Quick Actions Panel */}
      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <QuickActions view={view} />
      </div>
    </div>
  );
}

function QuickActions({ view }: { view: DashboardView }) {
  const actions: Record<DashboardView, Array<{ label: string; url?: string; action?: () => void }>> = {
    system: [
      { label: 'View Jaeger Traces', url: 'http://localhost:16686' },
      { label: 'Prometheus Metrics', url: 'http://localhost:9090' },
      { label: 'Download System Report', action: () => alert('Report download feature coming soon') },
    ],
    users: [
      { label: 'Export User Data (CSV)', action: () => alert('Export feature coming soon') },
      { label: 'User Segmentation Analysis', action: () => alert('Segmentation feature coming soon') },
    ],
    agents: [
      { label: 'View Failed Traces', url: 'http://localhost:16686/search?service=bestbox-agent-api&tags=%7B%22error%22%3A%22true%22%7D' },
      { label: 'Agent Performance Report', action: () => alert('Report generation coming soon') },
    ],
    conversations: [
      { label: 'Export Conversations (JSON)', action: () => alert('Export feature coming soon') },
      { label: 'Search by User ID', action: () => alert('Advanced search coming soon') },
    ],
  };

  return (
    <div className="flex flex-wrap items-center gap-4">
      <span className="text-sm text-gray-600 font-medium">Quick Actions:</span>
      {actions[view].map((action, idx) => (
        <button
          key={idx}
          onClick={() => action.url ? window.open(action.url, '_blank') : action.action?.()}
          className="text-sm text-blue-600 hover:text-blue-800 underline hover:no-underline transition-all"
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
```

### System Status Component

```typescript
// frontend/copilot-demo/components/SystemStatus.tsx - NEW FILE

'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertCircle, Loader2 } from 'lucide-react';

interface ServiceStatus {
  name: string;
  url: string;
  status: 'up' | 'down' | 'degraded' | 'checking';
  latency?: number;
  lastChecked?: Date;
}

export function SystemStatus() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'LLM Server', url: 'http://localhost:8080/health', status: 'checking' },
    { name: 'Embeddings', url: 'http://localhost:8081/health', status: 'checking' },
    { name: 'Agent API', url: 'http://localhost:8000/health', status: 'checking' },
    { name: 'Qdrant', url: 'http://localhost:6333/health', status: 'checking' },
    { name: 'PostgreSQL', url: 'http://localhost:8000/health/db', status: 'checking' },
  ]);

  useEffect(() => {
    const checkHealth = async () => {
      const updated = await Promise.all(
        services.map(async (service) => {
          try {
            const start = Date.now();
            const response = await fetch(service.url, {
              signal: AbortSignal.timeout(5000),
              cache: 'no-cache'
            });
            const latency = Date.now() - start;

            return {
              ...service,
              status: response.ok ? 'up' : 'degraded',
              latency,
              lastChecked: new Date(),
            } as ServiceStatus;
          } catch (error) {
            return {
              ...service,
              status: 'down' as const,
              lastChecked: new Date(),
            };
          }
        })
      );
      setServices(updated);
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {services.map((service) => (
        <ServiceCard key={service.name} service={service} />
      ))}
    </div>
  );
}

function ServiceCard({ service }: { service: ServiceStatus }) {
  const statusConfig = {
    up: {
      icon: CheckCircle,
      color: 'text-green-500',
      bg: 'bg-green-50',
      border: 'border-green-200',
    },
    degraded: {
      icon: AlertCircle,
      color: 'text-yellow-500',
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
    },
    down: {
      icon: XCircle,
      color: 'text-red-500',
      bg: 'bg-red-50',
      border: 'border-red-200',
    },
    checking: {
      icon: Loader2,
      color: 'text-gray-400',
      bg: 'bg-gray-50',
      border: 'border-gray-200',
    },
  };

  const config = statusConfig[service.status];
  const Icon = config.icon;

  return (
    <div className={`p-4 rounded-lg border ${config.border} ${config.bg} transition-all`}>
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-medium text-gray-900 text-sm">{service.name}</h3>
        <Icon
          className={`${config.color} ${service.status === 'checking' ? 'animate-spin' : ''}`}
          size={20}
        />
      </div>

      <div className="space-y-1">
        {service.latency !== undefined && (
          <p className="text-xs text-gray-600">
            Latency: <span className="font-mono font-medium">{service.latency}ms</span>
          </p>
        )}

        <p className="text-xs text-gray-500 capitalize">
          {service.status === 'checking' ? 'Checking...' : service.status}
        </p>
      </div>
    </div>
  );
}
```

### Update Main Chat UI

Integrate feedback buttons into existing chat:

```typescript
// frontend/copilot-demo/app/page.tsx - MODIFY MESSAGE RENDERING

import { FeedbackButtons } from '@/components/FeedbackButtons';

// In your message rendering logic, add after each assistant message:
{message.role === 'assistant' && (
  <FeedbackButtons
    messageId={message.id}
    sessionId={sessionId}
    onFeedbackSubmitted={(rating) => {
      console.log(`User rated message ${message.id} as ${rating}`);
      // Optional: Show a toast notification
    }}
  />
)}
```

### Add Admin Link to Navigation

```typescript
// frontend/copilot-demo/app/page.tsx - ADD TO HEADER/NAV

import Link from 'next/link';
import { Settings } from 'lucide-react';

// Add to your header/navigation area:
<div className="flex items-center gap-4">
  <Link
    href="/admin"
    className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
  >
    <Settings size={16} />
    <span className="hidden sm:inline">Admin</span>
  </Link>
</div>
```

---

## Deployment & Operations

### Deployment Script

```bash
#!/bin/bash
# scripts/deploy-observability.sh - NEW FILE

set -e

echo "🔧 BestBox Observability Stack Deployment"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo "📋 Step 1: Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}⚠️  PostgreSQL client not found. Install with: sudo apt install postgresql-client${NC}"
fi

echo -e "${GREEN}✅ Prerequisites OK${NC}"
echo ""

# Step 2: Generate secure credentials
echo "🔐 Step 2: Generating secure credentials..."

if [ ! -f .env.observability ]; then
    GRAFANA_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

    cat > .env.observability << EOF
# Grafana Admin Credentials
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASS}

# PostgreSQL Credentials (should match your existing setup)
POSTGRES_USER=bestbox
POSTGRES_PASSWORD=bestbox_secure_2026

# Admin Panel Password
ADMIN_PANEL_PASSWORD=${GRAFANA_PASS}

# Retention Policies
PROMETHEUS_RETENTION_DAYS=30
JAEGER_RETENTION_DAYS=7

# Optional: Alert notification endpoints
ALERT_EMAIL=
ALERT_SLACK_WEBHOOK=
EOF

    echo -e "${GREEN}✅ Generated .env.observability with secure passwords${NC}"
    echo -e "${YELLOW}⚠️  SAVE THIS PASSWORD: ${GRAFANA_PASS}${NC}"
else
    echo -e "${YELLOW}⚠️  .env.observability already exists, skipping generation${NC}"
fi
echo ""

# Step 3: Create directory structure
echo "📁 Step 3: Creating configuration directories..."

mkdir -p config/prometheus
mkdir -p config/grafana/provisioning/datasources
mkdir -p config/grafana/provisioning/dashboards
mkdir -p config/grafana/dashboards
mkdir -p data/prometheus
mkdir -p data/grafana
mkdir -p reports

echo -e "${GREEN}✅ Directories created${NC}"
echo ""

# Step 4: Database migration
echo "🗄️  Step 4: Running database migrations..."

if [ -f migrations/003_observability_tables.sql ]; then
    source .env.observability

    PGPASSWORD=${POSTGRES_PASSWORD} psql -h localhost -U ${POSTGRES_USER} -d bestbox \
        -f migrations/003_observability_tables.sql \
        2>/dev/null && echo -e "${GREEN}✅ Database schema updated${NC}" || \
        echo -e "${YELLOW}⚠️  Migration may have already run (this is OK)${NC}"
else
    echo -e "${RED}❌ migrations/003_observability_tables.sql not found${NC}"
    exit 1
fi
echo ""

# Step 5: Install Python dependencies
echo "🐍 Step 5: Installing Python observability libraries..."

if [ -f ~/BestBox/venv/bin/activate ]; then
    source ~/BestBox/venv/bin/activate

    pip install -q opentelemetry-api \
                   opentelemetry-sdk \
                   opentelemetry-exporter-otlp-proto-grpc \
                   openinference-instrumentation-langchain \
                   prometheus-client \
                   asyncpg

    echo -e "${GREEN}✅ Python dependencies installed${NC}"
else
    echo -e "${RED}❌ Virtual environment not found at ~/BestBox/venv${NC}"
    exit 1
fi
echo ""

# Step 6: Start observability services
echo "🚀 Step 6: Starting observability stack..."

docker compose up -d otel-collector jaeger prometheus grafana

echo -e "${GREEN}✅ Services started${NC}"
echo ""

# Step 7: Wait for services to be ready
echo "⏳ Step 7: Waiting for services to initialize (30 seconds)..."
sleep 30

# Step 8: Verify services
echo "🔍 Step 8: Verifying service health..."

services=(
  "http://localhost:4318|OpenTelemetry Collector"
  "http://localhost:16686|Jaeger UI"
  "http://localhost:9090|Prometheus"
  "http://localhost:3001|Grafana"
)

all_healthy=true
for service in "${services[@]}"; do
  IFS='|' read -r url name <<< "$service"

  if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -qE "200|302|401"; then
    echo -e "  ${GREEN}✅ $name is up${NC}"
  else
    echo -e "  ${RED}❌ $name failed to start${NC}"
    all_healthy=false
  fi
done
echo ""

# Step 9: Display summary
if [ "$all_healthy" = true ]; then
    source .env.observability

    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}║     🎉 Observability Stack Successfully Deployed! 🎉     ║${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "📊 Access URLs:"
    echo "  • Grafana Dashboard:  http://localhost:3001"
    echo "    Username: admin"
    echo "    Password: ${GRAFANA_ADMIN_PASSWORD}"
    echo ""
    echo "  • Jaeger Traces:      http://localhost:16686"
    echo "  • Prometheus:         http://localhost:9090"
    echo "  • Admin Panel:        http://localhost:3000/admin"
    echo ""
    echo "⚠️  IMPORTANT: Save your Grafana password securely!"
    echo ""
    echo "📝 Next Steps:"
    echo "  1. Restart Agent API to enable instrumentation:"
    echo "     ./scripts/start-agent-api.sh"
    echo ""
    echo "  2. Test the system:"
    echo "     - Visit http://localhost:3000 and send a message"
    echo "     - Click thumbs up/down to test feedback"
    echo "     - View metrics at http://localhost:3001"
    echo ""
    echo "  3. Review the Observability Playbook:"
    echo "     docs/observability_playbook.md"
    echo ""
else
    echo -e "${RED}❌ Some services failed to start. Check logs with:${NC}"
    echo "   docker compose logs otel-collector"
    echo "   docker compose logs grafana"
    echo "   docker compose logs prometheus"
    echo "   docker compose logs jaeger"
    exit 1
fi
```

Make executable:

```bash
chmod +x scripts/deploy-observability.sh
```

### Health Check Additions

Add database health check to Agent API:

```python
# services/agent_api.py - ADD HEALTH CHECK ENDPOINT

@app.get("/health/db")
async def health_check_database():
    """
    Database connectivity health check.
    Used by SystemStatus component in admin UI.
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "error": str(e)}
        )
```

---

## Continuous Improvement Process

### Weekly Review Workflow

Create structured process for using observability data:

```markdown
# docs/observability_playbook.md - NEW FILE

# BestBox Observability Playbook

## Purpose

This playbook defines how to use observability data to continuously improve BestBox quality, performance, and user experience.

## Weekly Review Cycle

### Monday Morning Review (30 minutes)

**Goal:** Identify issues from the past week and prioritize fixes

1. **Access Weekly Report**
   - Check `reports/` folder for auto-generated HTML report
   - Or run manually: `python scripts/generate_weekly_report.py`

2. **Review Key Metrics**
   - [ ] **SLA Compliance**
     - TTFT P95 < 2s? ✅ ❌
     - Error rate < 5%? ✅ ❌
     - User satisfaction > 80%? ✅ ❌

   - [ ] **Growth Trends**
     - Total sessions vs. last week: ↗️ ↘️
     - Unique users vs. last week: ↗️ ↘️
     - Messages per session: ↗️ ↘️

3. **Check Alerts**
   - Open Prometheus alerts: http://localhost:9090/alerts
   - Document any fired alerts in incident log
   - Example: `docs/incidents/2026-01-24-high-latency.md`

4. **Prioritize Actions**
   - Create GitHub issues for:
     - 🔴 Critical: Service downtime, P95 > 5s, error rate > 10%
     - 🟡 Warning: User satisfaction < 75%, P95 > 3s
     - 🟢 Enhancement: Feature requests from user feedback

   - Tag with `observability`, `performance`, or `quality` labels

### Friday Afternoon Review (15 minutes)

**Goal:** Understand user pain points through conversation analysis

1. **Sample Negative Feedback**
   - Open Conversation Audit dashboard
   - Filter for `user_feedback = 'negative'`
   - Review 5-10 thumbs-down conversations

2. **Look for Patterns**
   - ❓ **Specific agent failing?**
     - Example: "CRM agent has 15% negative feedback"
     - Root cause: Missing tool for bulk operations

   - ❓ **Query types struggling?**
     - Example: "Price calculation queries slow"
     - Root cause: Complex SQL query in ERP tool

   - ❓ **Hallucinations?**
     - Example: "Agent invents customer data"
     - Root cause: RAG relevance score too low (<0.5)

3. **Document Insights**
   - Add to monthly insights log: `docs/insights/2026-01.md`
   - Format:
     ```markdown
     ## 2026-01-24 Insight
     - **Finding**: CRM agent negative feedback 15% on pricing queries
     - **Evidence**: 12/80 pricing conversations got thumbs down
     - **Root cause**: Missing `get_bulk_pricing` tool
     - **Action**: Issue #123 created to implement tool
     - **Expected impact**: +10% satisfaction in CRM domain
     ```

## Monthly Deep Dive (2 hours)

### Performance Optimization Session

**Schedule:** First Monday of each month

1. **Identify Bottlenecks**

   Run Prometheus queries:

   ```promql
   # Slowest agent types (P95 latency)
   topk(5, histogram_quantile(0.95, rate(agent_latency_seconds_bucket[30d])))

   # Most error-prone tools
   topk(10, sum by (tool_name) (rate(tool_executions_total{status="error"}[30d])))

   # RAG performance
   histogram_quantile(0.95, rate(rag_retrieval_seconds_bucket[30d]))
   ```

2. **Analyze Root Causes**

   For slow agents:
   - Open Jaeger: http://localhost:16686
   - Search: `service=bestbox-agent-api duration>5s`
   - Click a trace → analyze waterfall view

   Common bottlenecks:
   - **RAG retrieval slow** → Tune Qdrant query, reduce `top_k`
   - **LLM generation slow** → Check GPU utilization with `rocm-smi`
   - **Tool execution slow** → Add caching, implement timeouts
   - **Router slow** (unlikely) → Simplify classification prompt

3. **Implement Optimizations**

   Example optimization workflow:
   ```markdown
   ## Optimization: Reduce RAG Latency

   **Baseline:** P95 retrieval = 450ms

   **Changes:**
   1. Reduced `top_k` from 10 to 5
   2. Added pre-filtering by domain
   3. Enabled Qdrant HNSW optimization

   **Result:** P95 retrieval = 180ms (60% improvement)

   **Verification:**
   - Prometheus query shows improvement
   - User satisfaction unchanged (quality maintained)
   ```

### Agent Quality Improvement Session

**Schedule:** Third Friday of each month

1. **Measure Router Accuracy**

   ```sql
   -- Find conversations where user had to switch agents
   SELECT
     session_id,
     array_agg(DISTINCT agent_type ORDER BY timestamp) as agent_sequence,
     COUNT(DISTINCT agent_type) as agent_switches
   FROM conversation_log
   WHERE timestamp > NOW() - INTERVAL '30 days'
   GROUP BY session_id
   HAVING COUNT(DISTINCT agent_type) > 2
   ORDER BY agent_switches DESC
   LIMIT 20;
   ```

   **Interpretation:**
   - `agent_sequence = ['router', 'erp', 'crm']` → User asked ERP question, got routed to CRM by mistake
   - High `agent_switches` → Router confusion

2. **Improve Router Prompts**

   For misrouted queries:
   1. Review the original user message
   2. Understand why router chose wrong agent
   3. Add example to router system prompt

   Example:
   ```python
   # agents/router.py - ADD TO SYSTEM PROMPT

   """
   Examples of ERP queries:
   - "What's our inventory level for SKU-12345?"
   - "Create a purchase order for 100 units"
   - "Show me pending invoices"  ← ADDED (was misrouted to CRM)
   """
   ```

3. **Evaluate Tool Effectiveness**

   ```sql
   -- Tools with high usage but low user satisfaction
   SELECT
     tool_calls->>'name' as tool_name,
     COUNT(*) as usage_count,
     AVG(CASE WHEN user_feedback = 'positive' THEN 1.0 ELSE 0.0 END) as satisfaction,
     AVG(latency_ms) as avg_latency_ms
   FROM conversation_log
   WHERE tool_calls IS NOT NULL
     AND timestamp > NOW() - INTERVAL '30 days'
   GROUP BY tool_name
   HAVING COUNT(*) > 10
   ORDER BY satisfaction ASC;
   ```

   **Action items:**
   - Satisfaction < 50% → Tool may be returning wrong data, review implementation
   - Latency > 2000ms → Tool is slow, add caching or optimize query

## Incident Response

### When Alert Fires

#### Alert: HighLatencyP95

**Severity:** Warning
**SLA Impact:** TTFT target violated (>2s)

**Response:**
1. Check LLM server health: `curl http://localhost:8080/health`
2. Check GPU utilization: `rocm-smi` (or `nvidia-smi`)
3. If GPU memory full: Restart LLM server
   ```bash
   pkill llama-server
   ./scripts/start-llm.sh
   ```
4. If GPU OK: Check Qdrant response time
   ```bash
   curl http://localhost:6333/health
   ```
5. Document in incident log: `docs/incidents/YYYY-MM-DD-high-latency.md`

**Escalation:** If latency >5s for >10 minutes, page on-call engineer

#### Alert: ServiceDown

**Severity:** Critical
**SLA Impact:** System unavailable

**Response:**
1. Identify which service: Check alert labels
2. Check Docker: `docker ps | grep <service>`
3. View logs: `docker logs bestbox-<service>`
4. Restart if needed: `docker compose restart <service>`
5. If database: Check PostgreSQL logs
   ```bash
   docker logs bestbox-postgres
   ```
6. Update status page (if external users affected)

**Escalation:** Immediate if downtime >5 minutes

#### Alert: LowUserSatisfaction

**Severity:** Warning
**SLA Impact:** User experience degraded

**Response:**
1. Not an immediate incident - schedule review
2. Sample recent negative feedback conversations:
   - Open Grafana Conversation Audit
   - Filter last 24 hours, negative feedback
3. Look for systemic issues (not one-off bad responses)
4. Create improvement ticket if pattern found
5. Plan fix for next sprint

**Escalation:** None (quality improvement, not outage)

## Success Metrics

Track these monthly to measure observability ROI:

| Metric | Definition | Month 1 | Month 2 | Target |
|--------|-----------|---------|---------|--------|
| **MTTD** (Mean Time to Detect) | Avg time from issue start to alert | — | — | <5 min |
| **MTTR** (Mean Time to Resolve) | Avg time from alert to resolution | — | — | <30 min |
| **User Satisfaction Trend** | Month-over-month satisfaction change | — | — | >80%, +2% MoM |
| **P95 Latency Trend** | Month-over-month latency change | — | — | <2s, -10% MoM |
| **Incident Count** | Production incidents per month | — | — | <2/month |
| **Optimization Impact** | Performance improvements from data-driven optimizations | — | — | >20% improvement/quarter |

## Tools Quick Reference

| Tool | URL | Purpose |
|------|-----|---------|
| **Grafana** | http://localhost:3001 | Primary dashboards, real-time monitoring |
| **Jaeger** | http://localhost:16686 | Trace debugging, waterfall views |
| **Prometheus** | http://localhost:9090 | Metric queries, alert management |
| **Admin Panel** | http://localhost:3000/admin | Embedded Grafana with quick actions |
| **PostgreSQL** | `psql -U bestbox -d bestbox` | Raw conversation data queries |

## Monthly Report Template

Use this template for stakeholder reporting:

```markdown
# BestBox Monthly Performance Report - [Month Year]

## Executive Summary

- **Total Sessions:** [number] ([+/-X%] vs last month)
- **User Satisfaction:** [X%] ([+/-X%] vs last month)
- **P95 Latency:** [X]ms ([+/-X%] vs last month)
- **Uptime:** [99.X%]

## Key Achievements

1. [Achievement 1 - e.g., "Reduced latency by 30% through RAG optimization"]
2. [Achievement 2]
3. [Achievement 3]

## Issues & Resolutions

| Issue | Impact | Resolution | Status |
|-------|--------|------------|--------|
| High latency on 01/15 | 200 users affected | Restarted LLM server | ✅ Resolved |
| Router accuracy drop | 5% misroutes | Updated prompts | ✅ Resolved |

## Optimizations Implemented

1. **[Optimization name]**
   - Baseline: [metric]
   - Result: [metric]
   - Impact: [user-facing improvement]

## Next Month Priorities

1. [Priority 1]
2. [Priority 2]
3. [Priority 3]

## Appendix: Raw Metrics

- Total messages: [X]
- Average session length: [X] messages
- Agent usage: ERP [X%], CRM [X%], IT Ops [X%], OA [X%]
- Tool success rate: [X%]
```

---

## Conclusion

This observability design transforms BestBox from a demo system into a production-ready platform with:

✅ **Comprehensive tracking** - Every user interaction logged and traceable
✅ **Real-time monitoring** - SLA compliance visible in <10 seconds
✅ **Data-driven improvement** - Structured process for continuous optimization
✅ **Admin-friendly UI** - Non-technical stakeholders can view metrics
✅ **Incident readiness** - Automated alerts and response playbooks

**Implementation Timeline:**

- Week 1: Deploy observability stack (4 hours)
- Week 2: Instrument Agent API (6 hours)
- Week 3: Build Grafana dashboards (8 hours)
- Week 4: Frontend integration + testing (6 hours)

**Total effort:** ~24 hours of development time

**Ongoing maintenance:** ~2 hours/week (weekly reviews + monthly deep dives)

---

## Appendix

### Appendix A: Full Dashboard JSON

Due to length constraints, full Grafana dashboard JSON definitions are available in:
- `config/grafana/dashboards/system-health.json`
- `config/grafana/dashboards/user-analytics.json`
- `config/grafana/dashboards/agent-performance.json`
- `config/grafana/dashboards/conversation-audit.json`

These files will be generated by the deployment script or can be exported from Grafana after manual creation.

### Appendix B: Environment Variables Reference

```bash
# .env.observability

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<generated-secure-password>

# PostgreSQL (should match docker-compose.yml)
POSTGRES_USER=bestbox
POSTGRES_PASSWORD=bestbox_secure_2026

# Admin Panel
ADMIN_PANEL_PASSWORD=<same-as-grafana-password>

# Retention
PROMETHEUS_RETENTION_DAYS=30
JAEGER_RETENTION_DAYS=7

# Alerts (optional)
ALERT_EMAIL=admin@example.com
ALERT_SLACK_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Appendix C: PostgreSQL Queries Cheat Sheet

```sql
-- Most active users (last 7 days)
SELECT
  us.user_id,
  COUNT(cl.id) as total_messages,
  MAX(cl.timestamp) as last_active,
  AVG(cl.latency_ms) as avg_latency
FROM user_sessions us
JOIN conversation_log cl ON us.session_id = cl.session_id
WHERE cl.timestamp > NOW() - INTERVAL '7 days'
GROUP BY us.user_id
ORDER BY total_messages DESC
LIMIT 10;

-- Conversations with negative feedback
SELECT
  cl.timestamp,
  us.user_id,
  cl.user_message,
  cl.agent_response,
  cl.agent_type,
  cl.trace_id
FROM conversation_log cl
JOIN user_sessions us ON cl.session_id = us.session_id
WHERE cl.user_feedback = 'negative'
  AND cl.timestamp > NOW() - INTERVAL '24 hours'
ORDER BY cl.timestamp DESC;

-- Agent performance by domain
SELECT
  agent_type,
  COUNT(*) as total_requests,
  AVG(latency_ms) as avg_latency,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
  SUM(CASE WHEN user_feedback = 'positive' THEN 1 ELSE 0 END)::float /
    NULLIF(SUM(CASE WHEN user_feedback IS NOT NULL THEN 1 ELSE 0 END), 0) as satisfaction_rate
FROM conversation_log
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY agent_type
ORDER BY total_requests DESC;

-- Tool usage statistics
SELECT
  tool_calls->>'name' as tool_name,
  COUNT(*) as usage_count,
  AVG((tool_calls->>'latency_ms')::int) as avg_latency_ms,
  SUM(CASE WHEN tool_calls->>'error' IS NULL THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM conversation_log,
  jsonb_array_elements(tool_calls) as tool_calls
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY tool_name
ORDER BY usage_count DESC;
```

### Appendix D: Troubleshooting Guide

**Problem:** Grafana dashboards show "No data"

**Solutions:**
1. Check Prometheus is scraping metrics:
   - Open http://localhost:9090/targets
   - Verify all targets are "UP"
2. Check Agent API `/metrics` endpoint:
   - `curl http://localhost:8000/metrics`
   - Should return Prometheus-formatted metrics
3. Check time range in Grafana:
   - Ensure you're looking at "Last 1 hour" or similar
   - No data exists if system just started

**Problem:** Jaeger shows no traces

**Solutions:**
1. Verify OpenTelemetry Collector is running:
   - `docker logs bestbox-otel-collector`
2. Check Agent API is exporting traces:
   - Look for "Span exported" in Agent API logs
3. Verify OTLP endpoint is correct:
   - Should be `http://localhost:4317` in agent_api.py

**Problem:** PostgreSQL queries fail in Grafana

**Solutions:**
1. Check datasource configuration:
   - Grafana → Datasources → BestBox PostgreSQL
   - Click "Test" button
2. Verify database schema exists:
   - `psql -U bestbox -d bestbox -c "\dt"`
   - Should show `user_sessions` and `conversation_log` tables
3. Check PostgreSQL is accessible from Grafana container:
   - `docker exec bestbox-grafana ping postgres`

---

**Document Version:** 1.0
**Last Updated:** January 24, 2026
**Next Review:** After implementation completion
