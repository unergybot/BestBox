#!/usr/bin/env bash
# DEPRECATED: Use ./start-all-services.sh instead.

echo "⚠️  DEPRECATED: scripts/start-vllm.sh is deprecated"
echo "   Use: ./start-all-services.sh"
echo ""

# Start vLLM with ROCm for Qwen3-30B
# Port: 8001 (avoids conflict with Agent API on 8000)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting vLLM with Qwen3-30B-A3B-Instruct-2507"
echo "=================================================="
echo "Backend: ROCm 7.2 (gfx1151)"
echo "Port: 8001"
echo "Profile: Stability-First (enforce-eager)"
echo ""

# Load environment
if [ -f "$PROJECT_ROOT/.env.vllm" ]; then
    set -a
    source "$PROJECT_ROOT/.env.vllm"
    set +a
fi

# Check if container already running
if docker ps --format '{{.Names}}' | grep -q "^vllm-server$"; then
    echo "⚠️  vLLM container already running"
    echo "Stop it with: docker compose stop vllm"
    exit 1
fi

# Start vLLM service
cd "$PROJECT_ROOT"
docker compose up -d vllm

echo ""
echo "⏳ Waiting for model to load (this takes ~2-3 minutes)..."
echo ""
echo "📊 Monitor startup:"
echo "   docker compose logs -f vllm"
echo ""
echo "🔍 Check health:"
echo "   curl http://localhost:8001/health"
echo ""
echo "🛑 Stop service:"
echo "   docker compose stop vllm"
echo ""

# Wait and show initial logs
sleep 5
docker compose logs --tail=50 vllm
