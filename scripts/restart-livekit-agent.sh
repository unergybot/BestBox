#!/bin/bash
# Restart LiveKit Agent with local STT/TTS

echo "🔄 Restarting LiveKit Agent with LOCAL STT/TTS..."
echo ""

# Kill existing agent
echo "1. Stopping existing agent..."
pkill -f "livekit_agent.py dev" 2>/dev/null && echo "   ✅ Old agent stopped" || echo "   ℹ️  No agent running"
sleep 2

# Verify it's stopped
if ps aux | grep "livekit_agent.py dev" | grep -v grep > /dev/null; then
    echo "   ⚠️  Agent still running, forcing kill..."
    pkill -9 -f "livekit_agent.py dev"
    sleep 1
fi

echo ""
echo "2. Starting new agent with local configuration..."
echo "   STT: local (faster-whisper)"
echo "   TTS: local (Piper)"
echo "   LLM: BestBox LangGraph + Qwen 2.5-14B"
echo ""

cd /home/unergy/BestBox

# Start in background with proper logging
nohup ./venv/bin/python3 services/livekit_agent.py dev > /tmp/livekit-agent.log 2>&1 &
AGENT_PID=$!

echo "3. Agent started (PID: $AGENT_PID)"
echo ""

# Wait a moment for initialization
sleep 3

# Check if it's running
if ps -p $AGENT_PID > /dev/null 2>&1; then
    echo "✅ Agent is running successfully!"
    echo ""
    echo "📊 Check logs:"
    echo "   tail -f /tmp/livekit-agent.log"
    echo ""
    echo "🎙️ Test the voice page:"
    echo "   1. Go to: http://localhost:3000/en/voice"
    echo "   2. Click 'Start Voice Session'"
    echo "   3. Speak into your microphone"
    echo "   4. Agent should respond with audio!"
    echo ""
    
    # Show initial logs
    echo "📝 Initial logs:"
    tail -20 /tmp/livekit-agent.log | sed 's/^/   /'
else
    echo "❌ Agent failed to start!"
    echo "Check logs: cat /tmp/livekit-agent.log"
    exit 1
fi
