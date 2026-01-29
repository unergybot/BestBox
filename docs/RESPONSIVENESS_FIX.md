# BestBox Responsiveness Improvement Plan

**Date:** January 25, 2026  
**Status:** 🔧 Implemented - Requires LLM Restart  
**Issue:** Multi-minute response delays, "Context size exceeded" errors

---

## 🔍 Root Cause Analysis

### Problem 1: Context Overflow (PRIMARY CAUSE)
**Symptom:** `Agent error: Context size has been exceeded`

**Root Cause:**
- LLM server was configured with `CONTEXT_SIZE=4096` tokens
- Qwen2.5-14B model supports up to 32,768 tokens natively
- Messages accumulated without truncation
- Each agent adds system prompts (~300-600 tokens each)
- Tool results (especially RAG) can be 500-2000 tokens
- After 5-6 turns, context exceeded 4096 tokens → crash

**Evidence:**
```bash
curl http://localhost:8080/v1/models | jq '.data[0].meta.n_ctx_train'
# Returns: 32768 (model capability)
# But start-llm.sh had: CONTEXT_SIZE=4096 (configured limit)
```

### Problem 2: No Context Management
- Messages passed to LLM with full history
- No sliding window implementation
- Long tool results not truncated
- System prompts were verbose (~500 tokens each)

### Problem 3: Cascade Latency
- Router invokes LLM → Agent invokes LLM → Tools invoked → Agent re-invoked
- Each LLM call: 2-10 seconds depending on context size
- Large contexts = slower inference (O(n²) attention)
- No early termination on errors

---

## ✅ Fixes Implemented

### 1. Increased Context Size
**File:** [scripts/start-llm.sh](scripts/start-llm.sh)
```bash
# Before: CONTEXT_SIZE=4096
# After:  CONTEXT_SIZE=8192
```

**Why 8192 not 32768?**
- Larger contexts = slower inference
- 8K is optimal for multi-turn conversation
- Leaves headroom for response generation

### 2. Context Manager Module
**File:** [agents/context_manager.py](agents/context_manager.py)

New module provides:
- `apply_sliding_window()` - Keeps recent messages within token limit
- `truncate_tool_result()` - Reduces large tool outputs
- `estimate_tokens()` - Fast character-based estimation
- `get_context_stats()` - Debugging context usage

### 3. Compact System Prompts
All agent system prompts reduced by ~60%:
- Router: 500 → 200 tokens
- ERP: 400 → 150 tokens  
- CRM, IT Ops, OA: Similar reductions

### 4. Router Optimization
- Router now uses max 3 messages (most recent)
- Only needs 1500 tokens for classification
- Fallback changed to `general_agent` (not `fallback`)

### 5. Agent Context Limits
Each agent now applies:
```python
managed_messages = apply_sliding_window(
    state["messages"],
    max_tokens=6000,  # Leave room for response
    max_messages=8,   # Limit conversation depth
    keep_system=False
)
```

### 6. Enhanced Observability
**File:** [services/observability.py](services/observability.py)

New metrics added:
- `context_tokens_used` - Track context consumption
- `context_truncation_total` - Count truncation events
- `llm_errors_total` - Categorized error tracking

### 7. Improved Timeouts
**File:** [agents/utils.py](agents/utils.py)
- Timeout: 60s → 120s for complex queries
- Added `max_retries=2` for transient failures

---

## 🚀 Deployment Steps

### Step 1: Restart LLM Server
```bash
# Stop current server
pkill -f "llama-server.*8080"

# Wait for clean shutdown
sleep 3

# Start with new config
./scripts/start-llm.sh
```

### Step 2: Restart Agent API
```bash
# If running directly:
pkill -f "agent_api.py"
cd /home/unergy/BestBox
python services/agent_api.py &

# Or restart the service if using systemd/docker
```

### Step 3: Verify Configuration
```bash
# Check LLM context size
curl -s http://localhost:8080/health
curl -s http://localhost:8080/v1/models | jq '.data[0]'

# Test simple query
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hi, what can you do?"}]}'
```

---

## 📊 Expected Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Context errors | Frequent | Rare | 95%+ reduction |
| Router latency | 3-5s | 1-2s | 2x faster |
| Agent response | 5-30s | 2-8s | 3x faster |
| Multi-turn capacity | 5-6 turns | 15+ turns | 3x longer |
| Error recovery | Crash | Graceful | Much improved |

---

## 📈 Monitoring & Telemetry

### Check Grafana Dashboards
- **URL:** http://localhost:3001 (admin/bestbox)
- Look for `agent_latency_seconds` histogram
- Monitor `context_tokens_used` distribution
- Alert on `llm_errors_total{error_type="context_exceeded"}`

### Prometheus Queries
```promql
# Average response time by agent
histogram_quantile(0.95, rate(agent_latency_seconds_bucket[5m]))

# Context overflow events
increase(llm_errors_total{error_type="context_exceeded"}[1h])

# Active sessions
active_sessions
```

### Jaeger Tracing
- **URL:** http://localhost:16686
- Search for service: `bestbox-agent-api`
- Look for long spans in `LangChainInstrumentor`

---

## 🔮 Future Optimizations

### Phase 2: Response Streaming
Currently responses wait for full completion. Enable:
1. Token-by-token streaming from llama-server
2. SSE streaming to frontend
3. Progressive rendering in UI

### Phase 3: Parallel Processing
- Router and agent can run in parallel for known patterns
- Pre-fetch tool results during LLM generation
- Cache frequent queries

### Phase 4: Model Optimization
- Consider Qwen2.5-7B for router (faster, smaller)
- Speculative decoding for faster generation
- Flash attention optimizations

---

## 🐛 Troubleshooting

### "Context size exceeded" still occurs
1. Check if LLM was restarted with new config
2. Verify: `curl http://localhost:8080/v1/models | jq '.data[0].meta'`
3. Check agent logs for context stats

### Slow first response
- LLM needs warm-up after restart
- First query loads KV cache
- Expected: 5-10s for first, faster after

### No metrics in Prometheus
1. Verify agent API is running: `curl http://localhost:8000/metrics`
2. Check Prometheus targets: http://localhost:9090/targets
3. Verify network connectivity

---

## 📝 Files Modified

| File | Changes |
|------|---------|
| [scripts/start-llm.sh](scripts/start-llm.sh) | Context 4096 → 8192 |
| [agents/context_manager.py](agents/context_manager.py) | NEW: Sliding window |
| [agents/router.py](agents/router.py) | Compact prompt, context limit |
| [agents/erp_agent.py](agents/erp_agent.py) | Compact prompt, context limit |
| [agents/crm_agent.py](agents/crm_agent.py) | Compact prompt, context limit |
| [agents/it_ops_agent.py](agents/it_ops_agent.py) | Compact prompt, context limit |
| [agents/oa_agent.py](agents/oa_agent.py) | Compact prompt, context limit |
| [agents/general_agent.py](agents/general_agent.py) | Compact prompt, context limit |
| [agents/utils.py](agents/utils.py) | Timeout 60→120s, retries |
| [services/observability.py](services/observability.py) | New context metrics |
