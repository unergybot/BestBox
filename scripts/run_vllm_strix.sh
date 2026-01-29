#!/usr/bin/env bash
set -e

MODEL="Qwen/Qwen2.5-14B-Instruct"
PORT=8000
IMAGE="vllm/vllm-openai-rocm:v0.14.1"  # ROCm-specific image

echo "🚀 vLLM on Ryzen AI Max+ 395 (gfx1151)"
echo "Model: ${MODEL}"
echo "Image: ${IMAGE}"
echo "ROCm: 7.2 native"

docker run --rm -it \
  --network=host \
  --ipc=host \
  --group-add video \
  --cap-add SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --device /dev/kfd \
  --device /dev/dri \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  -e HIP_VISIBLE_DEVICES=0 \
  -e HSA_ENABLE_SDMA=1 \
  -e HSA_OVERRIDE_GFX_VERSION=11.0.0 \
  -e PYTORCH_ROCM_ARCH=gfx1100 \
  ${IMAGE} \
  --model "${MODEL}" \
  --dtype float16 \
  --gpu-memory-utilization 0.92 \
  --max-model-len 8192 \
  --swap-space 16 \
  --enable-chunked-prefill \
  --trust-remote-code \
  --port ${PORT}

