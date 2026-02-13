# llama.cpp Archive

This directory contains the previous llama.cpp-based LLM setup, archived on 2026-02-12.

## Why Archived

Replaced with vLLM for better multi-user support and OpenAI API compatibility.

## Previous Performance

- Model: Qwen2.5-14B-Q4_K_M quantized
- Backend: Vulkan on gfx1151
- Performance: 527 tok/s prompt, 24 tok/s generation
- Port: 8080

## Restore Instructions

If you need to restore llama.cpp:

```bash
# 1. Copy scripts back
cp docs/archive/llama-cpp/scripts/start-llm.sh scripts/
chmod +x scripts/start-llm.sh

# 2. Update activate.sh
sed -i 's|:8001/v1"|:8080/v1"|g' activate.sh

# 3. Stop vLLM
docker-compose stop vllm

# 4. Start llama.cpp
./scripts/start-llm.sh
```

## Archived Date

2026-02-12
