#!/usr/bin/env bash
# Start vLLM in daemon mode (background)
set -e

MODEL="Qwen/Qwen2.5-14B-Instruct"
PORT=8000
IMAGE="vllm/vllm-openai-rocm:v0.14.1"
CONTAINER_NAME="vllm-server"

echo "🚀 Starting vLLM in daemon mode"
echo "Model: ${MODEL}"
echo "Image: ${IMAGE}"
echo "Port: ${PORT}"
echo "ROCm: 7.2 native"
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

echo "📦 Starting container..."
docker run -d \
  --name ${CONTAINER_NAME} \
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
  ${IMAGE} \
  --model "${MODEL}" \
  --dtype float16 \
  --gpu-memory-utilization 0.92 \
  --max-model-len 8192 \
  --swap-space 16 \
  --enable-chunked-prefill \
  --trust-remote-code \
  --port ${PORT}

echo ""
echo "✅ Container started successfully"
echo ""
echo "📊 Monitoring startup (Ctrl+C to stop watching):"
echo "   docker logs -f ${CONTAINER_NAME}"
echo ""
echo "🔍 Check status:"
echo "   docker ps | grep ${CONTAINER_NAME}"
echo ""
echo "🛑 Stop container:"
echo "   docker stop ${CONTAINER_NAME}"
echo ""

# Wait and show logs
sleep 2
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Container logs (waiting for model to load...):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker logs -f ${CONTAINER_NAME}
