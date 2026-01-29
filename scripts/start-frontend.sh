#!/bin/bash
#
# Start BestBox Frontend with LiveKit Integration
#
# This script builds and starts the Next.js frontend with full LiveKit support
#

set -e

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FRONTEND_DIR="$SCRIPT_DIR/../frontend/copilot-demo"

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   BestBox Frontend - LiveKit Voice Integration    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
echo ""

cd "$FRONTEND_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📦 Installing dependencies...${NC}"
    npm install
    echo ""
fi

# Check if LiveKit dependencies are installed
if ! npm list livekit-client &> /dev/null; then
    echo -e "${YELLOW}📦 Installing LiveKit dependencies...${NC}"
    npm install livekit-client@^2.7.5 @livekit/components-react@^2.6.4 livekit-server-sdk@^2.7.4
    echo ""
fi

# Check .env.local
if [ ! -f ".env.local" ]; then
    echo -e "${RED}✗ .env.local not found${NC}"
    echo -e "${YELLOW}Creating default .env.local...${NC}"
    cat > .env.local << 'EOF'
# OpenAI SDK Configuration - Points to our local LangGraph agent API
OPENAI_BASE_URL=http://127.0.0.1:8000/v1
OPENAI_API_KEY=sk-local-llm-no-key-needed

# Agent API URL
AGENT_API_URL=http://127.0.0.1:8000

# LiveKit Configuration
NEXT_PUBLIC_LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
NEXT_PUBLIC_USE_LIVEKIT=true
EOF
    echo -e "${GREEN}✓ Created .env.local${NC}"
    echo ""
fi

# Build the frontend
if [ "$1" = "build" ]; then
    echo -e "${YELLOW}🔨 Building production bundle...${NC}"
    npm run build
    echo ""
    echo -e "${GREEN}✓ Build complete!${NC}"
    echo ""
    echo -e "${BLUE}Start with:${NC} npm start"
    exit 0
fi

# Check if backend services are running
echo -e "${BLUE}Checking backend services...${NC}"

check_service() {
    local name=$1
    local url=$2
    
    if curl -s -f -o /dev/null --max-time 2 "$url" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $name is running"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} $name is NOT running"
        return 1
    fi
}

LLM_OK=false
API_OK=false
LIVEKIT_OK=false

check_service "LLM Server" "http://localhost:8080/health" && LLM_OK=true || true
check_service "Agent API" "http://localhost:8000/health" && API_OK=true || true

# Check LiveKit
if docker ps | grep -q livekit-server; then
    echo -e "${GREEN}✓${NC} LiveKit Server is running"
    LIVEKIT_OK=true
else
    echo -e "${YELLOW}⚠${NC} LiveKit Server is NOT running"
fi

echo ""

# Warnings
if [ "$LLM_OK" = false ] || [ "$API_OK" = false ]; then
    echo -e "${YELLOW}⚠ Backend services not running. Start with:${NC}"
    echo -e "  ${BLUE}./scripts/start-all-services.sh${NC}"
    echo ""
fi

if [ "$LIVEKIT_OK" = false ]; then
    echo -e "${YELLOW}⚠ LiveKit not running. Voice features disabled. Start with:${NC}"
    echo -e "  ${BLUE}./scripts/start-livekit.sh${NC}"
    echo ""
fi

# Start development server
echo -e "${GREEN}🚀 Starting Next.js development server...${NC}"
echo ""
echo -e "${BLUE}Frontend will be available at:${NC}"
echo -e "  • Main: ${GREEN}http://localhost:3000${NC}"
echo -e "  • Voice: ${GREEN}http://localhost:3000/en/voice${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

npm run dev
