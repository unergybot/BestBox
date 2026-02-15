#!/bin/bash
# BestBox Unified Service Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -z "${BESTBOX_GPU_BACKEND:-}" ]; then
  source "$SCRIPT_DIR/scripts/detect-gpu.sh"
  GPU_BACKEND="$(detect_gpu)"
  export BESTBOX_GPU_BACKEND="$GPU_BACKEND"
else
  GPU_BACKEND="$BESTBOX_GPU_BACKEND"
fi

BASE_COMPOSE="-f docker-compose.yml"
GPU_COMPOSE="-f docker-compose.${GPU_BACKEND}.yml"
mkdir -p logs .bestbox

echo -e "${GREEN}🚀 Starting BestBox services (${GPU_BACKEND} mode)${NC}"

echo -e "${GREEN}📦 Starting infrastructure services...${NC}"
docker compose $BASE_COMPOSE up -d qdrant postgres redis livekit mariadb erpnext otel-collector jaeger prometheus grafana docling-serve authelia gatus

if [ "$GPU_BACKEND" != "cpu" ]; then
  echo -e "${GREEN}🎮 Starting GPU services...${NC}"
  docker compose $BASE_COMPOSE $GPU_COMPOSE up -d vllm embeddings reranker
else
  echo -e "${YELLOW}⚠️  CPU mode selected: skipping GPU services${NC}"
fi

if [ "${BESTBOX_ENABLE_SPEECH:-false}" = "true" ]; then
  if [ "$GPU_BACKEND" = "cpu" ]; then
    echo -e "${YELLOW}⚠️  Speech services require GPU overlay; skipping in CPU mode${NC}"
  else
    echo -e "${GREEN}🎤 Starting speech services...${NC}"
    docker compose $BASE_COMPOSE $GPU_COMPOSE up -d qwen3-asr qwen3-tts s2s-gateway
  fi
fi

echo -e "${GREEN}🤖 Starting Agent API...${NC}"
if [ -z "${VIRTUAL_ENV:-}" ]; then
  source "$SCRIPT_DIR/activate.sh"
fi
if [ -f logs/agent_api.pid ] && ps -p "$(cat logs/agent_api.pid)" >/dev/null 2>&1; then
  kill "$(cat logs/agent_api.pid)" || true
fi
nohup python services/agent_api.py > logs/agent_api.log 2>&1 &
echo $! > logs/agent_api.pid

if [ "${BESTBOX_ENABLE_FRONTEND:-true}" = "true" ]; then
  echo -e "${GREEN}🌐 Starting frontend...${NC}"
  if [ -f logs/frontend.pid ] && ps -p "$(cat logs/frontend.pid)" >/dev/null 2>&1; then
    kill "$(cat logs/frontend.pid)" || true
  fi
  cd frontend/copilot-demo
  nohup npm run dev > ../../logs/frontend.log 2>&1 &
  echo $! > ../../logs/frontend.pid
  cd "$SCRIPT_DIR"
fi

echo
echo -e "${GREEN}✅ BestBox services started${NC}"
echo "  Agent API:  http://localhost:8000"
[ "$GPU_BACKEND" != "cpu" ] && echo "  LLM:        http://localhost:8001"
[ "$GPU_BACKEND" != "cpu" ] && echo "  Embeddings: http://localhost:8081"
[ "$GPU_BACKEND" != "cpu" ] && echo "  Reranker:   http://localhost:8082"
[ "${BESTBOX_ENABLE_FRONTEND:-true}" = "true" ] && echo "  Frontend:   http://localhost:3000"
[ "${BESTBOX_ENABLE_SPEECH:-false}" = "true" ] && echo "  S2S:        ws://localhost:8765"
