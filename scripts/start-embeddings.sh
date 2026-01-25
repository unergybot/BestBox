#!/bin/bash
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
echo "   Port: 8081"
echo ""

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
