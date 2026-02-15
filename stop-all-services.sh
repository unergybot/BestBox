#!/bin/bash
# BestBox Unified Service Stop Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}🛑 Stopping BestBox services...${NC}"

if [ -f logs/agent_api.pid ]; then
  PID="$(cat logs/agent_api.pid)"
  if ps -p "$PID" >/dev/null 2>&1; then
    kill "$PID" || true
  fi
  rm -f logs/agent_api.pid
fi

if [ -f logs/frontend.pid ]; then
  PID="$(cat logs/frontend.pid)"
  if ps -p "$PID" >/dev/null 2>&1; then
    kill "$PID" || true
  fi
  rm -f logs/frontend.pid
fi

if [ -z "${BESTBOX_GPU_BACKEND:-}" ]; then
  source "$SCRIPT_DIR/scripts/detect-gpu.sh"
  GPU_BACKEND="$(detect_gpu)"
else
  GPU_BACKEND="$BESTBOX_GPU_BACKEND"
fi

docker compose -f docker-compose.yml -f "docker-compose.${GPU_BACKEND}.yml" down || docker compose -f docker-compose.yml down

echo -e "${GREEN}✅ BestBox services stopped${NC}"
