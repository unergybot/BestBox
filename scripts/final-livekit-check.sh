#!/bin/bash
# Final verification before testing

echo "========================================="
echo "LiveKit Voice System - Final Status"
echo "========================================="
echo ""

# 1. Check Agent
echo "1. LiveKit Agent Status:"
AGENT_PID=$(ps aux | grep "livekit_agent.py dev" | grep -v grep | awk '{print $2}' | head -1)
if [ -n "$AGENT_PID" ]; then
    echo "   ✅ Running (PID: $AGENT_PID)"
    echo "   📝 Config:"
    grep -E "(STT Model|TTS Model|LangGraph)" /tmp/livekit-agent.log 2>/dev/null | tail -3 | sed 's/^/      /'
else
    echo "   ❌ NOT running"
    exit 1
fi
echo ""

# 2. Check LiveKit Server
echo "2. LiveKit Server:"
if docker ps | grep bestbox-livekit > /dev/null; then
    echo "   ✅ Running"
else
    echo "   ❌ NOT running"
    exit 1
fi
echo ""

# 3. Check Frontend
echo "3. Next.js Frontend:"
if ps aux | grep "node.*next dev" | grep -v grep > /dev/null; then
    echo "   ✅ Running on http://localhost:3000"
else
    echo "   ❌ NOT running"
    exit 1
fi
echo ""

# 4. Environment check
echo "4. Configuration:"
cd /home/unergy/BestBox
source .env 2>/dev/null
echo "   STT_MODEL: $STT_MODEL"
echo "   TTS_MODEL: $TTS_MODEL"
echo "   USE_LOCAL_SPEECH: $USE_LOCAL_SPEECH"
echo ""

echo "========================================="
echo "✅ ALL SYSTEMS READY!"
echo "========================================="
echo ""
echo "🎯 TESTING INSTRUCTIONS:"
echo ""
echo "1. Open browser to: http://localhost:3000/en/voice"
echo ""
echo "2. You should see:"
echo "   • Large button: '🎙️ Start Voice Session'"
echo "   • Text below: '✅ Audio fix v1.1 - Browser autoplay handled'"
echo ""
echo "3. Click the 'Start Voice Session' button"
echo "   • Browser will ask for microphone permission"
echo "   • Click 'Allow'"
echo ""
echo "4. You should see:"
echo "   • Status changes to '🟢 Connected'"
echo "   • Green notification: '✅ Audio system ready!'"
echo "   • Green microphone button at bottom: 🎤"
echo ""
echo "5. SPEAK into your microphone:"
echo "   • Try: 'Hello, can you help me?'"
echo "   • Your text appears in blue bubble (right)"
echo "   • Agent responds in gray bubble (left)"
echo "   • You HEAR the audio response!"
echo ""
echo "========================================="
echo "🐛 IF IT DOESN'T WORK:"
echo "========================================="
echo ""
echo "Check agent logs in real-time:"
echo "  tail -f /tmp/livekit-agent.log"
echo ""
echo "You should see when you speak:"
echo "  • 'New session started in room: bestbox-voice'"
echo "  • 'Using LOCAL STT (faster-whisper)'"
echo "  • '✅ Local STT initialized successfully'"
echo "  • 'Using LOCAL TTS (Piper)'"
echo "  • '✅ Local TTS initialized successfully'"
echo ""
echo "========================================="
