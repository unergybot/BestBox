#!/bin/bash

# Verify Model Sharing in LiveKit Agent
#
# This script helps verify that ASR and TTS models are being reused
# across sessions instead of loading new instances for each connection.

echo "=================================================="
echo "Model Sharing Verification for LiveKit Agent"
echo "=================================================="
echo ""

# Check if agent is running
if ! pgrep -f "livekit_agent.py" > /dev/null; then
    echo "❌ LiveKit agent is not running!"
    echo "   Start it with: python services/livekit_agent.py dev"
    exit 1
fi

echo "✅ LiveKit agent is running"
echo ""

# Get agent PID and memory usage
AGENT_PID=$(pgrep -f "livekit_agent.py" | head -1)
INITIAL_MEM=$(ps -o rss= -p $AGENT_PID)
INITIAL_MEM_MB=$((INITIAL_MEM / 1024))

echo "Agent PID: $AGENT_PID"
echo "Current memory: ${INITIAL_MEM_MB}MB"
echo ""

echo "=================================================="
echo "What to look for in agent logs:"
echo "=================================================="
echo ""
echo "FIRST SESSION (creates models):"
echo "  🔧 Initializing shared ASR model (first session)..."
echo "  ✅ Shared ASR model initialized (ID: XXXXXXXX)"
echo "  🔧 Initializing shared TTS engine (first session)..."
echo "  ✅ Shared TTS engine initialized (ID: XXXXXXXX)"
echo ""
echo "SUBSEQUENT SESSIONS (reuses models):"
echo "  ♻️  Reusing existing shared ASR model (ID: XXXXXXXX)"
echo "  ♻️  Reusing existing shared TTS engine (ID: XXXXXXXX)"
echo ""
echo "=================================================="
echo "Memory Monitor (runs every 60 seconds):"
echo "=================================================="
echo ""
echo "Healthy: Memory usage: XXXMB (healthy)"
echo "Warning: Memory usage: XXXMB (warning threshold)"
echo "High:    High memory usage detected: XXXMB - forcing GC"
echo ""
echo "=================================================="
echo "Testing Instructions:"
echo "=================================================="
echo ""
echo "1. Open browser to: http://localhost:3000/en/voice"
echo "2. Connect to voice UI (first time)"
echo "3. Watch logs - should see '🔧 Initializing' messages"
echo "4. Disconnect and reconnect (second time)"
echo "5. Watch logs - should see '♻️ Reusing' messages"
echo "6. Check memory hasn't grown significantly"
echo ""
echo "Expected memory behavior:"
echo "  - First connection:  ~1.8-2.2GB (loads models)"
echo "  - Second connection: ~1.8-2.3GB (minimal increase)"
echo "  - Third connection:  ~1.8-2.3GB (stable)"
echo ""
echo "=================================================="
echo "Monitoring memory changes..."
echo "=================================================="
echo ""

# Monitor memory for 10 seconds
for i in {1..10}; do
    CURRENT_MEM=$(ps -o rss= -p $AGENT_PID)
    CURRENT_MEM_MB=$((CURRENT_MEM / 1024))
    DIFF_MB=$((CURRENT_MEM_MB - INITIAL_MEM_MB))

    if [ $DIFF_MB -gt 0 ]; then
        echo "[$i/10] Memory: ${CURRENT_MEM_MB}MB (+${DIFF_MB}MB)"
    else
        echo "[$i/10] Memory: ${CURRENT_MEM_MB}MB"
    fi
    sleep 1
done

echo ""
echo "=================================================="
echo "Current Status:"
echo "=================================================="
FINAL_MEM=$(ps -o rss= -p $AGENT_PID)
FINAL_MEM_MB=$((FINAL_MEM / 1024))
TOTAL_DIFF=$((FINAL_MEM_MB - INITIAL_MEM_MB))

echo "Initial memory: ${INITIAL_MEM_MB}MB"
echo "Current memory: ${FINAL_MEM_MB}MB"
echo "Change: ${TOTAL_DIFF}MB"
echo ""

if [ $FINAL_MEM_MB -lt 2500 ]; then
    echo "✅ Memory usage is healthy (<2.5GB)"
elif [ $FINAL_MEM_MB -lt 3000 ]; then
    echo "⚠️  Memory usage approaching threshold (2.5-3GB)"
else
    echo "❌ Memory usage is high (>3GB) - check for leaks"
fi

echo ""
echo "To see live logs:"
echo "  tail -f <agent-log-file>"
echo ""
echo "To test multiple connections:"
echo "  Open 3 browser tabs, connect/disconnect from each"
echo "  Memory should stabilize around 2GB, not grow continuously"
echo ""
