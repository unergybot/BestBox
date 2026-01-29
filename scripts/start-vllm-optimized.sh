#!/bin/bash

# BestBox vLLM ROCm Launcher for Strix Halo (gfx1151)
# Optimized for Performance

# 1. Hardware Masquerading
# Strix Halo (gfx1151) is RDNA 3.5. We impersonate RDNA 3 (gfx1100) 
# because it has mature support in current vLLM/ROCm builds.
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100

# 2. Performance Tuning
# Enable system memory fallback if VRAM is tight (Strix has shared memory, so this is natural)
export HSA_ENABLE_SDMA=0 

# 3. Model Configuration
# Use a modern model. You mentioned Qwen2.5-14B in your issue report.
MODEL="Qwen/Qwen2.5-14B-Instruct"

echo "🚀 Starting vLLM on AMD Strix Halo (gfx1151 as gfx1100)..."
echo "Model: $MODEL"
echo "ROCm Version: Using container default (likely 6.x/7.x)"

# 4. Docker Command
# We use the 'latest' official image to avoid the bugs in v0.14.0
docker run -it \
    --network=host \
    --group-add=video \
    --ipc=host \
    --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined \
    --device /dev/kfd \
    --device /dri \
    -v $HOME/.cache/huggingface:/root/.cache/huggingface \
    -e HSA_OVERRIDE_GFX_VERSION=11.0.0 \
    -e ROCM_PATH=/opt/rocm \
    vllm/vllm-openai:latest \
    --model $MODEL \
    --dtype float16 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 8192 \
    --trust-remote-code
