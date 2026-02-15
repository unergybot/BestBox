#!/bin/bash
# DEPRECATED: Use ./start-all-services.sh instead.

echo "⚠️  DEPRECATED: scripts/start-embeddings.sh is deprecated"
echo "   Use: ./start-all-services.sh"
echo ""

# Start BGE-M3 Embeddings Service
# API endpoint: http://127.0.0.1:8081

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment
source "${PROJECT_DIR}/venv/bin/activate"

# Unset proxy variables to ensure local services communicate directly
unset http_proxy https_proxy ftp_proxy all_proxy no_proxy
unset HTTP_PROXY HTTPS_PROXY FTP_PROXY ALL_PROXY NO_PROXY

# Check if already running
if pgrep -f "uvicorn.*8081" > /dev/null; then
    echo "⚠️  Embeddings service already running on port 8081"
    exit 1
fi

echo "🚀 Starting BGE-M3 Embeddings Service"
echo "   Model: BAAI/bge-m3"
echo "   Device: ${EMBEDDINGS_DEVICE:-auto}"
echo "   Port: 8081"
echo ""

# Prefer running embeddings on the P100 (GPU 0) on multi-GPU machines.
# This prevents OOM when the RTX 3080 is already consumed by vLLM.
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_COUNT=$(nvidia-smi -L 2>/dev/null | wc -l | tr -d ' ')
    if [ "${GPU_COUNT:-0}" -ge 1 ]; then
        export CUDA_VISIBLE_DEVICES="${EMBEDDINGS_CUDA_VISIBLE_DEVICES:-0}"
        export EMBEDDINGS_DEVICE="${EMBEDDINGS_DEVICE:-cuda:0}"
    fi
fi

cd "${PROJECT_DIR}/services/embeddings"

# Install dependencies if needed
pip install -q fastapi uvicorn sentence-transformers

# Start the service
nohup uvicorn main:app --host 0.0.0.0 --port 8081 > embeddings.log 2>&1 &

echo "⏳ Waiting for model to load (this may take 30-60 seconds)..."
sleep 10

for i in {1..60}; do
    if curl -s "http://127.0.0.1:8081/health" | grep -q '"status":"ok"'; then
        echo "✅ Embeddings service ready!"
        echo "🔗 API Endpoint: http://127.0.0.1:8081/embed"
        exit 0
    fi
    sleep 2
done

echo "❌ Service failed to start. Check logs: embeddings.log"
tail -20 embeddings.log
exit 1
