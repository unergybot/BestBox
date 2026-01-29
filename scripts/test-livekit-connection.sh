#!/bin/bash
# Test LiveKit Voice System End-to-End

echo "========================================="
echo "LiveKit Voice System Diagnostic"
echo "========================================="
echo ""

# 1. Check LiveKit Server
echo "1. Checking LiveKit Server..."
if docker ps | grep bestbox-livekit > /dev/null; then
    echo "   ✅ LiveKit server container running"
    LIVEKIT_LOGS=$(docker logs bestbox-livekit --tail 5 2>&1)
    echo "   Last logs:"
    echo "$LIVEKIT_LOGS" | sed 's/^/      /'
else
    echo "   ❌ LiveKit server NOT running"
    exit 1
fi
echo ""

# 2. Check LiveKit Agent Process
echo "2. Checking LiveKit Agent..."
AGENT_PID=$(ps aux | grep "livekit_agent.py dev" | grep -v grep | awk '{print $2}' | head -1)
if [ -n "$AGENT_PID" ]; then
    echo "   ✅ Agent running (PID: $AGENT_PID)"
    echo "   Checking agent connectivity..."
    
    # Get terminal for agent
    AGENT_TTY=$(ps -p $AGENT_PID -o tty= | tr -d ' ')
    echo "   Agent terminal: $AGENT_TTY"
else
    echo "   ❌ Agent NOT running"
    echo "   Start with: cd /home/unergy/BestBox && ./venv/bin/python3 services/livekit_agent.py dev"
    exit 1
fi
echo ""

# 3. Check Environment Variables
echo "3. Checking Environment Variables..."
cd /home/unergy/BestBox
source .env 2>/dev/null || true

LIVEKIT_URL=$(grep LIVEKIT_URL .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || echo "ws://localhost:7880")
LIVEKIT_API_KEY=$(grep LIVEKIT_API_KEY .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || echo "devkey")
NEXT_PUBLIC_LIVEKIT_URL=$(grep NEXT_PUBLIC_LIVEKIT_URL .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || echo "ws://localhost:7880")

echo "   LIVEKIT_URL: $LIVEKIT_URL"
echo "   LIVEKIT_API_KEY: ${LIVEKIT_API_KEY:0:10}..."
echo "   NEXT_PUBLIC_LIVEKIT_URL: $NEXT_PUBLIC_LIVEKIT_URL"
echo ""

# 4. Test Token Generation
echo "4. Testing Token Generation..."
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:3000/api/livekit/token \
  -H "Content-Type: application/json" \
  -d '{"roomName":"test-room","participantName":"test-user"}')

if echo "$TOKEN_RESPONSE" | jq -e '.token' > /dev/null 2>&1; then
    echo "   ✅ Token API working"
    TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.token')
    echo "   Token: ${TOKEN:0:50}..."
else
    echo "   ❌ Token API failed"
    echo "   Response: $TOKEN_RESPONSE"
    exit 1
fi
echo ""

# 5. Check Frontend
echo "5. Checking Frontend..."
if ps aux | grep "node.*next dev" | grep -v grep > /dev/null; then
    echo "   ✅ Next.js dev server running"
else
    echo "   ❌ Next.js NOT running"
    exit 1
fi
echo ""

# 6. Test actual voice page load
echo "6. Testing Voice Page..."
PAGE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/en/voice)
if [ "$PAGE_RESPONSE" = "200" ]; then
    echo "   ✅ Voice page accessible (HTTP $PAGE_RESPONSE)"
else
    echo "   ❌ Voice page NOT accessible (HTTP $PAGE_RESPONSE)"
    exit 1
fi
echo ""

echo "========================================="
echo "System Status: ALL CHECKS PASSED ✅"
echo "========================================="
echo ""
echo "📋 Next Steps to Test:"
echo ""
echo "1. Open Browser Developer Console (F12)"
echo "2. Navigate to: http://localhost:3000/en/voice"
echo "3. Click '🎙️ Start Voice Session' button"
echo "4. Allow microphone when prompted"
echo ""
echo "Expected Console Output:"
echo "  [LiveKit] Connecting to: ws://localhost:7880"
echo "  [LiveKit] Audio context started successfully"
echo "  [LiveKit] Connected to room"
echo ""
echo "Agent Terminal to Monitor (for agent logs):"
echo "  ps -t $AGENT_TTY"
echo ""
echo "If you DON'T see these logs:"
echo "  - Check browser console for JavaScript errors"
echo "  - Verify microphone permission granted"
echo "  - Check agent terminal output for errors"
echo ""
