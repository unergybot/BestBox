#!/bin/bash
# BestBox LLM Server Startup Script (Docker ROCm Edition)
# Using llama.cpp with HIP/ROCm backend for AMD Strix Halo (gfx1151)
#
# This script builds and runs the llama.cpp Docker container with ROCm support.
# For native Vulkan version, use: ./start-llm.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LLAMA_SOURCE="${PROJECT_DIR}/third_party/llama.cpp"

# Configuration - LIGHT MODEL for fast tasks (routing, classification, ASR)
PORT=8081  # Different port from heavy model (8080)
HOST="0.0.0.0"
MODEL_PATH="/app/models/qwen2.5-7b-instruct-q5_k_m.gguf"
MODEL_DIR="${HOME}/models/7b"
MODEL_NAME="qwen2.5-7b-instruct-q5_k_m.gguf"

# Check if llama.cpp source exists
if [[ ! -d "$LLAMA_SOURCE" ]]; then
    echo "❌ llama.cpp source not found at: $LLAMA_SOURCE"
    exit 1
fi

echo "🚀 Starting BestBox LIGHT Model Server (Docker ROCm Edition)"
echo "   Model: Qwen2.5-7B (Fast routing & classification)"
echo "   Backend: HIP/ROCm"
echo "   Port: ${PORT} (Heavy model on 8080)"
echo "   Building Docker image (this may take a while first time)..."

# Build Docker image (skip if already exists, use --no-cache to force rebuild)
if ! docker image inspect llama-strix &>/dev/null; then
    docker build -t llama-strix -f "${LLAMA_SOURCE}/.devops/rocm.Dockerfile" --target server "$LLAMA_SOURCE"
else
    echo "   Image already exists. To rebuild: docker rmi llama-strix && ./start-llm-docker.sh"
fi

# Check if container is running or exists
if docker ps -a | grep -q "llm-server-light"; then
    echo "⚠️  llm-server-light container already exists. Stopping/Removing..."
    docker rm -f llm-server-light
fi

echo "   Starting container..."

# Run Docker container
# --device /dev/kfd --device /dev/dri are crucial for ROCm
docker run -d \
    --name llm-server-light \
    --restart unless-stopped \
    --device /dev/kfd \
    --device /dev/dri \
    --group-add video \
    --ipc=host \
    -e HSA_OVERRIDE_GFX_VERSION=11.5.0 \
    -v "${MODEL_DIR}:/app/models" \
    -p "${PORT}:8080" \
    llama-strix \
    --model "$MODEL_PATH" \
    --host 0.0.0.0 \
    --port 8080 \
    --n-gpu-layers 99 \
    --ctx-size 4096 \
    --no-direct-io \
    --mmap \
    --parallel 2

echo "   Container 'llm-server-light' started."
echo "   Logs:"
docker logs -f llm-server-light &

# Wait for server to initialize
echo "⏳ Waiting for llama.cpp to initialize..."
for i in {1..60}; do
    if curl -s "http://${HOST}:${PORT}/health" | grep -q '{"status":"ok"}' > /dev/null 2>&1; then
        echo "✅ llama.cpp Server is ready!"
        echo "🔗 API Endpoint: http://${HOST}:${PORT}/v1/chat/completions"
        exit 0
    fi
    sleep 2
done

echo "⚠️  Server taking long to start. Check logs explicitly."
exit 0
