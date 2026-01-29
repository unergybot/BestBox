#!/bin/bash
# Start LiveKit server and agent for BestBox
# This provides lower-latency voice interaction than the custom WebSocket S2S

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Starting LiveKit Stack ===${NC}"
echo ""

# Check if LiveKit server container is already running
if docker ps --format '{{.Names}}' | grep -q "^livekit-server$"; then
    echo -e "${GREEN}✅ LiveKit server already running${NC}"
else
    echo "Starting LiveKit server (Docker)..."
    
    # Clean up any stopped container with same name
    docker rm -f livekit-server 2>/dev/null || true
    
    # Start LiveKit server
    docker run -d --name livekit-server \
      -p 7890:7880 \
      -p 7891:7881/tcp \
      -p 50100-50120:50000-50020/udp \
      livekit/livekit-server:latest \
      --bind 0.0.0.0 \
      --dev > /dev/null 2>&1
    
    echo -e "${GREEN}✅ LiveKit server started${NC}"
    echo "   Container: livekit-server"
    echo "   HTTP Port: 7880"
    echo "   TCP Port: 7881"
    echo "   API Key: devkey"
    echo "   API Secret: secret"
    echo ""
    
    # Wait for server to be ready
    echo -n "Waiting for LiveKit server to initialize"
    for i in {1..15}; do
        if docker logs livekit-server 2>&1 | grep -q "starting LiveKit server"; then
            echo -e " ${GREEN}✓${NC}"
            break
        fi
        echo -n "."
        sleep 1
    done
    echo ""
fi

# Check if LLM is running
echo "Checking local LLM..."
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Local LLM is running${NC}"
else
    echo -e "${YELLOW}⚠️  Local LLM not running. Starting...${NC}"
    cd "$PROJECT_DIR"
    ./scripts/start-llm.sh &
    sleep 5
fi

echo ""
echo -e "${GREEN}=== LiveKit Stack Ready ===${NC}"
echo ""
echo "LiveKit Server: http://localhost:7880"
echo "Local LLM: http://localhost:8080"
echo ""
echo "To start the voice agent:"
echo "  cd $PROJECT_DIR"
echo "  python services/livekit_agent.py dev"
echo ""
echo "Or use the convenience script:"
echo "  ./scripts/start-livekit-agent.sh dev"
echo ""
echo "To stop LiveKit server:"
echo "  docker stop livekit-server"
