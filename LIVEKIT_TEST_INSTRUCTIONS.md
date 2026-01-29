# LiveKit Voice Assistant - Testing Instructions

**Date:** 2026-01-26
**Status:** ✅ All services running with instrumentation

---

## What We Fixed

### 1. ✅ Re-enabled LangGraph Integration
- Removed debug force-disable
- Agent now uses real BestBox multi-agent system (ERP/CRM/IT/OA)

### 2. ✅ Added Comprehensive Timing Instrumentation
All timing is now **LOUD and VISIBLE** in logs:

**STT (Speech-to-Text):**
- `🎤 STT: Started receiving audio` - When audio starts
- `📝 STT: Partial transcript (XXms)` - Interim results with timing
- `✅ STT: Transcription complete in XXms` - Final transcript with total time

**Agent Processing:**
- `🎯 AGENT: Processing user input: 'text...'` - Start
- `✅ AGENT: Response generated in XXms` - Completion with timing
- `❌ AGENT: Processing failed` - Errors (LOUD!)

**TTS (Text-to-Speech):**
- `🔊 TTS: Synthesizing 'text...'` - Start
- `✅ TTS: Synthesized XXms audio in XXms` - Complete with metrics
- `❌ TTS: Synthesis timeout` - Errors (LOUD!)

### 3. ✅ Fixed TTS Crash
- Added proper AudioEmitter lifecycle management
- TTS now works without "AudioEmitter isn't started" error

### 4. ✅ Created Diagnostic Tool
- `scripts/diagnose_livekit.py` - Tests all components
- Measures latency at every stage
- NO SILENT FAILURES

---

## Current Performance Baseline

From `scripts/diagnose_livekit.py`:

| Component | Latency | Status |
|-----------|---------|--------|
| LLM Server | 364ms | ✅ Fast |
| STT Processing | 684ms (for 3s audio) | ✅ OK |
| TTS Synthesis | 408ms (for 1.3s audio) | ✅ OK |
| **Agent Total** | **3880ms** | ⚠️ **SLOW!** |

**Problem:** Agent is 10x slower than raw LLM (3880ms vs 364ms)
- This suggests LangGraph routing/tool overhead
- Needs optimization

---

## How to Test (MANUAL - Real User Experience)

### Prerequisites

Check all services are running:

```bash
# 1. Check LiveKit server
docker ps | grep livekit-server
# Should show: livekit-server running on port 7880

# 2. Check LLM server
curl http://localhost:8080/health
# Should return: OK

# 3. Check LiveKit agent
ps aux | grep livekit_agent.py | grep -v grep
# Should show: python services/livekit_agent.py dev

# 4. Check frontend
curl http://localhost:3000 2>/dev/null | head -5
# Should return: HTML

# If any are missing, start them:
# LiveKit: ./scripts/start-livekit.sh
# LLM: ./scripts/start-llm.sh
# Agent: python services/livekit_agent.py dev
# Frontend: cd frontend/copilot-demo && npm run dev
```

### Test Steps

1. **Open Voice UI**
   ```
   http://localhost:3000/en/voice
   ```

2. **Watch Agent Logs** (in separate terminal)
   ```bash
   tail -f agent_debug.log | grep -E "STT:|AGENT:|TTS:|🎤|🎯|🔊|✅|❌"
   ```

3. **Allow Microphone**
   - Browser will ask for microphone permission
   - Click "Allow"

4. **Wait for Connection**
   - UI should show "🟢 Connected"
   - Agent log should show: "NEW SESSION REQUESTED"

5. **Speak a Test Query**

   **ERP Test:**
   ```
   "Show me the top 5 vendors"
   ```

   **CRM Test:**
   ```
   "Tell me about customer ABC Corp"
   ```

   **IT Ops Test:**
   ```
   "Check server status"
   ```

   **General Test:**
   ```
   "What's the weather today?"
   ```

6. **Watch the Logs** (This is the REAL test!)

   You should see (with timing):
   ```
   🎤 STT: Started receiving audio
   📝 STT: Partial transcript (500ms): 'Show me...'
   ✅ STT: Transcription complete in 750ms
   📝 STT: Transcript: 'Show me the top 5 vendors'

   🎯 AGENT: Processing user input: 'Show me the top 5 vendors'
   ⏱️  TIMING: Agent processing started
   ✅ AGENT: Response generated in 2500ms
   ⏱️  TIMING: Agent processing completed (2.500s)

   🔊 TTS: Synthesizing 'Here are the top 5 vendors...'
   ✅ TTS: Synthesized 2000ms audio in 400ms
   ```

7. **Verify You Hear Response**
   - Agent voice should play in browser
   - Response should be relevant to your query

8. **Check UI Display**
   - Transcript should appear
   - Agent response text should appear
   - Connection should stay green

---

## What to Watch For

### ✅ SUCCESS Indicators:
- Connection establishes (🟢 green)
- Transcript appears quickly (<1 second)
- Agent responds with relevant answer
- Voice plays in browser
- All emoji logs show up (🎤 🎯 🔊 ✅)

### ❌ FAILURE Indicators:
- No connection (🔴 red stays)
- No transcript after speaking
- No agent response after 5+ seconds
- No voice audio
- ❌ emoji in logs (errors!)
- Silence - NO RESPONSE AT ALL

### 📊 Performance Issues:
- STT > 1000ms = Too slow
- Agent > 5000ms = Way too slow (investigate)
- TTS > 1000ms = Too slow
- **Total latency > 7 seconds = UNACCEPTABLE**

---

## Troubleshooting

### Problem: No Transcript
**Check:**
```bash
tail -f agent_debug.log | grep "STT:"
```

**Look for:**
- `🎤 STT: Started receiving audio` - If missing, audio not reaching agent
- `❌ STT:` - If present, check error message

**Fix:**
- Check microphone permission in browser
- Verify audio input device works
- Check browser console for errors

---

### Problem: No Agent Response
**Check:**
```bash
tail -f agent_debug.log | grep "AGENT:"
```

**Look for:**
- `🎯 AGENT: Processing user input` - If missing, STT didn't produce transcript
- `❌ AGENT:` - If present, check error message
- Timing > 5000ms - Agent is too slow

**Fix:**
- Check LLM server: `curl http://localhost:8080/health`
- Check agent process: `ps aux | grep livekit_agent`
- Look for Python exceptions in logs

---

### Problem: No Audio Output
**Check:**
```bash
tail -f agent_debug.log | grep "TTS:"
```

**Look for:**
- `🔊 TTS: Synthesizing` - If missing, agent didn't send response
- `❌ TTS: Synthesis timeout` - TTS is failing
- `❌ TTS: No audio generated` - TTS returned empty

**Fix:**
- Check browser audio not muted
- Check system volume
- Verify TTS model loaded (look for "Shared TTS engine initialized")
- Check browser console for WebRTC errors

---

### Problem: Agent Too Slow (>5s)
**Check:**
```bash
tail -f agent_debug.log | grep "TIMING:"
```

**Look for:**
- `TIMING: Agent processing started`
- `TIMING: Agent processing completed (X.XXXs)`
- Calculate difference

**Causes:**
- LangGraph routing overhead (most likely)
- Tool calls taking too long
- LLM server slow
- Network latency

**Fix:**
1. Test raw LLM speed: `scripts/diagnose_livekit.py`
2. If LLM fast but agent slow → LangGraph problem
3. Check which agent it routed to (ERP/CRM/IT/OA)
4. Check if it's calling tools (database queries)

---

## Next Steps - Performance Optimization

Based on test results, we can optimize:

1. **If STT is slow:**
   - Switch to faster Whisper model (distil-small → tiny)
   - Or use cloud STT API
   - Or optimize VAD settings

2. **If Agent is slow:**
   - Profile LangGraph execution
   - Optimize routing logic
   - Cache tool results
   - Use faster LLM for simple queries

3. **If TTS is slow:**
   - Switch to faster TTS engine
   - Or use cloud TTS API
   - Or reduce audio quality

4. **Add Responsive Feedback:**
   - Show "🤔 Thinking..." while agent processes
   - Stream agent response as it generates
   - Play audio chunks as they're ready (already doing this)

---

## Success Criteria

Test is successful if:
- ✅ Connection works immediately
- ✅ Transcript appears within 1 second of speaking
- ✅ Agent responds within 3-5 seconds total
- ✅ Voice audio plays clearly
- ✅ Can have multi-turn conversation
- ✅ All timing logs appear correctly
- ✅ No ❌ errors in logs

---

## Files Modified

1. `services/livekit_agent.py` - Re-enabled LangGraph, added timing
2. `services/livekit_local.py` - Added STT/TTS timing instrumentation
3. `scripts/diagnose_livekit.py` - New diagnostic tool
4. `scripts/test_livekit_e2e_live.py` - Automated E2E test (work in progress)

---

**NOW GO TEST IT! Speak to the voice assistant and watch the logs.**

The most important test is: **Does it respond when you speak?**

If YES → Check timing, optimize slow parts
If NO → Check logs for ❌ errors, fix the broken component
