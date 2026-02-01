#!/bin/bash
# BestBox LLM Server Startup Script (CUDA)
# Intended for NVIDIA GPUs (e.g., RTX 3080)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration (override via environment variables)
LLAMA_SERVER_BIN="${LLM_SERVER_BIN:-}"
MODEL_PATH="${LLM_MODEL_PATH:-${HOME}/models/4b/Qwen3-4B-Instruct-Q4_K_M.gguf}"
PORT="${LLM_PORT:-8080}"
HOST="${LLM_HOST:-0.0.0.0}"
CONTEXT_SIZE="${LLM_CONTEXT_SIZE:-4096}"
GPU_LAYERS="${LLM_GPU_LAYERS:-999}"
LOG_FILE="${LLM_LOG_FILE:-${PROJECT_DIR}/llama-server.log}"

# Optional: pin to a specific CUDA device (useful for multi-GPU systems)
if [ -n "${LLM_CUDA_DEVICE:-}" ]; then
    export CUDA_VISIBLE_DEVICES="${LLM_CUDA_DEVICE}"
fi

# Resolve llama-server path
if [ -n "$LLAMA_SERVER_BIN" ]; then
    LLAMA_SERVER="$LLAMA_SERVER_BIN"
elif command -v llama-server >/dev/null 2>&1; then
    LLAMA_SERVER="$(command -v llama-server)"
elif [ -f "${PROJECT_DIR}/third_party/llama.cpp/build/bin/llama-server" ]; then
    LLAMA_SERVER="${PROJECT_DIR}/third_party/llama.cpp/build/bin/llama-server"
else
    echo "❌ llama-server not found. Set LLM_SERVER_BIN or install llama.cpp with CUDA support."
    exit 1
fi

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

# Verify model exists
if [[ ! -f "$MODEL_PATH" ]]; then
    echo "❌ Model not found at: $MODEL_PATH"
    echo "   Set LLM_MODEL_PATH to your GGUF model path"
    exit 1
fi

echo "🚀 Starting BestBox LLM Server (CUDA)"
echo "   Model: $(basename "$MODEL_PATH")"
echo "   Backend: CUDA"
echo "   Port: ${PORT}"
echo "   Context: ${CONTEXT_SIZE} tokens"
echo "   Log: ${LOG_FILE}"
if [ -n "${CUDA_VISIBLE_DEVICES:-}" ]; then
    echo "   CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES}"
fi
echo ""

nohup "$LLAMA_SERVER" \
    -m "$MODEL_PATH" \
    --port "$PORT" \
    --host "$HOST" \
    -c "$CONTEXT_SIZE" \
    --n-gpu-layers "$GPU_LAYERS" \
    > "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "   PID: ${SERVER_PID}"

echo ""
echo "⏳ Waiting for server to initialize..."
for i in {1..30}; do
    if curl -s "http://${HOST}:${PORT}/health" > /dev/null 2>&1; then
        echo "✅ Server is ready!"
        echo ""
        echo "🔗 API Endpoint: http://${HOST}:${PORT}/v1/chat/completions"
        echo "🔗 Health Check: http://${HOST}:${PORT}/health"
        exit 0
    fi
    sleep 1
done

echo "❌ Server failed to start. Check log: ${LOG_FILE}"
tail -20 "$LOG_FILE"
exit 1
