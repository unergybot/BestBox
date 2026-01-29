# LiveKit → CopilotKit Integration Issues

**Date:** 2026-01-29
**Status:** Issues identified, fixes needed

## Summary

The main UI uses LiveKit voice integration (`NEXT_PUBLIC_USE_LIVEKIT=true`), but ASR transcripts and agent responses are not appearing in the CopilotKit chat sidebar. Additionally, there's no text greeting when the voice session starts.

## Architecture Flow

```
User speaks → LiveKit Agent → ASR finalizes → Data channel message
                ↓
Frontend useLiveKitRoom hook receives data
                ↓
LiveKitVoiceButton state updates (transcript, agentResponse)
                ↓
Callbacks fire: onTranscript, onResponse
                ↓
VoiceInput appendMessage to CopilotKit
```

## Issues Identified

### 1. **No Initial Voice Greeting Text**

**Location:** `services/livekit_agent.py:946-954`

**Current Behavior:**
- `generate_greeting_audio()` only plays a musical beep (C-E-G chord progression)
- No data channel message sent with greeting text
- CopilotKit chat box remains empty on connection

**Root Cause:**
The agent sends an audio greeting but doesn't send a corresponding text message via data channel:
```python
await generate_greeting_audio(ctx.room)  # Only audio, no text
```

**Expected Behavior:**
Should send both audio greeting AND text message like:
```python
payload = json.dumps({
    "type": "agent_response",
    "text": "你好!我是BestBox智能助手,很高兴为您服务。",
    "timestamp": time.time()
}).encode('utf-8')
await ctx.room.local_participant.publish_data(payload, reliable=True)
```

### 2. **ASR Transcripts May Not Reach CopilotKit**

**Locations:**
- Backend: `services/livekit_agent.py:888-897`
- Frontend: `hooks/useLiveKitRoom.ts:226-258`
- Integration: `components/LiveKitVoiceButton.tsx:128-143`

**Data Flow:**

Backend correctly sends transcript:
```python
@session.on("transcript_finished")
async def on_transcript_finished(transcript: str):
    payload = json.dumps({
        "type": "user_transcript",
        "text": transcript,
        "timestamp": time.time()
    }).encode('utf-8')
    await ctx.room.local_participant.publish_data(payload, reliable=True)
```

Frontend receives and processes:
```typescript
// useLiveKitRoom.ts:239-241
if (data.type === 'transcript' || data.type === 'user_transcript') {
  setTranscript(data.text);
}
```

Callback triggers:
```typescript
// LiveKitVoiceButton.tsx:129-134
useEffect(() => {
  if (transcript && transcript !== lastTranscriptRef.current) {
    lastTranscriptRef.current = transcript;
    onTranscript?.(transcript);
  }
}, [transcript, onTranscript]);
```

**Potential Issues:**
a) **State Reset Issue:** The `transcript` state might be getting reset between button presses, causing the callback not to fire
b) **Callback Reference:** `onTranscript` callback might not have stable reference, causing missed updates
c) **Empty Transcript:** ASR might be sending empty strings that don't trigger the condition

### 3. **Agent Responses Not Appearing in Chat**

**Location:** `hooks/useLiveKitRoom.ts:242-244`

**Current Behavior:**
```typescript
else if (data.type === 'agent_response') {
  setAgentResponse(prev => prev + data.text);  // ACCUMULATION
}
```

**Issue:**
- Agent responses are ACCUMULATED (`prev + data.text`)
- The state never resets between responses
- `LiveKitVoiceButton` only calls `onResponse` when `agentResponse` CHANGES
- After first response, subsequent responses might not trigger callback if state wasn't cleared

**Missing Reset Logic:**
- No reset when user starts new query
- No reset on `agent_response_complete`
- Causes stale data and missed callbacks

### 4. **No Agent Response Data Channel Hook**

**Location:** `services/livekit_agent.py:899-956`

**Observation:**
- Backend has `@session.on("transcript_finished")` hook for user speech (line 888)
- **NO equivalent hook for agent speech completion!**
- Agent responses rely on `BestBoxVoiceAgent.on_agent_speech_committed()` (line 452)
- But this method might not be called in all response modes

**Missing:**
```python
@session.on("agent_speech_committed")
async def on_agent_response(response_text: str):
    payload = json.dumps({
        "type": "agent_response",
        "text": response_text,
        "timestamp": time.time()
    }).encode('utf-8')
    await ctx.room.local_participant.publish_data(payload, reliable=True)
```

## Root Cause Analysis

### Why transcripts don't appear:

1. **Backend sends correct message** ✅ (line 892-897)
2. **Frontend receives message** ✅ (useLiveKitRoom handles DataReceived)
3. **State updates** ✅ (setTranscript called)
4. **Callback fires** ⚠️ **CONDITIONAL** (only if transcript changed)
5. **appendMessage called** ⚠️ **IF callback fires**

**Key Issue:** If transcript state is not properly managed (reset between recordings), the `transcript !== lastTranscriptRef.current` check might fail, preventing callback from firing.

### Why agent responses don't appear:

1. **Backend might not send message** ⚠️ (no session hook, only agent method)
2. **Frontend accumulates without reset** ❌ (`prev + data.text` with no clear)
3. **Callback might not fire** ❌ (state comparison fails due to accumulation)
4. **appendMessage not called** ❌

## Debugging Steps

### Check Backend Logs

```bash
tail -f /home/unergy/BestBox/agent_debug.log | grep -E "(transcript|agent_response|Data sent)"
```

Look for:
- `🎤 User transcript finalized: ...`
- `📡 Data sent: user_transcript - ...`
- `🤖 Agent:` or `📡 Data sent: agent_response - ...`

### Check Frontend Console

In browser DevTools console:
```javascript
// Enable detailed logging
localStorage.setItem('debug', 'livekit:*');
// Reload page
```

Look for:
- `[LiveKit] Data received: user_transcript`
- `[LiveKit] User transcript: ...`
- `[LiveKit] Agent response: ...`

### Test Data Channel Directly

Add to `useLiveKitRoom.ts` line 237:
```typescript
const handleDataReceived = (...args) => {
  console.log('[DEBUG] DataReceived event:', args);
  // ... existing code
};
```

## Recommended Fixes

### Fix 1: Add Text Greeting

`services/livekit_agent.py:946-954`:
```python
# After generate_greeting_audio
greeting_text = "你好!我是BestBox智能助手,很高兴为您服务。"
payload = json.dumps({
    "type": "agent_response",
    "text": greeting_text,
    "timestamp": time.time()
}).encode('utf-8')
await ctx.room.local_participant.publish_data(payload, reliable=True)
logger.info(f"✅ Greeting text sent: {greeting_text}")
```

### Fix 2: Reset Transcript State

`hooks/useLiveKitRoom.ts`: Add reset on disconnect/new session:
```typescript
const handleDisconnected = () => {
  setTranscript('');  // ADD THIS
  setAgentResponse('');  // ADD THIS
  // ... rest of existing code
};
```

### Fix 3: Reset Agent Response on Completion

`hooks/useLiveKitRoom.ts:246-248`:
```typescript
} else if (data.type === 'agent_response_complete') {
  console.log('[LiveKit] Agent response complete');
  // TRIGGER FINAL CALLBACK BEFORE RESET
  const finalResponse = agentResponse;
  if (finalResponse) {
    // Notify any listeners of complete response
    // (LiveKitVoiceButton will handle this via onResponse)
  }
  setAgentResponse('');  // ADD THIS - Reset for next interaction
}
```

### Fix 4: Add Agent Response Session Hook

`services/livekit_agent.py` after line 903:
```python
@session.on("agent_speech_committed")
async def on_agent_speech_committed(response: str):
    logger.info(f"🤖 Agent response finalized: {response[:100]}...")
    payload = json.dumps({
        "type": "agent_response",
        "text": response,
        "timestamp": time.time()
    }).encode('utf-8')
    await ctx.room.local_participant.publish_data(payload, reliable=True)

    # Send completion marker
    await asyncio.sleep(0.1)  # Brief delay
    complete_payload = json.dumps({
        "type": "agent_response_complete",
        "timestamp": time.time()
    }).encode('utf-8')
    await ctx.room.local_participant.publish_data(complete_payload, reliable=True)
```

### Fix 5: Improve Callback Robustness

`components/LiveKitVoiceButton.tsx:137-143`: Force callback on ANY non-empty change:
```typescript
useEffect(() => {
  // Trim whitespace for comparison
  const trimmed = agentResponse.trim();
  const lastTrimmed = lastResponseRef.current.trim();

  // Call on ANY content (even if same), as long as not empty
  // This ensures responses always reach CopilotKit
  if (trimmed && trimmed !== lastTrimmed) {
    lastResponseRef.current = agentResponse;
    onResponse?.(agentResponse);
  }
}, [agentResponse, onResponse]);
```

## Testing Checklist

- [ ] Start LiveKit server (`livekit-server`)
- [ ] Start LiveKit agent (`./scripts/start-livekit-agent.sh dev`)
- [ ] Start frontend (`cd frontend/copilot-demo && npm run dev`)
- [ ] Open browser to http://localhost:3000
- [ ] Click voice button - should see greeting in chat
- [ ] Speak test phrase - should see transcript in chat
- [ ] Wait for agent response - should see response in chat
- [ ] Check browser console for data received logs
- [ ] Check agent_debug.log for data sent logs

## Next Steps

1. Apply fixes in order (greeting → state reset → session hooks)
2. Test after each fix
3. Monitor logs on both backend and frontend
4. Verify messages flow through entire chain
5. Update CLAUDE.md with LiveKit integration status

## Related Files

- Backend: `services/livekit_agent.py`
- Data Channel Hook: `useLiveKitRoom.ts:226-258`
- Button Component: `LiveKitVoiceButton.tsx:128-143`
- Chat Integration: `VoiceInput.tsx:32-52`
- Main UI: `app/[locale]/page.tsx:26` (uses VoiceInput)
