#!/bin/bash
# Restart script for BestBox Agent API

echo "🔄 Restarting Agent API..."

# 1. Kill existing process
pkill -f 'services/agent_api.py' && echo "✅ Stopped existing server" || echo "ℹ️ No server was running"

# 2. Start again using the start script
bash scripts/start-agent-api.sh
