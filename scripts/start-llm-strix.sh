#!/bin/bash
# BestBox LLM Server Startup Script for Strix Halo (ROCm)
# Optimized for AMD Ryzen AI Max+ 395 (gfx1103)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
LLAMA_SERVER="${PROJECT_DIR}/third_party/llama.cpp/build/bin/llama-server"
# Default to Qwen3-30B MoE as recommended in docs
MODEL_PATH="${HOME}/models/30b/Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf"
PORT=8080
HOST="0.0.0.0"
CONTEXT_SIZE=8192
GPU_LAYERS=999
LOG_FILE="${PROJECT_DIR}/llama-server-strix.log"

# ROCm / SMX Optimization
export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
export GGML_CUDA_FORCE_MMQ=1
# HSA_OVERRIDE_GFX_VERSION is usually required for newer chips not yet in stable ROCm
# For Strix Halo (Radeon 8060S), the ISA is gfx1151
export HSA_OVERRIDE_GFX_VERSION=11.5.1

# Check if already running
if pgrep -f "llama-server.*${PORT}" > /dev/null; then
    echo "⚠️  llama-server already running on port ${PORT}"
    if [[ "$1" == "--restart" ]]; then
        echo "   Stopping existing server..."
        pkill -f "llama-server.*${PORT}" || true
        sleep 2
    else
        exit 0
    fi
fi

# Verify binary exists
if [[ ! -f "$LLAMA_SERVER" ]]; then
    # Check if pre-built exists in standard location if build fails
    if [[ -f "/usr/local/bin/llama-server" ]]; then
        LLAMA_SERVER="/usr/local/bin/llama-server"
    else
        echo "❌ llama-server not found. Please run scripts/setup-rocm-llm.sh first."
        exit 1
    fi
fi

# Verify model exists
if [[ ! -f "$MODEL_PATH" ]]; then
    echo "❌ Model not found at: $MODEL_PATH"
    echo "   Please download the model first: huggingface-cli download Qwen/Qwen3-30B-A3B-Instruct-2507-GGUF --local-dir ~/models/30b"
    exit 1
fi

echo "🚀 Starting BestBox LLM Server (ROCm Optimized)"
echo "   Hardware: AMD Ryzen AI Max+ 395 (Strix Halo)"
echo "   Model: $(basename $MODEL_PATH)"
echo "   Unified Memory: Enabled"
echo "   Port: ${PORT}"
echo ""

nohup "$LLAMA_SERVER" \
    -m "$MODEL_PATH" \
    --port "$PORT" \
    --host "$HOST" \
    -c "$CONTEXT_SIZE" \
    --n-gpu-layers "$GPU_LAYERS" \
    --fa \
    > "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "   PID: ${SERVER_PID}"

# Health check
echo "⏳ Waiting for server to initialize..."
for i in {1..60}; do
    if curl -s "http://${HOST}:${PORT}/health" > /dev/null 2>&1; then
        echo "✅ LLM Server (Strix Halo) is ready!"
        exit 0
    fi
    sleep 2
done

echo "❌ Server failed to start. Check log: ${LOG_FILE}"
tail -20 "$LOG_FILE"
exit 1
