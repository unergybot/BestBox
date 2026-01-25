# Dual Model Architecture for BestBox

## Overview

BestBox uses a **tiered model architecture** for optimal performance:

```
┌─────────────────────────────────────────────────────┐
│  User Query                                         │
└─────────────┬───────────────────────────────────────┘
              │
              ▼
      ┌───────────────┐
      │ LIGHT MODEL   │  Qwen2.5-7B Q5_K_M
      │ Port: 8081    │  (Router, Classification)
      │ Docker ROCm   │  ~15-20 tok/s
      └───────┬───────┘
              │
              │ Routes to agent
              ▼
      ┌───────────────┐
      │ HEAVY MODEL   │  Qwen2.5-14B Q4_K_M
      │ Port: 8080    │  (Agent Reasoning, Tools)
      │ Native Vulkan │  ~24 tok/s
      └───────────────┘
```

## Model Allocation

### Heavy Model (8080) - Qwen2.5-14B Q4_K_M
- **Runtime**: Native Vulkan (`start-llm.sh`)
- **VRAM**: ~8-10GB
- **Context**: 8192 tokens
- **Use cases**:
  - ERP agent reasoning
  - CRM agent analysis
  - IT Ops diagnostics
  - OA document generation
  - Tool calling
  - RAG synthesis
  - Multi-step planning

### Light Model (8081) - Qwen2.5-7B Q5_K_M
- **Runtime**: Docker ROCm (`start-llm-docker.sh`)
- **VRAM**: ~6GB
- **Context**: 4096 tokens
- **Parallel**: 2 (faster throughput)
- **Use cases**:
  - **Router classification** ← Biggest win!
  - Intent detection
  - Quick yes/no answers
  - ASR text cleanup
  - Punctuation restoration
  - Simple summarization
  - Health check responses

## Routing Logic

### When to Use Light Model (8081)

```python
def should_use_light_model(task):
    """Determine if task can use the fast 7B model."""

    # Classification tasks
    if task.type in ["routing", "classification", "intent_detection"]:
        return True

    # ASR post-processing
    if task.type == "asr_cleanup":
        return True

    # Simple queries (< 50 tokens expected output)
    if task.estimated_output_tokens < 50:
        return True

    # Quick lookups
    if task.requires_tools is False and task.complexity == "low":
        return True

    return False
```

### When to Use Heavy Model (8080)

```python
def should_use_heavy_model(task):
    """Determine if task needs the powerful 14B model."""

    # Multi-step reasoning
    if task.requires_planning or task.steps > 1:
        return True

    # Tool calling
    if task.requires_tools:
        return True

    # Long-form generation
    if task.estimated_output_tokens > 100:
        return True

    # Domain expertise
    if task.domain in ["erp", "crm", "it_ops", "oa"]:
        return True

    return True  # Default to heavy for safety
```

## Setup Instructions

### 1. Download Light Model

```bash
# Download Qwen2.5-7B Q5_K_M
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF \
  qwen2.5-7b-instruct-q5_k_m.gguf \
  --local-dir ~/models/7b \
  --local-dir-use-symlinks False
```

### 2. Start Both Models

```bash
# Terminal 1: Heavy model (native Vulkan)
./scripts/start-llm.sh

# Terminal 2: Light model (Docker ROCm)
./scripts/start-llm-docker.sh
```

### 3. Verify Both Running

```bash
# Heavy model
curl http://localhost:8080/health

# Light model
curl http://localhost:8081/health
```

### 4. Update Agent Configuration

Edit `agents/utils.py` to support dual models:

```python
def get_llm(temperature=0.7, model_type="heavy"):
    """
    Get LLM client.

    Args:
        temperature: Sampling temperature
        model_type: "heavy" (8080) or "light" (8081)
    """
    port = 8080 if model_type == "heavy" else 8081

    llm = ChatOpenAI(
        base_url=f"http://localhost:{port}/v1",
        api_key="not-needed",
        model="qwen2.5",
        temperature=temperature,
        max_tokens=4096 if model_type == "light" else 8192,
    )
    return llm
```

### 5. Update Router to Use Light Model

Edit `agents/router.py:53`:

```python
def router_node(state: AgentState):
    """Route using the fast 7B model."""
    # Use light model for classification (3-5x faster!)
    llm = get_llm(temperature=0.1, model_type="light")

    structured_llm = llm.with_structured_output(RouteDecision)
    # ... rest of code
```

## Performance Comparison

### Before (Single 14B Model)

```
User Query → Router (14B, ~24 tok/s) → Agent (14B, ~24 tok/s)
Total latency: ~2-3 seconds routing + 5-10s reasoning = 7-13s
```

### After (Dual Models)

```
User Query → Router (7B, ~18 tok/s) → Agent (14B, ~24 tok/s)
Total latency: ~0.5-1s routing + 5-10s reasoning = 5.5-11s
```

**Improvement**: ~15-20% faster overall, router is 3x faster

## Resource Usage

### Expected VRAM

```
Heavy model (14B Q4_K_M):  ~8-10GB
Light model (7B Q5_K_M):   ~6GB
Total:                     ~14-16GB / 96GB available
Headroom:                  ~80GB for system/cache
```

### Expected RAM

```
Both models loaded:        ~20-25GB / 128GB total
OS + Services:             ~10GB
Available:                 ~90GB
```

## Monitoring

### Check Model Status

```bash
# Quick status
curl -s http://localhost:8080/health | jq .  # Heavy
curl -s http://localhost:8081/health | jq .  # Light

# GPU usage
rocm-smi
```

### Performance Benchmarking

```bash
# Benchmark light model (router simulation)
time curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5",
    "messages": [{"role": "user", "content": "Classify: show me top vendors"}],
    "max_tokens": 50
  }'

# Benchmark heavy model (agent simulation)
time curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5",
    "messages": [{"role": "user", "content": "Analyze Q1 procurement trends"}],
    "max_tokens": 500
  }'
```

## Troubleshooting

### Light Model Not Starting

```bash
# Check if port 8081 is free
sudo lsof -i :8081

# Check Docker logs
docker logs llm-server-light

# Verify model exists
ls -lh ~/models/7b/qwen2.5-7b-instruct-q5_k_m.gguf
```

### VRAM Exhaustion

```bash
# Check VRAM usage
rocm-smi --showmeminfo vram

# Reduce GPU layers if needed (edit scripts)
# Heavy: --n-gpu-layers 80 (instead of 999)
# Light: --n-gpu-layers 60 (instead of 99)
```

## Migration Path

### Phase 1: Parallel Testing (Current)
- Run both models
- Router still uses heavy model
- Test light model separately

### Phase 2: Router Migration
- Update `router.py` to use light model
- Monitor classification accuracy
- Rollback if issues

### Phase 3: Expand Light Model Usage
- ASR post-processing → light model
- Quick Q&A → light model
- Health checks → light model

### Phase 4: Optimization
- Tune context sizes
- Adjust GPU layers
- Benchmark and compare

## Expected Benefits

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Router latency | 2-3s | 0.5-1s | 3x faster |
| VRAM usage | 8-10GB | 14-16GB | More models |
| Throughput | ~24 tok/s | ~18-24 tok/s | Similar |
| Flexibility | Low | High | Multi-tier |

## Next Steps

1. Download 7B model
2. Start both servers
3. Test light model manually
4. Update router code
5. Monitor and compare
6. Expand light model usage

See also:
- [llm_backend_comparison.md](./llm_backend_comparison.md) - Backend comparison
- [../agents/router.py](../agents/router.py) - Router implementation
- [../agents/utils.py](../agents/utils.py) - LLM utilities
