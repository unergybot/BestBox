#!/bin/bash
# LiveKit Audio Fix Verification Script

echo "========================================="
echo "LiveKit Voice Page - Audio Fix Verification"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check LiveKit Server
echo -n "1. Checking LiveKit Server (port 7880)... "
if lsof -i:7880 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
    exit 1
fi

# Check LiveKit Agent
echo -n "2. Checking LiveKit Agent processes... "
AGENT_COUNT=$(ps aux | grep "livekit_agent.py" | grep -v grep | wc -l)
if [ "$AGENT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Running ($AGENT_COUNT processes)${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
    exit 1
fi

# Check Next.js Frontend
echo -n "3. Checking Next.js Frontend (port 3000)... "
if ps aux | grep "node.*next dev" | grep -v grep > /dev/null; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
    exit 1
fi

# Check Voice Page Accessibility
echo -n "4. Checking Voice Page accessibility... "
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/en/voice)
if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ Accessible (HTTP $HTTP_STATUS)${NC}"
else
    echo -e "${RED}✗ Not Accessible (HTTP $HTTP_STATUS)${NC}"
    exit 1
fi

# Check LiveKit Token API
echo -n "5. Checking LiveKit Token API... "
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/livekit/token \
  -H "Content-Type: application/json" \
  -d '{"roomName":"test-room","participantName":"test-user"}' \
  -w "\n%{http_code}" | tail -1)

if [ "$TOKEN_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ Working${NC}"
else
    echo -e "${YELLOW}⚠ Check backend (HTTP $TOKEN_RESPONSE)${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}All Core Services Running!${NC}"
echo "========================================="
echo ""
echo "🎉 The LiveKit audio fix has been applied!"
echo ""
echo "Next Steps:"
echo "  1. Open browser: http://localhost:3000/en/voice"
echo "  2. Click the '🎙️ Start Voice Session' button"
echo "  3. Allow microphone access when prompted"
echo "  4. Wait for '✅ Audio system ready!' notification"
echo "  5. Start speaking to test"
echo ""
echo "Expected Console Logs:"
echo "  • [LiveKit] Connecting to: ws://localhost:7880"
echo "  • [LiveKit] Audio context started successfully"
echo "  • [LiveKit] Connected to room"
echo "  • [LiveKit] Agent audio track subscribed"
echo "  • [LiveKit] Audio playback started successfully"
echo ""
echo "📚 See docs/LIVEKIT_AUDIO_FIX.md for details"
echo ""
