#!/bin/bash
# Start LangGraph Agent API
# Endpoint: http://127.0.0.1:8000

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment
source "${PROJECT_DIR}/venv/bin/activate"

# Unset proxy variables to ensure local services communicate directly
# This prevents issues with ChatOpenAI/httpx trying to use SOCKS proxies
unset http_proxy https_proxy ftp_proxy all_proxy no_proxy
unset HTTP_PROXY HTTPS_PROXY FTP_PROXY ALL_PROXY NO_PROXY

# Check if already running
if pgrep -f "uvicorn.*8000" > /dev/null; then
    echo "⚠️  Agent API already running on port 8000"
    exit 1
fi

echo "🚀 Starting LangGraph Agent API"
echo "   Port: 8000"
echo ""

# Set LLM Base URL (vLLM is on port 8001)
export LLM_BASE_URL="${LLM_BASE_URL:-http://127.0.0.1:8001/v1}"
export LLM_MODEL="Qwen/Qwen3-4B-Instruct-2507"

cd "${PROJECT_DIR}"

# Start the service
nohup python services/agent_api.py > agent_api.log 2>&1 &

echo "⏳ Waiting for API to confirm startup..."
sleep 5

if curl -s "http://127.0.0.1:8000/health" | grep -q '"status":"ok"'; then
    echo "✅ Agent API ready!"
    echo "🔗 Endpoint: http://127.0.0.1:8000/v1/chat/completions"
    exit 0
fi

echo "❌ Service failed to start. Check logs: agent_api.log"
tail -20 agent_api.log
exit 1
