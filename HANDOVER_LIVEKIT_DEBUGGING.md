# LiveKit Voice Integration - Debugging Handover Document

**Date:** 2026-01-26
**Status:** 🚧 IN PROGRESS - Core issue identified, test agent working
**Handover To:** Antigravity

---

## 🎯 Original Goal

Fix the LiveKit voice integration to provide fast, responsive speech-to-speech interaction with BestBox agents. The previous S2S system was working but too slow, needed to improve:
- ASR (Automatic Speech Recognition) speed
- TTS (Text-to-Speech) speed
- Agent response time
- User experience with responsive feedback
- Ability to queue long-running agent tasks

---

## 📊 Current Status Summary

### What's Working ✅
- **LiveKit server**: Running on port 7880 (Docker)
- **LLM server**: Running on port 8080, 364ms response time
- **Frontend**: Running on port 3000, connects to LiveKit
- **Test agent**: Successfully connects when user opens voice page
- **Agent dispatch**: Frontend properly dispatches "BestBoxVoiceAgent"

### What's Broken ❌
- **No audio playback**: User speaks but hears nothing back
- **Test tone fails**: Even a simple 440Hz test tone doesn't play
- **Agent crashes**: Main BestBox agent has multiple pipeline failures

### Root Cause Identified 🔍
**The agent IS being called (confirmed via logs), but fails when trying to publish audio back to LiveKit.**

---

## 🔬 Investigation Summary

### Timeline of Discovery

1. **Initial Problem**: User speaks into voice UI, gets no response (no text, no voice, nothing)

2. **First Hypothesis**: STT not working
   - Added comprehensive logging with emojis (🎤 🎯 🔊 ✅ ❌)
   - Found: STT was producing garbage transcripts ("Shum...", "Shire...")

3. **STT Fixes Applied**:
   - Changed language config from "zh" (Chinese) to "en" (English)
   - Upgraded model from `distil-small.en` to `base.en` for better accuracy
   - Fixed import errors in error handlers

4. **Second Hypothesis**: TTS not working
   - Found: TTS was crashing with "AudioEmitter isn't started" error
   - Fixed: Corrected TTS API usage (`initialize()` → `push()` → `flush()`)

5. **Third Hypothesis**: Agent not being called
   - Found: Agent was never entering the `entrypoint()` function
   - Discovered: Agent names didn't match (dispatch requested "BestBoxVoiceAgent" but agent registered as different names)

6. **Current Finding**: Agent connects but crashes when publishing audio
   - Created simple test agent that bypasses all complexity
   - Test agent successfully connects to room
   - Test agent crashes when trying to publish audio track
   - Error: `AttributeError: 'Room' object has no attribute 'wait_until_ready'` (FIXED)
   - New error expected: likely in audio publishing code

---

## 🛠️ Files Modified

### 1. `/home/unergy/BestBox/services/livekit_agent.py`
**Changes:**
- Line 98: Re-enabled LangGraph integration (removed force-disable)
- Line 101-128: Added timing instrumentation to `graph_wrapper()`
- Line 410: Changed STT config from `language="zh"` to `language="en"`
- Line 410: Changed model from `distil-small.en` to `base.en`
- Line 169: Fixed AIMessage import in error handler

**Purpose:** Enable real agent responses with better STT accuracy

### 2. `/home/unergy/BestBox/services/livekit_local.py`
**Changes:**
- Line 174-234: Added timing instrumentation to STT (`_run()` method)
- Line 291-361: Completely rewrote TTS `_run()` method to use correct AudioEmitter API
  - Old: `start_input()` → `push(SynthesizedAudio)` → `end_input()`
  - New: `initialize()` → `push(bytes)` → `flush()`

**Purpose:** Fix TTS crashes and add visibility into pipeline

### 3. `/home/unergy/BestBox/services/speech/asr.py`
**Changes:**
- Line 21: Changed default model from `distil-small.en` to `base.en`
- Line 24: Changed language from `""` (auto) to `"en"` (English)

**Purpose:** Better STT accuracy for English speech

### 4. `/home/unergy/BestBox/scripts/diagnose_livekit.py` (NEW)
**Purpose:** Comprehensive diagnostic tool that tests all components
- Tests: LiveKit server, LLM server, STT, TTS, LangGraph, Frontend
- Measures latency at each stage
- NO SILENT FAILURES - everything is loud and explicit
- Provides actionable fix suggestions

**Usage:**
```bash
python scripts/diagnose_livekit.py
```

### 5. `/home/unergy/BestBox/services/livekit_agent_simple_test.py` (NEW)
**Purpose:** Minimal test agent to isolate LiveKit publishing issues
- Bypasses all STT/LLM/TTS complexity
- Just connects and publishes a 440Hz test tone
- If tone plays → LiveKit works, problem is in pipeline
- If tone fails → LiveKit setup issue

**Usage:**
```bash
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret
python services/livekit_agent_simple_test.py dev
```

### 6. `/home/unergy/BestBox/LIVEKIT_TEST_INSTRUCTIONS.md` (NEW)
**Purpose:** Step-by-step manual testing guide with troubleshooting

---

## 🎯 Key Findings

### 1. Agent Name Mismatch (CRITICAL - NOW FIXED)
**Problem:**
- Frontend dispatch API requests agent named `"BestBoxVoiceAgent"` (line 73 in `app/api/livekit/dispatch/route.ts`)
- Original agent was registered with different names
- LiveKit couldn't match them, so agent was never called

**Fix:**
- All agents must use `@server.rtc_session(agent_name="BestBoxVoiceAgent")`
- Test agent now uses correct name

### 2. STT Model Too Aggressive
**Problem:**
- `distil-small.en` model rejected all speech due to low confidence
- Produced garbage: "Shum...", "Shire...", "Sure...."
- Log showed: "Log probability threshold is not met"

**Fix:**
- Upgraded to `base.en` model (better accuracy, still fast on CPU)
- Changed language from "zh" to "en"

### 3. TTS AudioEmitter API Wrong
**Problem:**
- Used incorrect API: `start_input()` / `end_input()`
- Correct API: `initialize()` / `push()` / `flush()`
- Referenced OpenAI TTS plugin for correct implementation

**Fix:**
- Completely rewrote `LocalTTSStream._run()` method
- Now matches OpenAI plugin pattern

### 4. Missing Environment Variables
**Problem:**
- Test agent failed to start without `LIVEKIT_URL` env var
- Need all three: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

**Fix:**
- Must export these before running agent:
```bash
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret
```

---

## 🔍 Current Debugging State

### What We Know For Sure
1. ✅ LiveKit server is running and healthy
2. ✅ Frontend connects to LiveKit successfully
3. ✅ Frontend dispatch API is called and creates rooms
4. ✅ Agent worker is registered with correct name ("BestBoxVoiceAgent")
5. ✅ Agent `entrypoint()` function IS being called (confirmed in logs)
6. ❌ Agent crashes when trying to publish audio

### Most Recent Error
```
AttributeError: 'Room' object has no attribute 'wait_until_ready'
```

**Status:** FIXED in test agent, but test not completed yet

### Next Expected Error
Likely in audio publishing code around line 32-57 of test agent:
- Creating AudioSource
- Creating LocalAudioTrack
- Publishing track
- Sending audio frames

---

## 📋 Recommended Next Steps (In Order)

### IMMEDIATE (Step 1)
**Test the simple test agent:**

1. Ensure test agent is running:
```bash
ps aux | grep livekit_agent_simple_test
```

2. Open voice page: http://localhost:3000/en/voice

3. Check logs for:
```bash
tail -f /tmp/test_agent.log | grep "CONNECTED\|Publishing\|Track published\|Test audio sent"
```

4. **Expected outcomes:**
   - ✅ Hear 440Hz tone for 2 seconds → LiveKit publishing works!
   - ❌ Agent crashes → Check error in logs, likely audio API issue
   - ❌ No tone, no crash → Audio reaches LiveKit but browser can't play it

### SHORT TERM (Step 2)
**If test tone works:**
- Problem is in main agent pipeline (STT/LLM/TTS)
- Use the instrumentation we added to trace where it fails
- Look for 🎤 🎯 🔊 ✅ ❌ emojis in logs

**If test tone fails:**
- Problem is in LiveKit audio publishing
- Check LiveKit server logs: `docker logs livekit-server`
- Check browser console for WebRTC errors
- Verify audio format (48kHz, mono, PCM16)

### MEDIUM TERM (Step 3)
**Fix the main BestBox agent:**

Current issues in `/home/unergy/BestBox/services/livekit_agent.py`:
1. No environment variables loaded (needs .env or explicit exports)
2. TTS may still have issues despite our fixes
3. LangGraph integration slow (3880ms vs 364ms raw LLM)

**Approach:**
1. Copy working audio publishing code from test agent
2. Test with hard-coded text (bypass STT/LLM)
3. Add STT back
4. Add LLM back
5. Verify each stage with logs

### LONG TERM (Step 4)
**Performance optimization:**

Based on diagnostic results:
- LLM: 364ms ✅ (fast)
- STT: 684ms for 3s audio ⚠️ (could be better)
- TTS: 408ms ✅ (acceptable)
- **Agent: 3880ms** ❌ (TOO SLOW!)

Agent is 10x slower than raw LLM → LangGraph routing overhead

**Options:**
- Profile LangGraph execution
- Cache tool results
- Use faster model for simple queries
- Implement streaming responses

---

## 🧪 Testing Checklist

### Test 1: Simple Test Agent (CURRENT PRIORITY)
```bash
# Start test agent
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret
python services/livekit_agent_simple_test.py dev

# Open browser
http://localhost:3000/en/voice

# Expected: Hear 440Hz tone for 2 seconds
```

**Status:** Agent connects but audio publishing not yet verified

### Test 2: Diagnostic Tool
```bash
python scripts/diagnose_livekit.py
```

**Status:** ✅ All services pass (11/11 tests)

**Results:**
- LLM: 364ms
- STT: 684ms (for 3s audio)
- TTS: 408ms
- Agent: 3880ms (too slow)

### Test 3: Main Agent (BLOCKED)
```bash
# Not working yet - depends on test agent success
python services/livekit_agent.py dev
```

---

## 📁 Important Files & Locations

### Logs
- `/home/unergy/BestBox/agent_debug.log` - Main agent logs
- `/tmp/test_agent.log` - Simple test agent logs
- `/home/unergy/BestBox/agent_livekit.log` - Agent startup logs

### Configuration
- `/home/unergy/BestBox/.env` - Environment variables (LIVEKIT_URL, etc.)
- `/home/unergy/BestBox/frontend/copilot-demo/.env.local` - Frontend config

### Key Source Files
- `services/livekit_agent.py` - Main voice agent (MODIFIED)
- `services/livekit_local.py` - STT/TTS adapters (MODIFIED)
- `services/livekit_agent_simple_test.py` - Test agent (NEW)
- `services/speech/asr.py` - ASR config (MODIFIED)
- `frontend/copilot-demo/app/api/livekit/dispatch/route.ts` - Agent dispatch

### Documentation
- `LIVEKIT_TEST_INSTRUCTIONS.md` - Manual testing guide (NEW)
- `HANDOVER_LIVEKIT_DEBUGGING.md` - This document (NEW)
- `docs/E2E_LIVEKIT_INTEGRATION.md` - Original integration docs

---

## 🐛 Known Issues

### Issue 1: Agent Audio Publishing (ACTIVE)
**Symptom:** Test agent connects but crashes when publishing audio
**Last Error:** `AttributeError: 'Room' object has no attribute 'wait_until_ready'`
**Status:** Fixed in code, needs testing
**Priority:** P0 (CRITICAL)

### Issue 2: Main Agent Not Working
**Symptom:** User speaks, no response
**Root Cause:** Multiple pipeline failures (STT, TTS, agent routing)
**Status:** Partially fixed, needs end-to-end test
**Priority:** P0 (CRITICAL)

### Issue 3: Agent Performance Slow
**Symptom:** Agent takes 3880ms vs 364ms for raw LLM
**Root Cause:** LangGraph routing/tool overhead
**Status:** Identified, not fixed
**Priority:** P1 (after basic functionality works)

### Issue 4: No User Feedback
**Symptom:** User doesn't know if system is working
**Status:** Instrumentation added to logs, not visible in UI
**Priority:** P2

---

## 💡 Expert Analysis (from consultation)

Based on expert debugging advice, we followed this systematic approach:

### Debug Hierarchy (Most to Least Common)
1. **ASR never triggers** (VAD / audio format issue) - ✅ INVESTIGATED
2. **Agent produces text, but TTS never fires** - ✅ FIXED
3. **Audio published, but wrong format** - 🔍 CURRENT FOCUS
4. **Agent not subscribed correctly** - ✅ VERIFIED OK
5. **Whisper model too slow** - ✅ MODEL UPGRADED

### Critical Insights
- Browser sends **stereo float32**, Whisper expects **mono int16**
- TTS outputs **float32**, LiveKit wants **int16 PCM 48kHz**
- Sample rate mismatches cause **silent playback with no error**
- Agent async tasks not awaited → loop exits early

### Recommended Approach (We Followed This)
1. ✅ **Step 1:** Bypass everything - test audio publishing only
2. 🔍 **Step 2:** Bypass STT - hard-code text input
3. ⏸️ **Step 3:** Bypass LLM - hard-code response
4. ⏸️ **Step 4:** Log every boundary

**Current Status:** Working on Step 1

---

## 🔧 How to Continue Debugging

### If Test Tone Works
```bash
# The problem is in the main agent pipeline
tail -f /home/unergy/BestBox/agent_debug.log | grep "🎤\|🎯\|🔊\|✅\|❌"

# Look for missing emojis - that's where it fails
```

### If Test Tone Fails
```bash
# Check LiveKit server logs
docker logs livekit-server | tail -50

# Check browser console (F12)
# Look for: WebRTC errors, audio context errors

# Check audio format
# LiveKit expects: 48kHz, mono, PCM16
```

### If Nothing Happens
```bash
# Check if agent is even being called
tail -f /tmp/test_agent.log | grep "CONNECTED"

# If not called, check agent name match
grep "agent_name" /tmp/test_agent.log
# Should show: "BestBoxVoiceAgent"
```

---

## 📞 Quick Reference Commands

### Start Test Agent
```bash
cd /home/unergy/BestBox
source activate.sh
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret
python services/livekit_agent_simple_test.py dev
```

### Check Services Status
```bash
# LiveKit server
docker ps | grep livekit-server

# LLM server
curl http://localhost:8080/health

# Frontend
curl http://localhost:3000 | head -5

# Test agent
ps aux | grep livekit_agent_simple_test | grep -v grep
```

### Monitor Logs
```bash
# Test agent
tail -f /tmp/test_agent.log

# Main agent
tail -f /home/unergy/BestBox/agent_debug.log | grep "🎤\|🎯\|🔊\|✅\|❌"

# LiveKit server
docker logs -f livekit-server
```

### Run Diagnostics
```bash
python scripts/diagnose_livekit.py
```

---

## 🎓 Key Learnings

1. **Agent name must match dispatch** - LiveKit can't route if names differ
2. **LiveKit API varies by version** - `wait_until_ready()` doesn't exist in some versions
3. **AudioEmitter API is specific** - Must use `initialize()` → `push()` → `flush()`
4. **Sample rates matter** - 48kHz for LiveKit, 16kHz for Whisper, 24kHz for TTS
5. **Silent failures are common** - Audio format mismatches cause no audio with no error
6. **Test in isolation first** - Bypass complexity to find root cause

---

## 📚 References

### Documentation
- LiveKit Python SDK: https://docs.livekit.io/agents/
- LiveKit AudioEmitter API: Check `livekit/agents/tts/tts.py`
- OpenAI TTS plugin: `/venv/lib/python3.12/site-packages/livekit/plugins/openai/tts.py`

### Related Files
- `docs/E2E_LIVEKIT_INTEGRATION.md` - Original integration docs
- `docs/LIVEKIT_DEPLOYMENT.md` - Deployment guide
- `docs/TESTING_GUIDE.md` - General testing guide

---

## ✅ Handover Checklist

Before continuing, verify:

- [ ] Test agent is running: `ps aux | grep livekit_agent_simple_test`
- [ ] LiveKit server is running: `docker ps | grep livekit-server`
- [ ] LLM server is running: `curl http://localhost:8080/health`
- [ ] Frontend is running: `curl http://localhost:3000`
- [ ] Environment variables are set: `echo $LIVEKIT_URL`
- [ ] You can access logs: `tail /tmp/test_agent.log`
- [ ] You understand the test agent purpose: Isolate LiveKit publishing

---

**NEXT ACTION:** Test the simple test agent by opening http://localhost:3000/en/voice and listening for a 440Hz tone. Report back whether you hear it or see errors in logs.

**Good luck! The core issue is very close to being solved. The agent IS connecting, we just need to fix the audio publishing.**

---

**End of Handover Document**
