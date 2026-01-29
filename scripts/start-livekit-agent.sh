#!/bin/bash
# BestBox LiveKit Voice Agent Startup Script
#
# This script starts the LiveKit-based voice agent for BestBox.
# It provides lower latency than the custom WebSocket S2S implementation.
#
# Prerequisites:
#   1. LiveKit server running (livekit-server --dev)
#   2. Local LLM running (scripts/start-llm.sh)
#   3. Python dependencies installed
#
# Usage:
#   ./scripts/start-livekit-agent.sh [dev|connect|join]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   BestBox LiveKit Voice Agent${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check virtual environment
if [[ -n "$VIRTUAL_ENV" ]]; then
    echo -e "${GREEN}Using active virtual environment: $VIRTUAL_ENV${NC}"
elif [[ -f "venv/bin/activate" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
elif [[ -f ".venv/bin/activate" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source .venv/bin/activate
fi

# Check for LiveKit agents installation
if ! python -c "from livekit.agents import Agent" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  LiveKit agents not installed. Installing...${NC}"
    pip install "livekit-agents[silero,langchain,turn-detector]~=1.0"
    pip install livekit-plugins-openai
fi

# Check if LiveKit server is running
LIVEKIT_URL="${LIVEKIT_URL:-ws://localhost:7880}"
LIVEKIT_HTTP_URL=$(echo "$LIVEKIT_URL" | sed 's/ws:/http:/g')

echo -e "Checking LiveKit server at ${LIVEKIT_HTTP_URL}..."

if curl -s "$LIVEKIT_HTTP_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ LiveKit server is running${NC}"
else
    echo -e "${YELLOW}⚠️  LiveKit server not responding at $LIVEKIT_HTTP_URL${NC}"
    echo ""
    echo "Start LiveKit server with one of these methods:"
    echo ""
    echo "  Option 1: Development mode (easiest)"
    echo "    livekit-server --dev"
    echo ""
    echo "  Option 2: Docker"
    echo "    docker run -d --name livekit \\"
    echo "      -p 7880:7880 -p 7881:7881/tcp -p 50000-60000:50000-60000/udp \\"
    echo "      livekit/livekit-server:latest --dev"
    echo ""
    echo "  Option 3: Build from source"
    echo "    cd ~/MyCode/livekit && go build -o livekit-server ./cmd/server"
    echo "    ./livekit-server --dev"
    echo ""
    
    if [ -t 0 ]; then
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${YELLOW}Non-interactive terminal detected. Continuing anyway...${NC}"
    fi
fi

# Check if local LLM is running
LLM_URL="${OPENAI_BASE_URL:-http://localhost:8080/v1}"
LLM_HEALTH_URL=$(echo "$LLM_URL" | sed 's/\/v1$/\/health/g')

echo -e "Checking local LLM at ${LLM_HEALTH_URL}..."

if curl -s "$LLM_HEALTH_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Local LLM is running${NC}"
else
    echo -e "${YELLOW}⚠️  Local LLM not responding. Starting...${NC}"
    ./scripts/start-llm.sh &
    sleep 10
fi

# Set environment variables
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-http://localhost:8080/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-no-key-required}"
export LIVEKIT_URL="${LIVEKIT_URL:-ws://localhost:7880}"

# Auto-detect speech mode
if [[ -z "$DEEPGRAM_API_KEY" ]] && [[ -z "$CARTESIA_API_KEY" ]] && [[ -z "$USE_LOCAL_SPEECH" ]]; then
    echo -e "${YELLOW}⚠️  Cloud speech keys not found. Switching to LOCAL speech (Whisper/Piper).${NC}"
    export USE_LOCAL_SPEECH=true
fi

# For development mode, use auto-generated keys
if [[ -z "$LIVEKIT_API_KEY" ]]; then
    export LIVEKIT_API_KEY="devkey"
    export LIVEKIT_API_SECRET="secret"
fi

echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  LIVEKIT_URL: $LIVEKIT_URL"
echo "  OPENAI_BASE_URL: $OPENAI_BASE_URL"
echo "  LLM_MODEL: ${LLM_MODEL:-qwen2.5-14b}"
echo ""

# Determine run mode
MODE="${1:-dev}"

case "$MODE" in
    dev)
        echo -e "${BLUE}Starting agent in development mode...${NC}"
        python services/livekit_agent.py dev
        ;;
    connect)
        echo -e "${BLUE}Starting agent in connect mode...${NC}"
        python services/livekit_agent.py connect
        ;;
    join)
        ROOM="${2:-bestbox-room}"
        echo -e "${BLUE}Joining room: ${ROOM}...${NC}"
        python services/livekit_agent.py join --room "$ROOM"
        ;;
    *)
        echo "Usage: $0 [dev|connect|join [room-name]]"
        echo ""
        echo "Modes:"
        echo "  dev     - Development mode with auto-discovery"
        echo "  connect - Connect to LiveKit Cloud"
        echo "  join    - Join a specific room"
        exit 1
        ;;
esac
