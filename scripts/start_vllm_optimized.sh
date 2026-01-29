#!/usr/bin/env bash
# Start vLLM with AMD's official ROCm recommendations
# Based on: https://rocm.docs.amd.com/en/latest/how-to/rocm-for-ai/inference/benchmark-docker/vllm.html

set -e

MODEL="Qwen/Qwen2.5-14B-Instruct"
PORT=8000
IMAGE="vllm/vllm-openai-rocm:v0.14.1"
CONTAINER_NAME="vllm-server-optimized"

echo "🚀 Starting vLLM with AMD ROCm Optimizations"
echo "=============================================="
echo "Model: ${MODEL}"
echo "Image: ${IMAGE}"
echo "Port: ${PORT}"
echo ""
echo "⚙️  Optimizations applied:"
echo "   - Shared memory: 16GB (AMD recommendation)"
echo "   - Max batched tokens: 32768 (increased from 8192)"
echo "   - Max sequences: 512"
echo "   - Relaxed security options"
echo ""

# Check if container already running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "⚠️  Container '${CONTAINER_NAME}' already running"
    echo "Stop it with: docker stop ${CONTAINER_NAME}"
    exit 1
fi

# Remove old container if exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "🧹 Removing old container..."
    docker rm -f ${CONTAINER_NAME}
fi

echo "📦 Starting optimized container..."
echo ""

docker run -d \
  --name ${CONTAINER_NAME} \
  --network=host \
  --ipc=host \
  --shm-size 16G \
  --group-add video \
  --cap-add SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \
  --device /dev/kfd \
  --device /dev/dri \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  -e HIP_VISIBLE_DEVICES=0 \
  -e HSA_ENABLE_SDMA=1 \
  -e HSA_OVERRIDE_GFX_VERSION=11.0.0 \
  -e PYTORCH_ROCM_ARCH=gfx1100 \
  -e HUGGINGFACE_HUB_CACHE=/root/.cache/huggingface \
  ${IMAGE} \
  --model "${MODEL}" \
  --dtype float16 \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --max-num-batched-tokens 32768 \
  --max-num-seqs 512 \
  --swap-space 16 \
  --enable-chunked-prefill \
  --trust-remote-code \
  --disable-log-requests \
  --port ${PORT}

echo ""
echo "✅ Container started successfully"
echo ""
echo "📊 Monitor startup:"
echo "   docker logs -f ${CONTAINER_NAME}"
echo ""
echo "🔍 Check status:"
echo "   docker ps | grep ${CONTAINER_NAME}"
echo ""
echo "🛑 Stop container:"
echo "   docker stop ${CONTAINER_NAME}"
echo ""
echo "⏳ Waiting for model to load (this takes ~2 minutes)..."
echo ""

# Wait and show logs
sleep 3
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker logs -f ${CONTAINER_NAME}
