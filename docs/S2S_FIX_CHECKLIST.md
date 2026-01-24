# S2S Fix Checklist - Step-by-Step Action Plan

**Goal:** Get S2S feature working for UI testing
**Time Estimate:** 1-2 hours
**Status:** Ready to execute

---

## ✅ Phase 1: Quick Fix (30 minutes)

### Step 1.1: Add TTS Toggle to Server

**File:** `services/speech/s2s_server.py`

**Find line ~236:**
```python
    # Load TTS model (takes time)
    logger.info("Loading TTS model...")
    tts_model = StreamingTTS(TTSConfig(
        model_name=config.tts_model,
        gpu=config.tts_gpu,
        default_language=config.tts_language
    ))
```

**Replace with:**
```python
    # Load TTS model (optional for testing)
    enable_tts = os.environ.get("S2S_ENABLE_TTS", "false").lower() == "true"
    if enable_tts:
        logger.info("Loading TTS model...")
        tts_model = StreamingTTS(TTSConfig(
            model_name=config.tts_model,
            gpu=config.tts_gpu,
            default_language=config.tts_language
        ))
        logger.info("TTS model loaded")
    else:
        logger.info("TTS disabled (set S2S_ENABLE_TTS=true to enable)")
        tts_model = None
```

**Verification:**
```bash
grep -A 10 "Load TTS model" services/speech/s2s_server.py
```

---

### Step 1.2: Test Server Startup

```bash
# Set environment
export S2S_ENABLE_TTS=false

# Start server
./scripts/start-s2s.sh &

# Wait for startup
sleep 5

# Check health
curl -s http://localhost:8765/health | jq '.'
# Expected output:
# {
#   "status": "ok",
#   "service": "s2s-gateway",
#   "tts_enabled": false,
#   ...
# }
```

**✓ Success Criteria:**
- Server starts in < 10 seconds
- Health endpoint returns 200 OK
- No hanging/timeout

**If fails:** Check logs in terminal where `start-s2s.sh` is running

---

### Step 1.3: Test WebSocket Connection

**Open browser console (F12) and run:**
```javascript
// Test WebSocket connection
const ws = new WebSocket('ws://localhost:8765/ws/s2s');

ws.onopen = () => {
  console.log('✅ Connected');

  // Initialize session
  ws.send(JSON.stringify({
    type: 'session_start',
    lang: 'zh',
    audio: { sample_rate: 16000, format: 'pcm16', channels: 1 }
  }));
};

ws.onmessage = (event) => {
  if (typeof event.data === 'string') {
    const msg = JSON.parse(event.data);
    console.log('📨 Message:', msg);
  } else {
    console.log('🔊 Audio:', event.data.byteLength, 'bytes');
  }
};

ws.onerror = (error) => console.error('❌ Error:', error);
ws.onclose = () => console.log('👋 Disconnected');
```

**✓ Success Criteria:**
- `✅ Connected` appears
- `📨 Message: { type: "session_ready", ... }` appears

**If fails:**
- Check if server is running: `curl http://localhost:8765/health`
- Check WebSocket URL is correct: `ws://localhost:8765/ws/s2s`

---

### Step 1.4: Test Text Input (Skip ASR/TTS)

**Continue in browser console:**
```javascript
// Send text directly (no speech needed)
ws.send(JSON.stringify({
  type: 'text_input',
  text: '今天有什么会议？'
}));

// You should see:
// 📨 Message: { type: "llm_token", token: "今" }
// 📨 Message: { type: "llm_token", token: "天" }
// ...
// 📨 Message: { type: "response_end" }
```

**✓ Success Criteria:**
- Tokens stream back
- `response_end` message received
- Agent processes query correctly

**If fails:**
- Check if LangGraph agent is available
- Check server logs for errors

---

## ✅ Phase 2: Frontend Integration (30 minutes)

### Step 2.1: Start Frontend Dev Server

```bash
cd frontend/copilot-demo
npm run dev
```

**Wait for:**
```
  ▲ Next.js 16.0.0
  - Local:        http://localhost:3000
  - Ready in 2.5s
```

---

### Step 2.2: Open Voice Demo Page

**Browser:**
```
http://localhost:3000/voice
```

**✓ Should see:**
- Voice demo page loads
- Two mode buttons: "完整面板" and "仅按钮"
- Connection indicator at bottom (should turn green if server running)

**If page doesn't load:**
- Check Next.js console for errors
- Check browser console for errors
- Verify frontend compiled: `npm run build`

---

### Step 2.3: Test Connection Status

**Look for:**
- Small dot indicator at bottom of VoiceButton
- Should be **green** if connected, gray if not

**If gray (not connected):**
1. Open browser DevTools → Network → WS tab
2. Check for WebSocket connection attempts
3. Look for error messages

**Common issues:**
- CORS: Server should have CORS middleware (already added)
- Wrong URL: Check `useS2S.ts` uses `ws://localhost:8765/ws/s2s`
- Server not running: Restart `./scripts/start-s2s.sh`

---

### Step 2.4: Test Text Input (No Mic Yet)

If VoicePanel has text input box:
1. Type: "今天有什么会议？"
2. Press Enter or click Send
3. Watch for:
   - User message appears
   - Response starts streaming
   - Response completes

**✓ Success Criteria:**
- Text appears in conversation
- Agent responds
- No errors in console

---

### Step 2.5: Test Microphone (Optional if Audio Working)

**Note:** Audio capture requires HTTPS or localhost + user permission

1. Click microphone button
2. Browser asks for mic permission → Click "Allow"
3. Speak: "今天有什么会议？"
4. Click button again to stop

**✓ Success Criteria:**
- Partial transcripts appear while speaking
- Final transcript shows when stopped
- Agent responds

**If fails:**
- Check browser has mic permission
- Check `getUserMedia` errors in console
- May need HTTPS for non-localhost testing

---

## ✅ Phase 3: Verification (15 minutes)

### Test Matrix

| Test | Expected | Status |
|------|----------|--------|
| Server starts | < 10 sec | ⬜ |
| Health endpoint | 200 OK | ⬜ |
| WebSocket connects | `session_ready` | ⬜ |
| Text input works | Agent responds | ⬜ |
| Frontend loads | Page renders | ⬜ |
| Frontend connects | Green indicator | ⬜ |
| Text input (UI) | Response appears | ⬜ |
| Mic capture | Transcript appears | ⬜ |

**Minimum success:** First 4 checkboxes ✅
**Full success:** All checkboxes ✅

---

### Collect Evidence

**Screenshot checklist:**
- [ ] Terminal showing server startup logs
- [ ] `curl http://localhost:8765/health` output
- [ ] Browser console showing WebSocket messages
- [ ] Frontend UI showing successful connection
- [ ] Frontend showing agent response

**Log files:**
```bash
# Save server startup log
./scripts/start-s2s.sh > s2s_startup.log 2>&1 &

# Test and save results
curl -s http://localhost:8765/health > health_check.json

# Browser console: Right-click → Save as...
```

---

## ✅ Phase 4: Enable TTS (Optional, 1-2 hours)

**Only attempt if Phase 1-3 successful**

### Step 4.1: Debug Piper TTS Initialization

```bash
# Test Piper in isolation
python3 -c "
from services.speech.tts import StreamingTTS, TTSConfig
import time

print('Creating TTS config...')
config = TTSConfig(fallback_to_piper=True, gpu=False)

print('Initializing TTS (may hang)...')
start = time.time()
tts = StreamingTTS(config)
print(f'TTS loaded in {time.time() - start:.2f}s')

print('Synthesizing test audio...')
audio = tts.synthesize('Hello world', language='en')
print(f'Generated {len(audio)} bytes')
"
```

**If hangs:**
- Try with `strace -tt python3 -c "..."` to see where it blocks
- Check for model downloads in progress
- Check available disk space: `df -h ~`

---

### Step 4.2: Alternative - Use Mock TTS

**File:** `services/speech/tts.py`

**Add at top:**
```python
class MockTTS:
    """Mock TTS for testing without actual synthesis."""
    def __init__(self, config):
        logger.info("Using mock TTS (returns silence)")

    def synthesize(self, text: str, language: str = "en") -> bytes:
        """Return 1 second of silence."""
        sample_rate = 24000
        duration = 1.0
        samples = int(sample_rate * duration)
        silence = np.zeros(samples, dtype=np.int16)
        return silence.tobytes()
```

**In TTSConfig:**
```python
@dataclass
class TTSConfig:
    use_mock: bool = False  # Add this
    # ... other fields ...
```

**In StreamingTTS.__init__:**
```python
def __init__(self, config: TTSConfig):
    if config.use_mock:
        self.engine = MockTTS(config)
        return

    # ... existing code ...
```

**Test:**
```bash
export S2S_ENABLE_TTS=true
export S2S_TTS_MOCK=true  # Need to add this check
./scripts/start-s2s.sh
```

---

## 🚨 Troubleshooting Guide

### Issue: Server won't start even with TTS disabled

**Check:**
```bash
# Python environment
python3 --version  # Should be 3.12+

# Dependencies
source activate.sh
pip list | grep -E "faster-whisper|fastapi|uvicorn"

# Ports
lsof -i :8765  # Should be empty or show your process
```

**Fix:**
```bash
# Kill existing process
pkill -f s2s_server

# Reinstall dependencies
pip install -r requirements-s2s.txt

# Try again
./scripts/start-s2s.sh
```

---

### Issue: WebSocket connection refused

**Check:**
```bash
# Is server actually listening?
netstat -tuln | grep 8765
# Should show: tcp  0.0.0.0:8765  LISTEN

# Test with curl
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  http://localhost:8765/ws/s2s
```

**Fix:**
- Check firewall: `sudo ufw status`
- Check server logs for binding errors
- Try different port: `export S2S_PORT=9000`

---

### Issue: Frontend can't connect from remote machine

**Cause:** Frontend hardcoded to `localhost:8765`

**Fix:**
```typescript
// frontend/copilot-demo/hooks/useS2S.ts
const DEFAULT_SERVER_URL = process.env.NEXT_PUBLIC_S2S_URL
  || 'ws://localhost:8765/ws/s2s';
```

**Then:**
```bash
# In frontend/.env.local
NEXT_PUBLIC_S2S_URL=ws://YOUR_SERVER_IP:8765/ws/s2s

npm run dev
```

---

## 📊 Success Metrics

**Phase 1 Success:**
- [x] Server starts without hanging
- [x] Health endpoint responds
- [x] WebSocket accepts connections
- [x] Text input generates agent response

**Phase 2 Success:**
- [x] Frontend page loads
- [x] Connection indicator shows green
- [x] UI interaction works
- [x] Agent responses display

**Phase 3 Verification:**
- [x] All tests pass
- [x] Screenshots collected
- [x] Logs saved

**Phase 4 TTS (Optional):**
- [ ] TTS initializes without hanging
- [ ] Audio synthesis works
- [ ] Audio playback works in browser

---

## 🎯 Definition of Done

**Minimum (Testing Enabled):**
1. S2S server starts reliably
2. WebSocket connection works
3. Text input → Agent response works
4. Frontend UI functional
5. Documentation updated

**Complete (Production Ready):**
1. All minimum criteria met
2. TTS audio working
3. ASR transcription working (CPU acceptable)
4. End-to-end latency < 2 seconds
5. Error handling robust
6. Performance benchmarks documented

---

## 📝 Next Steps After Completion

Once checklist complete:

1. **Document findings:**
   - Update `PROJECT_STATUS.md`
   - Add screenshots to `docs/screenshots/`
   - Update CLAUDE.md with S2S usage

2. **Create demo video:**
   - Screen recording of working flow
   - Show: Connect → Speak → Transcribe → Respond
   - Upload to docs/

3. **Plan improvements:**
   - GPU ASR support (CTranslate2 + ROCm)
   - TTS optimization (async loading)
   - Mobile client
   - Performance tuning

4. **Celebrate! 🎉**
   - Working S2S is a major milestone
   - Document lessons learned
   - Share with team

---

## Time Estimate Breakdown

| Phase | Task | Time | Cumulative |
|-------|------|------|------------|
| 1.1 | Add TTS toggle | 10m | 10m |
| 1.2 | Test startup | 5m | 15m |
| 1.3 | Test WebSocket | 5m | 20m |
| 1.4 | Test text input | 10m | 30m |
| 2.1 | Start frontend | 5m | 35m |
| 2.2 | Open demo page | 5m | 40m |
| 2.3 | Test connection | 5m | 45m |
| 2.4 | Test UI text | 10m | 55m |
| 2.5 | Test microphone | 5m | 60m |
| 3 | Verification | 15m | 75m |
| 4 | TTS debug (opt) | 60-120m | 135-195m |

**Total:** 75 minutes (minimum) to 3 hours (with TTS)
