#!/bin/bash
# Quick Reference: BestBox LiveKit Voice Interface
# =================================================

cat << 'EOF'

╔══════════════════════════════════════════════════════════╗
║       BestBox LiveKit Integration - Quick Start          ║
╚══════════════════════════════════════════════════════════╝

🚀 START ALL SERVICES (3 commands in 3 terminals)
────────────────────────────────────────────────────────────

Terminal 1 - Backend Services:
$ USE_LIVEKIT=true ./scripts/start-all-services.sh

Terminal 2 - LiveKit Voice Agent:
$ python services/livekit_agent.py dev

Terminal 3 - Frontend:
$ ./scripts/start-frontend.sh

────────────────────────────────────────────────────────────
✅ VERIFY EVERYTHING WORKS
────────────────────────────────────────────────────────────

$ ./scripts/test_e2e_livekit.sh

Expected: ✓ All tests passed! (19/19)

────────────────────────────────────────────────────────────
🎙️ ACCESS VOICE INTERFACE
────────────────────────────────────────────────────────────

Primary:   http://localhost:3000/en/voice
Dashboard: http://localhost:3000
           (Click "🎙️ LiveKit Voice Assistant" button)

────────────────────────────────────────────────────────────
📊 SYSTEM STATUS
────────────────────────────────────────────────────────────

Check Services:
$ curl http://localhost:8080/health    # LLM Server
$ curl http://localhost:8000/health    # Agent API
$ docker ps | grep livekit-server      # LiveKit Server

Check Agent:
$ ps aux | grep livekit_agent          # Voice Agent Process

Check Frontend:
$ curl http://localhost:3000           # Next.js Server

────────────────────────────────────────────────────────────
🎯 SAMPLE VOICE QUERIES
────────────────────────────────────────────────────────────

ERP/Finance:
• "What are the top 5 vendors?"
• "Check inventory levels"
• "Show me purchase orders from last month"

CRM/Sales:
• "Tell me about customer ABC Corp"
• "What are the recent sales opportunities?"
• "Show me the sales pipeline"

IT Operations:
• "Check server status"
• "Show me recent error logs"
• "What's the system health?"

Office Automation:
• "Show pending leave requests"
• "What's on my calendar today?"
• "Approve leave request for John"

────────────────────────────────────────────────────────────
⚡ PERFORMANCE METRICS
────────────────────────────────────────────────────────────

End-to-End Latency: 200-800ms (typical: ~650ms)
- Speech Detection:  50-100ms
- ASR (Speech→Text): 100-200ms
- LLM Inference:     300-500ms
- TTS (Text→Speech): 150-300ms
- Audio Playback:    50ms

Compare to Legacy S2S: ~5x FASTER (was 2-5 seconds)

────────────────────────────────────────────────────────────
🔧 TROUBLESHOOTING
────────────────────────────────────────────────────────────

Service Not Running?
$ ./scripts/start-all-services.sh     # Restart all
$ ./scripts/start-livekit.sh          # Restart LiveKit only

Frontend Issues?
$ cd frontend/copilot-demo && npm install
$ npm run dev

Agent Not Responding?
$ python services/livekit_agent.py dev  # Restart agent
$ curl http://localhost:8080/health      # Check LLM

Connection Drops?
$ docker logs livekit-server             # Check LiveKit logs
$ docker restart livekit-server          # Restart if needed

────────────────────────────────────────────────────────────
📚 DOCUMENTATION
────────────────────────────────────────────────────────────

Complete Guide:        docs/E2E_LIVEKIT_INTEGRATION.md
Testing:               docs/TESTING_GUIDE.md
Deployment:            docs/LIVEKIT_DEPLOYMENT.md
Summary:               docs/FRONTEND_LIVEKIT_COMPLETE.md

────────────────────────────────────────────────────────────
✨ KEY FEATURES
────────────────────────────────────────────────────────────

✓ Real-time Voice (WebRTC)
✓ ~650ms Average Latency
✓ Semantic Turn Detection
✓ Can Interrupt Agent
✓ Conversation History
✓ Audio Visualizer
✓ Auto-reconnect
✓ Mobile Ready

────────────────────────────────────────────────────────────

Need help? Run: ./scripts/test_e2e_livekit.sh

EOF
