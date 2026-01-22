#!/bin/bash
# BestBox LLM Server Startup Script
# Using Vulkan backend for AMD Radeon 8060S (gfx1151)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
LLAMA_SERVER="${PROJECT_DIR}/third_party/llama.cpp/build/bin/llama-server"
MODEL_PATH="${HOME}/models/14b/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
PORT=8080
HOST="127.0.0.1"
CONTEXT_SIZE=4096
GPU_LAYERS=999
LOG_FILE="${PROJECT_DIR}/llama-server.log"

# Check if already running
if pgrep -f "llama-server.*${PORT}" > /dev/null; then
    echo "⚠️  llama-server already running on port ${PORT}"
    echo "   To restart, run: $0 --restart"
    if [[ "$1" == "--restart" ]]; then
        echo "   Stopping existing server..."
        pkill -f "llama-server.*${PORT}" || true
        sleep 2
    else
        exit 1
    fi
fi

# Verify binary exists
if [[ ! -f "$LLAMA_SERVER" ]]; then
    echo "❌ llama-server not found at: $LLAMA_SERVER"
    echo "   Please build llama.cpp first"
    exit 1
fi

# Verify model exists
if [[ ! -f "$MODEL_PATH" ]]; then
    echo "❌ Model not found at: $MODEL_PATH"
    exit 1
fi

echo "🚀 Starting BestBox LLM Server (Vulkan)"
echo "   Model: $(basename $MODEL_PATH)"
echo "   Backend: Vulkan (AMD Radeon 8060S)"
echo "   Port: ${PORT}"
echo "   Context: ${CONTEXT_SIZE} tokens"
echo "   Log: ${LOG_FILE}"
echo ""

# Start server with Vulkan backend
# Note: --no-direct-io --mmap required for gfx1151 compatibility
nohup "$LLAMA_SERVER" \
    -m "$MODEL_PATH" \
    --port "$PORT" \
    --host "$HOST" \
    -c "$CONTEXT_SIZE" \
    --n-gpu-layers "$GPU_LAYERS" \
    --no-direct-io \
    --mmap \
    > "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "   PID: ${SERVER_PID}"

# Wait for server to initialize
echo ""
echo "⏳ Waiting for server to initialize..."
for i in {1..30}; do
    if curl -s "http://${HOST}:${PORT}/health" > /dev/null 2>&1; then
        echo "✅ Server is ready!"
        echo ""
        echo "🔗 API Endpoint: http://${HOST}:${PORT}/v1/chat/completions"
        echo "🔗 Health Check: http://${HOST}:${PORT}/health"
        echo ""
        echo "📊 Benchmark Results (Vulkan on gfx1151):"
        echo "   - pp512: ~527 tok/s (prompt processing)"
        echo "   - tg128: ~24 tok/s (text generation)"
        echo "   - ~2.5x faster than CPU baseline"
        exit 0
    fi
    sleep 1
done

echo "❌ Server failed to start. Check log: ${LOG_FILE}"
tail -20 "$LOG_FILE"
exit 1
