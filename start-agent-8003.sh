#!/bin/bash
cd /home/apexai/BestBox
source venv/bin/activate
export AGENT_API_PORT=8003
# Only export specific vars we need
export LLM_BASE_URL=$(grep '^LLM_BASE_URL=' .env | cut -d= -f2-)
export EMBEDDINGS_URL=$(grep '^EMBEDDINGS_URL=' .env | cut -d= -f2-)
export QDRANT_HOST=$(grep '^QDRANT_HOST=' .env | cut -d= -f2-)
export QDRANT_PORT=$(grep '^QDRANT_PORT=' .env | cut -d= -f2-)
nohup python services/agent_api.py > agent_api_8003.log 2>&1 &
echo $! > /tmp/agent_api_8003.pid
echo "Started Agent API on port 8003 (PID: $!)"
sleep 3
curl -s http://localhost:8003/health
