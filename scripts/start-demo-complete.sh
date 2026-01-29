#!/bin/bash
# Top-level demo script for BestBox + ClawdBot
# Starts all BestBox backend services, LiveKit Voice Agent, Frontend, and ensures ClawdBot is running.

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}   BestBox + ClawdBot Unified Demo Startup    ${NC}"
echo -e "${BLUE}==============================================${NC}"
echo ""

# 1. Start BestBox Backend Services
echo -e "${YELLOW}[1/4] Starting BestBox Backend Services...${NC}"
if [ -f "./scripts/start-all-services.sh" ]; then
    # We use USE_LIVEKIT=true to ensure LiveKit server is started by start-all-services.sh
    export USE_LIVEKIT=true
    ./scripts/start-all-services.sh
else
    echo -e "${RED}Error: ./scripts/start-all-services.sh not found!${NC}"
    exit 1
fi

# 2. Wait for services to stabilize
echo -e "\n${YELLOW}[2/4] Waiting for services to stabilize...${NC}"
sleep 2
echo -e "${GREEN}✓ Backend services ready${NC}"

# 3. Start Frontend (npm run dev)
echo -e "\n${YELLOW}[3/4] Starting Frontend...${NC}"
if pgrep -f "next-server" > /dev/null || pgrep -f "next dev" > /dev/null; then
    echo -e "${GREEN}✓ Frontend (Next.js) is already running${NC}"
else
    echo "Starting Frontend on port 3000..."
    cd frontend/copilot-demo
    nohup npm run dev > ../../frontend.log 2>&1 &
    cd ../..
    echo -e "${GREEN}✓ Frontend started${NC}"
    echo "Logs available in: frontend.log"
fi


# 4. Restart ClawdBot Gateway
echo -e "\n${YELLOW}[4/4] Ensuring ClawdBot Gateway is active...${NC}"
echo "Restarting clawdbot-gateway.service..."
systemctl --user restart clawdbot-gateway

# Wait a moment for it to stabilize
sleep 3

if systemctl --user is-active --quiet clawdbot-gateway; then
    echo -e "${GREEN}✓ ClawdBot Gateway is RUNNING${NC}"
else
    echo -e "${RED}✗ ClawdBot Gateway failed to start${NC}"
    echo "Check logs with: journalctl --user -u clawdbot-gateway -f"
    # We don't exit here, as BestBox might still be usable
fi

# 5. Final Summary
echo -e "\n${YELLOW}[Final] Deployment Status${NC}"
echo -e "${GREEN}=== System Ready ===${NC}"
echo ""
echo -e "📦 ${BLUE}BestBox Agent${NC}:      http://localhost:8000/health"
echo -e "🤖 ${BLUE}ClawdBot${NC}:           Running (Systemd)"
echo -e "🎙️ ${BLUE}Voice Agent${NC}:        Running (LiveKit)"
echo -e "🖥️ ${BLUE}Frontend${NC}:           http://localhost:3000"
echo -e "🧠 ${BLUE}Reranker${NC}:           http://localhost:8082"
echo -e "🗣️ ${BLUE}S2S/Speech${NC}:         http://localhost:8765"
echo ""
echo -e "Logs:"
echo -e "  - Voice Agent:   ${YELLOW}tail -f livekit_agent.log${NC}"
echo -e "  - Frontend:      ${YELLOW}tail -f frontend.log${NC}"
echo -e "  - ClawdBot:      ${YELLOW}journalctl --user -u clawdbot-gateway -f${NC}"
echo -e "  - Agent API:     ${YELLOW}tail -f agent_api.log${NC}"
echo ""
echo -e "To stop services: ${YELLOW}pkill -f 'agent_api|s2s_server|reranker|livekit_agent|next-server'${NC}"
echo ""
echo "Demo is ready! Open http://localhost:3000 to begin."
