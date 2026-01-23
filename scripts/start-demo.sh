#!/bin/bash
# BestBox AI Agent Demo Startup Script
# Orchestrates Docker services, Agent API, and frontend components

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== BestBox AI Agent Demo Startup ===${NC}"

# 1. Start Docker Services
echo -e "\n${YELLOW}[1/4] Starting Docker services...${NC}"
if docker compose up -d; then
    echo -e "${GREEN}✓ Docker services started${NC}"
else
    echo -e "${RED}Failed to start Docker services${NC}"
    exit 1
fi

# 2. Wait for services (brief check)
echo -e "\n${YELLOW}[2/4] Checking core services...${NC}"
sleep 5
if docker compose ps | grep -q "bestbox-redis"; then
    echo -e "${GREEN}✓ Redis is running${NC}"
else
    echo -e "${YELLOW}Warning: Redis might not be ready yet${NC}"
fi

# 3. Start Agent API Server
echo -e "\n${YELLOW}[3/4] Starting Agent API Server...${NC}"
if pgrep -f "services/agent_api.py" > /dev/null; then
    echo -e "${GREEN}✓ Agent API server is already running${NC}"
else
    echo "Starting server on port 8000..."
    # Run in background with nohup, redirect logs to file
    source venv/bin/activate
    nohup python services/agent_api.py > agent_api.log 2>&1 &
    PID=$!
    echo -e "${GREEN}✓ Agent API server started (PID: $PID)${NC}"
    echo "Logs available in: agent_api.log"
fi

# 4. Success Message
echo -e "\n${GREEN}=== Demo Environment Ready ===${NC}"
echo -e "ERPNext:    http://localhost:8002 (Administrator / admin)"
echo -e "Agent API:  http://localhost:8000/health"
echo -e "Frontend:   http://localhost:3000 (if npm run dev is running)"
echo -e ""
echo -e "To stop the API server later: pkill -f 'services/agent_api.py'"
echo -e "To view API logs: tail -f agent_api.log"
