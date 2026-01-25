# BestBox Observability Playbook

## Purpose

This playbook defines how to use observability data to continuously improve BestBox quality, performance, and user experience.

## Weekly Review Cycle

### Monday Morning Review (30 minutes)

**Goal:** Identify issues from the past week and prioritize fixes

1. **Review Key Metrics (Grafana)**
   - Open http://localhost:3001
   - Check System Health dashboard

   - [ ] **SLA Compliance**
     - TTFT P95 < 2s? ✅ ❌
     - Error rate < 5%? ✅ ❌
     - User satisfaction > 80%? ✅ ❌

   - [ ] **Growth Trends**
     - Total sessions vs. last week: ↗️ ↘️
     - Unique users vs. last week: ↗️ ↘️
     - Messages per session: ↗️ ↘️

2. **Check Alerts**
   - Open Prometheus alerts: http://localhost:9090/alerts
   - Document any fired alerts in `docs/incidents/YYYY-MM-DD-<issue>.md`
   - Example template:
     ```markdown
     # High Latency Incident - 2026-01-24

     **Duration:** 10:30 AM - 10:45 AM (15 minutes)
     **Severity:** Warning
     **Impact:** 50 users experienced slow responses (TTFT > 3s)

     ## Root Cause
     LLM server memory leak caused GPU memory exhaustion

     ## Resolution
     Restarted llama-server service

     ## Prevention
     - Add memory monitoring alert
     - Investigate memory leak in llama.cpp
     ```

3. **Prioritize Actions**
   - Create GitHub issues for:
     - 🔴 **Critical**: Service downtime, P95 > 5s, error rate > 10%
     - 🟡 **Warning**: User satisfaction < 75%, P95 > 3s
     - 🟢 **Enhancement**: Feature requests from user feedback

   - Tag with `observability`, `performance`, or `quality` labels

### Friday Afternoon Review (15 minutes)

**Goal:** Understand user pain points through conversation analysis

1. **Sample Negative Feedback**
   - Open Conversation Audit dashboard in Grafana
   - Filter for negative feedback (thumbs down)
   - Review 5-10 conversations

2. **Look for Patterns**
   - ❓ **Specific agent failing?**
     - Example: "CRM agent has 15% negative feedback on price queries"
     - Root cause: Missing tool for bulk pricing lookup

   - ❓ **Query types struggling?**
     - Example: "Complex multi-step queries timeout"
     - Root cause: Agent plan exceeds 5-step limit

   - ❓ **Hallucinations?**
     - Example: "Agent invents customer data not in database"
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

1. **Identify Bottlenecks with Prometheus**

   Run these queries in Prometheus (http://localhost:9090):

   ```promql
   # Slowest agent types (P95 latency)
   topk(5, histogram_quantile(0.95, rate(agent_latency_seconds_bucket[30d])))

   # Most error-prone tools
   topk(10, sum by (tool_name) (rate(tool_executions_total{status="error"}[30d])))

   # RAG retrieval performance
   histogram_quantile(0.95, rate(rag_retrieval_seconds_bucket[30d]))
   ```

2. **Analyze Root Causes with Jaeger**

   For slow agents:
   - Open Jaeger: http://localhost:16686
   - Search: `service=bestbox-agent-api duration>5s`
   - Click a trace → analyze waterfall view

   Common bottlenecks:
   - **RAG retrieval slow** (>500ms) → Tune Qdrant, reduce `top_k`
   - **LLM generation slow** (<20 tok/s) → Check GPU utilization
   - **Tool execution slow** (>2s) → Add caching, implement timeouts
   - **Router slow** (>500ms, unlikely) → Simplify classification prompt

3. **Implement Optimizations**

   Example workflow:
   ```markdown
   ## Optimization: Reduce RAG Latency

   **Baseline:** P95 retrieval = 450ms

   **Changes:**
   1. Reduced `top_k` from 10 to 5
   2. Added pre-filtering by domain
   3. Enabled Qdrant HNSW optimization

   **Result:** P95 retrieval = 180ms (60% improvement)

   **Verification:**
   - Prometheus shows P95 < 200ms ✅
   - User satisfaction unchanged (quality maintained) ✅
   ```

### Agent Quality Improvement Session

**Schedule:** Third Friday of each month

1. **Measure Router Accuracy**

   Query PostgreSQL for misrouted conversations:

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
   - High `agent_switches` → Router confusion, needs prompt improvement

2. **Improve Router Prompts**

   For each misrouted query:
   1. Review the original user message
   2. Understand why router chose wrong agent
   3. Add example to router system prompt in `agents/router.py`

3. **Evaluate Tool Effectiveness**

   ```sql
   -- Tools with high usage but low user satisfaction
   SELECT
     tool_calls->>'name' as tool_name,
     COUNT(*) as usage_count,
     AVG(CASE WHEN user_feedback = 'positive' THEN 1.0 ELSE 0.0 END) as satisfaction,
     AVG(latency_ms) as avg_latency_ms
   FROM conversation_log,
     jsonb_array_elements(tool_calls) as tool_calls
   WHERE timestamp > NOW() - INTERVAL '30 days'
   GROUP BY tool_name
   HAVING COUNT(*) > 10
   ORDER BY satisfaction ASC;
   ```

   **Action items:**
   - Satisfaction < 50% → Tool returning wrong data, review implementation
   - Latency > 2000ms → Tool is slow, add caching or optimize

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

**Escalation:** If latency >5s for >10 minutes, notify team lead

#### Alert: ServiceDown

**Severity:** Critical
**SLA Impact:** System unavailable

**Response:**
1. Identify which service from alert labels
2. Check Docker: `docker ps | grep <service>`
3. View logs: `docker logs bestbox-<service>`
4. Restart if needed: `docker compose restart <service>`
5. If PostgreSQL down: Check disk space
   ```bash
   df -h
   docker logs bestbox-postgres
   ```

**Escalation:** Immediate if downtime >5 minutes

#### Alert: LowUserSatisfaction

**Severity:** Warning
**SLA Impact:** User experience degraded

**Response:**
1. Not an immediate incident - schedule review
2. Sample recent negative feedback:
   - Open Grafana Conversation Audit
   - Filter last 24 hours, negative feedback only
3. Look for systemic issues (not one-off bad responses)
4. Create improvement ticket if pattern found

**Escalation:** None (quality improvement, not outage)

## Success Metrics

Track these monthly to measure observability ROI:

| Metric | Definition | Target | How to Measure |
|--------|-----------|--------|----------------|
| **MTTD** (Mean Time to Detect) | Avg time from issue start to alert firing | <5 min | Prometheus alert history |
| **MTTR** (Mean Time to Resolve) | Avg time from alert to resolution | <30 min | Incident log timestamps |
| **User Satisfaction Trend** | Month-over-month change | >80%, +2% MoM | Grafana User Analytics |
| **P95 Latency Trend** | Month-over-month change | <2s, -10% MoM | Grafana System Health |
| **Incident Count** | Production incidents per month | <2/month | Count incident logs |

## Tools Quick Reference

| Tool | URL | Purpose |
|------|-----|---------|
| **Grafana** | http://localhost:3001 | Primary dashboards, real-time monitoring |
| **Jaeger** | http://localhost:16686 | Trace debugging, waterfall views |
| **Prometheus** | http://localhost:9090 | Metric queries, alert management |
| **Admin Panel** | http://localhost:3000/admin | Embedded Grafana with quick actions |
| **PostgreSQL** | `psql -U bestbox -d bestbox` | Raw conversation data queries |

## PostgreSQL Queries Cheat Sheet

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

-- Agent performance by type
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
```

---

**Last Updated:** January 24, 2026
**Next Review:** After first week of production use
