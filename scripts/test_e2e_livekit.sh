#!/bin/bash
#
# End-to-End LiveKit Integration Test
# Tests the complete stack from frontend to backend
#

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  BestBox End-to-End LiveKit Integration Test     ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

PASS_COUNT=0
FAIL_COUNT=0

# Test function
test_service() {
    local name=$1
    local url=$2
    local expected=$3
    
    echo -n "Testing $name... "
    
    if curl -s -f -o /dev/null --max-time 2 "$url" 2>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASS_COUNT++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo -e "  ${YELLOW}Expected: Service running at $url${NC}"
        ((FAIL_COUNT++))
        return 1
    fi
}

# Test imports
test_import() {
    local name=$1
    local module=$2
    
    echo -n "Testing $name import... "
    
    if python -c "import $module" 2>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASS_COUNT++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo -e "  ${YELLOW}Cannot import $module${NC}"
        ((FAIL_COUNT++))
        return 1
    fi
}

# Test file existence
test_file() {
    local name=$1
    local path=$2
    
    echo -n "Testing $name exists... "
    
    if [ -f "$path" ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASS_COUNT++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo -e "  ${YELLOW}File not found: $path${NC}"
        ((FAIL_COUNT++))
        return 1
    fi
}

echo -e "${BLUE}1. Backend Services${NC}"
echo -e "───────────────────────────────────────────────────"
test_service "LLM Server" "http://localhost:8080/health" || true
test_service "Agent API" "http://localhost:8000/health" || true

# Check LiveKit container
echo -n "Testing LiveKit Server... "
if docker ps | grep -q livekit-server; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo -e "  ${YELLOW}Container not running. Start with: ./scripts/start-livekit.sh${NC}"
    ((FAIL_COUNT++))
fi
echo ""

echo -e "${BLUE}2. Backend Components${NC}"
echo -e "───────────────────────────────────────────────────"
test_file "LiveKit Agent" "services/livekit_agent.py"
test_file "BestBox Graph" "agents/graph.py"
test_file "Context Manager" "agents/context_manager.py"
test_import "LiveKit Plugins" "livekit.agents"
test_import "BestBox Graph" "agents.graph"
echo ""

echo -e "${BLUE}3. Frontend Components${NC}"
echo -e "───────────────────────────────────────────────────"
test_file "LiveKit Voice Panel" "frontend/copilot-demo/components/LiveKitVoicePanel.tsx"
test_file "LiveKit Room Hook" "frontend/copilot-demo/hooks/useLiveKitRoom.ts"
test_file "Token API" "frontend/copilot-demo/app/api/livekit/token/route.ts"
test_file "Voice Page" "frontend/copilot-demo/app/[locale]/voice/page.tsx"
test_file "Environment Config" "frontend/copilot-demo/.env.local"

# Check npm packages
echo -n "Testing LiveKit npm packages... "
cd frontend/copilot-demo
if npm list livekit-client &> /dev/null && npm list @livekit/components-react &> /dev/null; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo -e "  ${YELLOW}Run: npm install${NC}"
    ((FAIL_COUNT++))
fi
cd "$PROJECT_ROOT"
echo ""

echo -e "${BLUE}4. Configuration${NC}"
echo -e "───────────────────────────────────────────────────"

# Check .env.local content
echo -n "Testing LIVEKIT_URL in .env.local... "
if grep -q "NEXT_PUBLIC_LIVEKIT_URL" frontend/copilot-demo/.env.local; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL_COUNT++))
fi

echo -n "Testing LIVEKIT_API_KEY in .env.local... "
if grep -q "LIVEKIT_API_KEY" frontend/copilot-demo/.env.local; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL_COUNT++))
fi

echo -n "Testing USE_LIVEKIT flag... "
if grep -q "NEXT_PUBLIC_USE_LIVEKIT=true" frontend/copilot-demo/.env.local; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${YELLOW}⚠ WARNING${NC} (LiveKit button may not appear on main page)"
fi
echo ""

echo -e "${BLUE}5. Integration Tests${NC}"
echo -e "───────────────────────────────────────────────────"

# Test agent can import graph
echo -n "Testing BestBox graph import... "
if python -c "from agents.graph import app; assert app is not None" 2>/dev/null; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL_COUNT++))
fi

# Test LiveKit agent
echo -n "Testing LiveKit agent initialization... "
if python -c "from services.livekit_agent import BestBoxVoiceAgent; agent = BestBoxVoiceAgent()" 2>/dev/null; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ FAIL${NC}"
    ((FAIL_COUNT++))
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Passed:${NC} $PASS_COUNT"
echo -e "${RED}Failed:${NC} $FAIL_COUNT"
echo ""

# Recommendations
if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! System is ready.${NC}"
    echo ""
    echo -e "${BLUE}🚀 Next Steps:${NC}"
    echo -e "  1. Start all services:"
    echo -e "     ${YELLOW}USE_LIVEKIT=true ./scripts/start-all-services.sh${NC}"
    echo ""
    echo -e "  2. Start LiveKit agent:"
    echo -e "     ${YELLOW}python services/livekit_agent.py dev${NC}"
    echo ""
    echo -e "  3. Start frontend:"
    echo -e "     ${YELLOW}./scripts/start-frontend.sh${NC}"
    echo ""
    echo -e "  4. Open browser:"
    echo -e "     ${YELLOW}http://localhost:3000/en/voice${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠ Some tests failed. Please fix the issues above.${NC}"
    echo ""
    
    # Provide specific guidance
    if ! docker ps | grep -q livekit-server; then
        echo -e "${BLUE}To start LiveKit:${NC}"
        echo -e "  ${YELLOW}./scripts/start-livekit.sh${NC}"
        echo ""
    fi
    
    if ! curl -s -f -o /dev/null --max-time 2 "http://localhost:8080/health" 2>/dev/null; then
        echo -e "${BLUE}To start LLM server:${NC}"
        echo -e "  ${YELLOW}./scripts/start-llm.sh${NC}"
        echo ""
    fi
    
    if ! curl -s -f -o /dev/null --max-time 2 "http://localhost:8000/health" 2>/dev/null; then
        echo -e "${BLUE}To start agent API:${NC}"
        echo -e "  ${YELLOW}USE_LIVEKIT=true ./scripts/start-all-services.sh${NC}"
        echo ""
    fi
fi

exit $FAIL_COUNT
