#!/bin/bash
# Start BGE-reranker-base Service for RAG precision boosting
# API endpoint: http://127.0.0.1:8082

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment
source "${PROJECT_DIR}/venv/bin/activate"

# Check if already running
if pgrep -f "uvicorn.*8082" > /dev/null; then
    echo "⚠️  Reranker service already running on port 8082"
    exit 1
fi

echo "🚀 Starting BGE-reranker-base Service"
echo "   Model: BAAI/bge-reranker-base"
echo "   Port: 8082"
echo ""

cd "${PROJECT_DIR}/services/rag_pipeline"

# Install dependencies if needed
pip install -q fastapi uvicorn sentence-transformers

# Start the service
nohup python reranker.py > reranker.log 2>&1 &

echo "⏳ Waiting for model to load (this may take 30-60 seconds)..."
sleep 10

for i in {1..60}; do
    if curl -s "http://127.0.0.1:8082/health" | grep -q '"status":"ok"'; then
        echo "✅ Reranker service ready!"
        echo "🔗 API Endpoint: http://127.0.0.1:8082/rerank"
        exit 0
    fi
    sleep 2
done

echo "❌ Service failed to start. Check logs: services/rag_pipeline/reranker.log"
tail -20 "${PROJECT_DIR}/services/rag_pipeline/reranker.log"
exit 1
