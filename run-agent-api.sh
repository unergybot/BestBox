#!/bin/bash
# Run BestBox Agent API persistently
cd /home/apexai/BestBox
source venv/bin/activate
export AGENT_API_PORT=8003
export LLM_BASE_URL=http://127.0.0.1:8001/v1
export QDRANT_HOST=localhost
export QDRANT_PORT=6333

# Run
exec python services/agent_api.py
