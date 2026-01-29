#!/usr/bin/env bash
# Start vLLM with AITER (AMD Inference Throughput Enhancement Runtime)
# Based on: https://rocm.blogs.amd.com/software-tools-optimization/vllm-omni/README.html

set -e

MODEL="Qwen/Qwen2.5-14B-Instruct"
PORT=8000
IMAGE="vllm/vllm-openai-rocm:v0.14.0"  # Stable version from AMD blog
CONTAINER_NAME="vllm-aiter"

echo "🚀 Starting vLLM with AITER Optimizations"
echo "=========================================="
echo "Model: ${MODEL}"
echo "Image: ${IMAGE} (stable release)"
echo "Port: ${PORT}"
echo ""
echo "⚡ AITER Features:"
echo "   - AMD's optimized inference kernels"
echo "   - Assembly-optimized Paged Attention"
echo "   - FP8 fast paths"
echo "   - Fused sampling operations"
echo ""
echo "🎯 Expected speedup: 2-5x vs standard vLLM"
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

# Pull stable image if not present
echo "📥 Ensuring stable image is available..."
docker pull ${IMAGE}

echo ""
echo "📦 Starting AITER-enabled container..."
echo ""

docker run -d \
  --name ${CONTAINER_NAME} \
  --ipc=host \
  --group-add video \
  --cap-add SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --device /dev/kfd \
  --device /dev/dri \
  -p ${PORT}:${PORT} \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  -e VLLM_ROCM_USE_AITER=1 \
  -e HIP_VISIBLE_DEVICES=0 \
  ${IMAGE} \
  --model "${MODEL}" \
  --dtype float16 \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --enable-chunked-prefill \
  --trust-remote-code \
  --port ${PORT}

echo ""
echo "✅ Container started successfully"
echo ""
echo "📊 Monitor startup (Ctrl+C to stop watching):"
echo "   docker logs -f ${CONTAINER_NAME}"
echo ""
echo "🔍 Check status:"
echo "   docker ps | grep ${CONTAINER_NAME}"
echo ""
echo "🛑 Stop container:"
echo "   docker stop ${CONTAINER_NAME}"
echo ""
echo "📈 Run benchmark after startup:"
echo "   python scripts/benchmark_vllm.py"
echo ""
echo "⏳ Waiting for model to load (~2 minutes)..."
echo ""

# Wait and show logs
sleep 3
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Startup logs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker logs -f ${CONTAINER_NAME}
