#!/bin/bash
# Monitor agent logs in real-time

echo "========================================="
echo "Monitoring LiveKit Agent Logs"
echo "========================================="
echo ""
echo "Watching: /tmp/livekit-agent.log"
echo "Press Ctrl+C to stop"
echo ""
echo "Now:"
echo "1. Refresh http://localhost:3000/en/voice"
echo "2. Click 'Start Voice Session'"
echo "3. Speak into microphone"
echo ""
echo "You should see logs appear here..."
echo ""
echo "========================================="
echo ""

tail -f /tmp/livekit-agent.log
