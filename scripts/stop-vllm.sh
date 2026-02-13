#!/usr/bin/env bash
# Stop vLLM gracefully

set -e

echo "🛑 Stopping vLLM service..."
docker-compose stop vllm

echo "✅ vLLM stopped"
