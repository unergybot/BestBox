# vLLM + Qwen3-14B Benchmark Guide

## Quick Start

### 1. Start vLLM Server

```bash
cd ~/BestBox
./scripts/run_vllm_strix.sh
```

Wait for the message: `"Application startup complete"`

### 2. Run Benchmark (Option A - Automated)

In a **new terminal**:

```bash
cd ~/BestBox
source activate.sh
python scripts/benchmark_vllm.py
```

This will test:
- ✅ Short prompts (100 tokens)
- ✅ Medium prompts (300 tokens)
- ✅ Long prompts (800 tokens)
- ✅ Code generation (500 tokens)
- ✅ Streaming performance (TTFT)

Results saved to `benchmark_results_YYYYMMDD_HHMMSS.json`

### 3. Monitor in Real-time (Option B - Manual Testing)

```bash
./scripts/monitor_vllm.sh
```

Shows live GPU usage, memory, and vLLM metrics while you run requests.

## Manual Testing

### Test 1: Simple Completion

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-14B-Instruct",
    "messages": [{"role": "user", "content": "Explain quantum computing"}],
    "max_tokens": 200
  }' | jq
```

### Test 2: Streaming Response

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-14B-Instruct",
    "messages": [{"role": "user", "content": "Write a Python function for quicksort"}],
    "max_tokens": 300,
    "stream": true
  }'
```

### Test 3: Check Model Info

```bash
curl http://localhost:8000/v1/models | jq
```

## Key Metrics to Watch

### Throughput
- **Tokens/second**: Higher is better
- Expected range: 15-30 tok/s (generation) on gfx1151
- Depends on: context length, batch size, quantization

### Latency
- **TTFT (Time To First Token)**: Lower is better
- Expected: 100-500ms for typical prompts
- **Time per token**: Lower is better
- Expected: 30-60ms/token

### Resource Usage
- **GPU VRAM**: Should be < 16GB for Q4 quantized model
- **GPU Utilization**: Should be 80-100% during generation
- **System RAM**: Model cached in system RAM (~10-12GB)

## Comparing with llama.cpp

Your current llama.cpp setup (from CLAUDE.md):
- Qwen2.5-14B-Instruct-Q4_K_M
- ~527 tok/s prompt processing
- ~24 tok/s generation

vLLM typically offers:
- Better batching (multiple requests)
- Continuous batching (dynamic scheduling)
- PagedAttention (efficient memory)
- Faster for concurrent users

## Troubleshooting

### vLLM won't start

```bash
# Check Docker logs
docker logs -f <container_name>

# Verify ROCm
rocm-smi

# Check GPU visibility
echo $HIP_VISIBLE_DEVICES
```

### Low performance

1. Check GPU utilization: `rocm-smi --showuse`
2. Verify quantization: Model should be FP16 or quantized
3. Check batch size: `--max-model-len 8192` in run script
4. Monitor temperature: `rocm-smi --showtemp`

### Out of memory

Reduce in `scripts/run_vllm_strix.sh`:
- `--gpu-memory-utilization 0.92` → `0.85`
- `--max-model-len 8192` → `4096`

## Expected Performance (gfx1151)

Based on AMD Ryzen AI Max+ 395:

| Metric | Expected Value |
|--------|---------------|
| Throughput (gen) | 15-30 tok/s |
| Throughput (prompt) | 200-500 tok/s |
| TTFT | 100-500ms |
| VRAM Usage | 8-14GB |
| Max Context | 8192 tokens |
| Concurrent Requests | 2-4 optimal |

## Integration with BestBox

To use vLLM with your agents, update `services/agent_api.py`:

```python
# Change from llama.cpp endpoint
LLM_BASE_URL = "http://localhost:8000/v1"  # vLLM OpenAI-compatible

# Model name
MODEL_NAME = "Qwen/Qwen3-14B-Instruct"
```

vLLM is fully OpenAI API compatible, so your existing code should work!

## References

- vLLM Docs: https://docs.vllm.ai
- ROCm Support: https://rocm.docs.amd.com
- Qwen3 Model Card: https://huggingface.co/Qwen/Qwen3-14B-Instruct
