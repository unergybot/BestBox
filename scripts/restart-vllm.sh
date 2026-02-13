#!/usr/bin/env bash
# Restart vLLM with health check

set -e

echo "🔄 Restarting vLLM service..."
docker-compose restart vllm

echo "⏳ Waiting for health check..."
sleep 10

if curl -sf http://localhost:8001/health > /dev/null; then
    echo "✅ vLLM healthy"
else
    echo "⚠️  vLLM health check failed"
    echo "Check logs: docker-compose logs vllm"
    exit 1
fi
