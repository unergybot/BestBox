#!/usr/bin/env bash
# Emergency rollback to llama.cpp

set -e

echo "🚨 Emergency Rollback to llama.cpp"
echo "===================================="

# 1. Stop vLLM
docker-compose stop vllm
echo "✅ vLLM stopped"

# 2. Restore llama.cpp scripts
cp docs/archive/llama-cpp/scripts/start-llm.sh scripts/
chmod +x scripts/start-llm.sh
echo "✅ llama.cpp scripts restored"

# 3. Update environment
sed -i 's|LLM_BASE_URL="http://localhost:8001/v1"|LLM_BASE_URL="http://localhost:8080/v1"|g' activate.sh
source activate.sh
echo "✅ Environment updated"

# 4. Start llama.cpp
./scripts/start-llm.sh &
sleep 10
echo "✅ llama.cpp starting"

# 5. Verify
if curl -sf http://localhost:8080/v1/models > /dev/null; then
    echo "✅ llama.cpp operational"
else
    echo "⚠️  llama.cpp health check failed"
fi

# 6. Restart Agent API
pkill -f agent_api || true
./scripts/start-agent-api.sh &
sleep 5
echo "✅ Agent API restarted"

# 7. Test end-to-end
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ System operational"
else
    echo "⚠️  System health check failed"
fi

echo ""
echo "✅ Rollback complete"
echo "System is running on llama.cpp again"
echo ""
echo "To investigate vLLM issues:"
echo "  docker-compose logs vllm > vllm-failure.log"
