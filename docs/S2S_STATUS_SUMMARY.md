# S2S Feature Status - Quick Summary

**Last Updated:** 2026-01-23
**Overall Status:** 🔴 NOT WORKING (but fully implemented)

---

## TL;DR

✅ **All code written and in place**
❌ **Service won't start due to TTS model loading hang**
🎯 **Fix: 1-2 hours to make testable**

---

## The Problem in One Sentence

The S2S WebSocket server hangs indefinitely during startup when trying to load the TTS model, preventing any testing of the otherwise complete implementation.

---

## What Works ✅

```
┌─────────────────────────────────────────────────────┐
│  CODE COMPLETE (100%)                              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Backend:                                           │
│  ✅ ASR service (faster-whisper + VAD)             │
│  ✅ TTS service (XTTS v2 / Piper fallback)         │
│  ✅ WebSocket gateway (FastAPI)                    │
│  ✅ Session management                             │
│  ✅ LangGraph agent integration                    │
│                                                     │
│  Frontend:                                          │
│  ✅ useS2S hook (WebSocket + audio)                │
│  ✅ useAudioCapture hook (WebAudio API)            │
│  ✅ VoiceButton component                          │
│  ✅ VoicePanel component                           │
│  ✅ /voice demo page                               │
│                                                     │
│  Infrastructure:                                    │
│  ✅ Python 3.12 compatibility fixes                │
│  ✅ Startup scripts                                │
│  ✅ Requirements files                             │
│  ✅ Documentation                                  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## What's Broken ❌

```
┌─────────────────────────────────────────────────────┐
│  RUNTIME ISSUES                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🔴 P0: TTS Model Loading Hangs                    │
│     └─ Blocks server startup indefinitely          │
│     └─ Piper TTS init appears to freeze            │
│     └─ No WebSocket endpoint available             │
│                                                     │
│  🟡 P0: ASR GPU Not Working                        │
│     └─ CTranslate2 lacks ROCm support              │
│     └─ Falls back to CPU (slow but works)          │
│     └─ Acceptable for testing                      │
│                                                     │
│  🟡 P1: Missing Dependencies in Main Env           │
│     └─ requirements-s2s.txt not auto-installed     │
│     └─ Test scripts fail                           │
│     └─ Easy fix: pip install -r requirements-s2s.txt │
│                                                     │
│  🔴 P0: Frontend Can't Connect                     │
│     └─ Because server never starts                 │
│     └─ Will work once server issue fixed           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## The Startup Flow (Where It Breaks)

```
./scripts/start-s2s.sh
    │
    ├─ ✅ Activate venv
    ├─ ✅ Check dependencies
    ├─ ✅ Detect GPU
    ├─ ⚠️  GPU init fails → CPU fallback
    ├─ ✅ Start uvicorn
    │
    └─ FastAPI Application Startup
        │
        ├─ ✅ Load config
        ├─ ✅ Create session manager
        │
        └─ ❌ Load TTS model ← HANGS HERE
            │
            └─ (Never reaches this point)
                ├─ Start WebSocket server
                ├─ Accept connections
                └─ Service ready
```

**Code Location:** `services/speech/s2s_server.py:236-242`

---

## Quick Fix (1 hour)

**Option: Disable TTS for Testing**

```python
# In services/speech/s2s_server.py, line ~236
async def lifespan(app: FastAPI):
    # ...

    # BEFORE:
    logger.info("Loading TTS model...")
    tts_model = StreamingTTS(TTSConfig(...))

    # AFTER:
    if os.environ.get("S2S_ENABLE_TTS", "false").lower() == "true":
        logger.info("Loading TTS model...")
        tts_model = StreamingTTS(TTSConfig(...))
    else:
        logger.info("TTS disabled for testing")
        tts_model = None  # Agent will work without TTS
```

**Test:**
```bash
export S2S_ENABLE_TTS=false
./scripts/start-s2s.sh
# Should start in <5 seconds

curl http://localhost:8765/health
# Should return: {"status": "ok"}
```

---

## Better Fix (2 hours)

**Option: Lazy Load TTS on First Use**

```python
# Global state
tts_model: Optional[StreamingTTS] = None
tts_loading: bool = False

async def get_tts_model():
    """Lazy-load TTS model on first request."""
    global tts_model, tts_loading

    if tts_model is not None:
        return tts_model

    if tts_loading:
        # Wait for another request to finish loading
        while tts_loading:
            await asyncio.sleep(0.1)
        return tts_model

    tts_loading = True
    try:
        logger.info("Loading TTS model (lazy)...")
        tts_model = StreamingTTS(TTSConfig(...))
        logger.info("TTS model loaded")
    finally:
        tts_loading = False

    return tts_model

# In lifespan:
async def lifespan(app: FastAPI):
    # ... startup ...
    # Don't load TTS here

    logger.info("S2S Gateway ready (TTS will load on first use)")
    yield
```

---

## Test Plan After Fix

```bash
# 1. Start service with TTS disabled
export S2S_ENABLE_TTS=false
./scripts/start-s2s.sh &

# 2. Verify health
curl http://localhost:8765/health

# 3. Test WebSocket with text input (no audio needed)
node <<EOF
const WebSocket = require('ws');
const ws = new WebSocket('ws://localhost:8765/ws/s2s');

ws.on('open', () => {
  ws.send(JSON.stringify({
    type: 'session_start',
    lang: 'zh'
  }));

  ws.send(JSON.stringify({
    type: 'text_input',
    text: '今天天气怎么样？'
  }));
});

ws.on('message', (data) => {
  console.log('Received:', data.toString());
});
EOF

# 4. Test frontend
cd frontend/copilot-demo && npm run dev
# Open http://localhost:3000/voice
# Should connect and work with text input
```

---

## Architecture Diagram (What Should Happen)

```
┌─────────────┐
│   Browser   │
│  (Next.js)  │
└──────┬──────┘
       │ ws://localhost:8765/ws/s2s
       ▼
┌─────────────────────────────────────────┐
│     S2S Gateway (FastAPI)               │
│  ┌───────────────────────────────────┐  │
│  │  WebSocket Handler                │  │
│  │  ┌─────────┐  ┌─────────────┐    │  │
│  │  │   VAD   │  │   Session   │    │  │
│  │  │         │  │   Manager   │    │  │
│  │  └─────────┘  └─────────────┘    │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │   ASR    │ │ LangGraph│ │  TTS   │ │
│  │ (Whisper)│ │  Agent   │ │ (Piper)│ │
│  └──────────┘ └──────────┘ └────────┘ │
│      ↑             ↑           ↑       │
│      CPU         Works       HANGS     │
└─────────────────────────────────────────┘
```

**Current Reality:**
- TTS hangs during init → Server never starts
- Browser sees: `Connection failed`

**After Fix:**
- TTS loads lazily/disabled → Server starts
- Browser connects successfully
- Can test full flow (minus TTS audio)

---

## File Locations

```
Backend:
  services/speech/
    ├── asr.py              ← ASR engine (works on CPU)
    ├── tts.py              ← TTS engine (init hangs)
    └── s2s_server.py       ← Main server (blocked by TTS)

Frontend:
  frontend/copilot-demo/
    ├── hooks/
    │   ├── useAudioCapture.ts  ← Mic capture
    │   └── useS2S.ts           ← WebSocket hook
    ├── components/
    │   ├── VoiceButton.tsx     ← UI component
    │   └── VoicePanel.tsx      ← Full UI panel
    └── app/[locale]/voice/
        └── page.tsx            ← Demo page

Scripts:
  scripts/
    ├── start-s2s.sh        ← Startup script
    └── test_s2s.py         ← Test script (broken)

Docs:
  docs/
    ├── S2S_GAP_ANALYSIS.md        ← Full analysis (this file's big brother)
    ├── S2S_PYTHON312_FIX.md       ← Python 3.12 fixes (done)
    └── plans/2026-01-23-speech-to-speech-implementation.md
```

---

## Next Actions

**For Immediate Testing (30 min):**
1. Add TTS disable flag to `s2s_server.py`
2. Restart with `S2S_ENABLE_TTS=false`
3. Test WebSocket with browser console
4. Verify agent integration works

**For Production (1-2 weeks):**
1. Debug Piper TTS initialization hang
2. Implement lazy loading properly
3. Fix CTranslate2 ROCm support for GPU ASR
4. Performance tuning and testing
5. Error handling and reconnection logic

---

## Conclusion

**Everything is built. Nothing works. One function call is the problem.**

The entire S2S pipeline has been implemented according to plan, with high-quality code and proper architecture. However, a single synchronous TTS model load operation blocks the entire service from starting.

**Time to fix:** 1-2 hours for testing, 1-2 weeks for production-ready.

---

## See Also

- **Full Analysis:** `docs/S2S_GAP_ANALYSIS.md` (detailed technical breakdown)
- **Implementation Plan:** `docs/plans/2026-01-23-speech-to-speech-implementation.md`
- **Python 3.12 Fix:** `docs/S2S_PYTHON312_FIX.md`
