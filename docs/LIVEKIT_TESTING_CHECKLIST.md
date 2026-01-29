# LiveKit Voice Page - Testing Checklist

## ⚠️ IMPORTANT: You Must Click "Start Voice Session"

The console logs `[LiveKit] Connecting to...` will **ONLY appear AFTER you click the "Start Voice Session" button** in the browser. This is intentional and required by browser security policies.

## Step-by-Step Testing Instructions

### 1. Open the Page
- Navigate to: **http://localhost:3000/en/voice**
- You should see a large blue button: **"🎙️ Start Voice Session"**
- Below it, you should see: ✅ **Audio fix v1.1 - Browser autoplay handled**
  - If you DON'T see this text, refresh the page (Ctrl+F5) to clear cache

### 2. Open Browser Console
- Press **F12** to open Developer Tools
- Click **Console** tab
- Clear any existing logs

### 3. Click "Start Voice Session"
**THIS IS THE CRITICAL STEP!**

When you click the button, you should immediately see console logs:
```
[LiveKit] Connecting to: ws://localhost:7880
[LiveKit] Audio context started successfully
```

Then within 1-2 seconds:
```
[LiveKit] Connected to room
[LiveKit] Agent audio track subscribed
[LiveKit] Audio playback started successfully
```

### 4. Grant Microphone Permission
- Browser will prompt for microphone access
- Click **"Allow"**
- You should see microphone icon in browser tab

### 5. Verify Connection
After successful connection, you should see:
- ✅ Status: **"🟢 Connected"** (top of panel)
- ✅ Green notification: **"Audio system ready! Start speaking to interact with BestBox."**
- ✅ Green microphone button at bottom: **🎤 Microphone Active**

### 6. Test Voice Interaction
- **Speak clearly** into your microphone
- Try: *"Hello, what can you help me with?"*
- You should see:
  - Your transcript appear in blue bubble (right side)
  - Agent response appear in gray bubble (left side)
  - Agent audio plays through speakers

## Expected Console Output

```
[LiveKit] Connecting to: ws://localhost:7880
[LiveKit] Audio context started successfully
[LiveKit] Connected to room
[LiveKit] Agent audio track subscribed
[LiveKit] Audio playback started successfully
[LiveKit] Connection successful
```

## Troubleshooting

### Problem: No console logs at all
**Cause**: You didn't click the "Start Voice Session" button  
**Solution**: Click the button!

### Problem: Console shows "NotAllowedError" for audio
**Cause**: Browser blocked audio before user interaction  
**Solution**: Our fix handles this! Just click anywhere on the page and audio should resume automatically

### Problem: Connected but no agent response
**Cause**: Agent might not be running or configured correctly  
**Check**:
```bash
# Verify agent is running
ps aux | grep livekit_agent.py

# Should show: ./venv/bin/python3 services/livekit_agent.py dev
```

**Check Agent Terminal** (pts/2):
```bash
# Watch agent logs in real-time
# Open the terminal where agent is running
# You should see logs like:
# "New session started in room: bestbox-voice"
# "STT configured: deepgram/nova-3"
# "Using BestBox LangGraph for LLM"
```

### Problem: Microphone not working
**Check**:
1. Microphone permission granted?
2. Correct microphone selected in browser settings?
3. Test microphone in browser: chrome://settings/content/microphone

### Problem: Can hear yourself echo
**Cause**: Browser audio output feeding back to microphone  
**Solution**: Use headphones or reduce speaker volume

## System Requirements Check

Run this before testing:
```bash
cd /home/unergy/BestBox
./scripts/test-livekit-connection.sh
```

Should show all green ✅ checkmarks.

## Architecture Flow

```
User speaks into mic
    ↓
Browser captures audio
    ↓
LiveKit WebRTC → LiveKit Server (ws://localhost:7880)
    ↓
LiveKit Agent (services/livekit_agent.py)
    ↓
STT (Deepgram/nova-3 or local Whisper)
    ↓
BestBox LangGraph (agents/graph.py)
    ↓
LLM (Qwen 2.5-14B at localhost:8080)
    ↓
TTS (Cartesia/sonic-3 or local Piper)
    ↓
LiveKit Server → Browser
    ↓
User hears response
```

## Performance Expectations

- **First response latency**: 2-4 seconds
  - STT: ~500ms
  - LLM: 1-2s
  - TTS: ~500ms
  - Network: <100ms

- **Subsequent responses**: 1-2 seconds (with streaming)

## Debug Mode

To see detailed agent logs:
```bash
# In agent terminal (pts/2)
cd /home/unergy/BestBox
export LIVEKIT_LOG_LEVEL=debug
./venv/bin/python3 services/livekit_agent.py dev
```

## Success Criteria

✅ Page loads with "Start Voice Session" button  
✅ Button shows "Audio fix v1.1" text  
✅ Console logs appear after clicking button  
✅ Connection established within 2 seconds  
✅ Green "Audio system ready" notification  
✅ Microphone icon shows active  
✅ Speaking shows transcript  
✅ Agent responds with audio  

## Common Mistakes

❌ **Expecting logs before clicking button** - Won't happen!  
❌ **Not granting microphone permission** - Required!  
❌ **Testing without agent running** - Agent must be active!  
❌ **Browser cache showing old code** - Hard refresh (Ctrl+F5)!

## Additional Resources

- Full fix documentation: `docs/LIVEKIT_AUDIO_FIX.md`
- Agent code: `services/livekit_agent.py`
- Frontend hook: `frontend/copilot-demo/hooks/useLiveKitRoom.ts`
- LiveKit docs: https://docs.livekit.io/agents/
