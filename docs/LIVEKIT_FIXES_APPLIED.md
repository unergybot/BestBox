# LiveKit → CopilotKit Fixes Applied

**Date:** 2026-01-29
**Status:** ✅ All fixes applied, ready for testing

## Summary

Applied 5 critical fixes to enable ASR transcripts and agent responses to appear in the CopilotKit chat box when using LiveKit voice integration.

## Changes Made

### Backend Changes (`services/livekit_agent.py`)

#### 1. Added Text Greeting on Session Start
**Location:** Lines 949-962 (main session) and 973-983 (fallback session)

**What Changed:**
- Added data channel message to send greeting text after audio greeting
- Greeting appears in CopilotKit chat box when voice session starts

**Code Added:**
```python
# Send text greeting to CopilotKit chat
greeting_text = "你好!我是BestBox智能助手,很高兴为您服务。"
payload = json.dumps({
    "type": "agent_response",
    "text": greeting_text,
    "timestamp": time.time()
}).encode('utf-8')
await ctx.room.local_participant.publish_data(payload, reliable=True)
logger.info(f"✅ Greeting text sent: {greeting_text}")
```

#### 2. Added Agent Response Session Hook
**Location:** Lines 905-927 (after transcript hooks)

**What Changed:**
- Added `@session.on("agent_speech_committed")` hook
- Sends agent responses via data channel when agent finishes speaking
- Sends completion marker to trigger state reset

**Code Added:**
```python
@session.on("agent_speech_committed")
async def on_agent_speech_committed(response: str):
    logger.info(f"🤖 Agent response finalized: {response[:100]}...")
    if response and response.strip():
        # Send agent response
        payload = json.dumps({
            "type": "agent_response",
            "text": response,
            "timestamp": time.time()
        }).encode('utf-8')
        await ctx.room.local_participant.publish_data(payload, reliable=True)

        # Send completion marker
        await asyncio.sleep(0.1)
        complete_payload = json.dumps({
            "type": "agent_response_complete",
            "timestamp": time.time()
        }).encode('utf-8')
        await ctx.room.local_participant.publish_data(complete_payload, reliable=True)
        logger.info("✅ Agent response sent via data channel")
```

### Frontend Changes

#### 3. Reset State on Disconnect (`hooks/useLiveKitRoom.ts`)
**Location:** Lines 104-110

**What Changed:**
- Added state reset when room disconnects
- Clears transcript and agent response to prepare for next session

**Code Modified:**
```typescript
const handleDisconnected = () => {
  console.log('[LiveKit] Disconnected from room');
  setIsConnected(false);
  setIsConnecting(false);
  setAgentIsSpeaking(false);
  setTranscript('');  // ← ADDED
  setAgentResponse('');  // ← ADDED
};
```

#### 4. Reset Agent Response on Completion (`hooks/useLiveKitRoom.ts`)
**Location:** Lines 245-251

**What Changed:**
- Reset `agentResponse` state when `agent_response_complete` received
- Ensures callbacks fire correctly for next response
- Uses timeout to ensure final callback fires first

**Code Modified:**
```typescript
} else if (data.type === 'agent_response_complete') {
  // Response finished - reset for next interaction
  console.log('[LiveKit] Agent response complete');
  // Brief delay to ensure final callback fires, then reset
  setTimeout(() => {
    setAgentResponse('');
  }, 100);
}
```

#### 5. Improved Callback Robustness (`components/LiveKitVoiceButton.tsx`)
**Location:** Lines 128-143 (transcript) and Lines 136-149 (response)

**What Changed:**
- Added trimming for better comparison
- Added debug logging to track callback execution
- Ensured callbacks fire on any non-empty content change

**Code Modified:**
```typescript
// Transcript callback
const lastTranscriptRef = useRef('');
useEffect(() => {
    const trimmed = transcript.trim();
    const lastTrimmed = lastTranscriptRef.current.trim();

    if (trimmed && trimmed !== lastTrimmed) {
        lastTranscriptRef.current = transcript;
        onTranscript?.(transcript);
        console.log('[LiveKitVoiceButton] Calling onTranscript with:', transcript);
    }
}, [transcript, onTranscript]);

// Response callback
const lastResponseRef = useRef('');
useEffect(() => {
    const trimmed = agentResponse.trim();
    const lastTrimmed = lastResponseRef.current.trim();

    if (trimmed && trimmed !== lastTrimmed) {
        lastResponseRef.current = agentResponse;
        onResponse?.(agentResponse);
        console.log('[LiveKitVoiceButton] Calling onResponse with:', agentResponse.substring(0, 50) + '...');
    }
}, [agentResponse, onResponse]);
```

## Data Flow After Fixes

### User Speaks → Transcript Appears

```
1. User speaks into mic
2. LiveKit STT processes audio
3. session.on("transcript_finished") fires
4. Data channel sends: {"type": "user_transcript", "text": "..."}
5. Frontend useLiveKitRoom receives data
6. setTranscript(text) updates state
7. LiveKitVoiceButton useEffect detects change
8. onTranscript callback fires
9. VoiceInput.handleTranscript receives text
10. appendMessage adds to CopilotKit chat ✅
```

### Agent Responds → Response Appears

```
1. Agent generates response via LLM
2. session.on("agent_speech_committed") fires ← NEW!
3. Data channel sends: {"type": "agent_response", "text": "..."}
4. Frontend useLiveKitRoom receives data
5. setAgentResponse(prev + text) accumulates
6. LiveKitVoiceButton useEffect detects change ← IMPROVED!
7. onResponse callback fires
8. VoiceInput.handleResponse receives text
9. appendMessage adds to CopilotKit chat ✅
10. Completion marker received
11. setAgentResponse('') resets for next turn ← NEW!
```

### Session Starts → Greeting Appears

```
1. User clicks voice button
2. LiveKit room connects
3. Agent enters session
4. generate_greeting_audio() plays beep
5. Data channel sends: {"type": "agent_response", "text": "你好!..."} ← NEW!
6. Frontend processes as agent response
7. Greeting appears in CopilotKit chat ✅
```

## Testing Steps

### 1. Restart Services

```bash
# Terminal 1: Restart LiveKit agent (to pick up backend changes)
pkill -f livekit_agent
./scripts/start-livekit-agent.sh dev

# Terminal 2: Restart frontend (to pick up React changes)
cd frontend/copilot-demo
npm run dev
```

### 2. Test Greeting

1. Open http://localhost:3000
2. Click voice button (microphone icon)
3. **Expected:** Should see "你好!我是BestBox智能助手,很高兴为您服务。" in chat
4. **Check:** Browser console should show `[LiveKit] Data received: agent_response`

### 3. Test User Transcript

1. Click voice button (turns red)
2. Speak: "你好" or "Hello"
3. Click button again to stop (mic off)
4. **Expected:** Your transcript appears in chat as user message
5. **Check:** Console shows:
   - `[LiveKit] User transcript: 你好`
   - `[LiveKitVoiceButton] Calling onTranscript with: 你好`

### 4. Test Agent Response

1. Wait for agent to process and respond
2. **Expected:** Agent response appears in chat as assistant message
3. **Check:** Console shows:
   - `[LiveKit] Agent response: ...`
   - `[LiveKitVoiceButton] Calling onResponse with: ...`
   - `[LiveKit] Agent response complete`

### 5. Test Multiple Turns

1. Speak another query
2. **Expected:** New transcript appears, old response is cleared
3. **Expected:** New agent response appears
4. **Check:** Each turn creates separate messages in chat

## Debugging

### Backend Logs

```bash
tail -f /home/unergy/BestBox/agent_debug.log | grep -E "(transcript|agent_response|Greeting)"
```

Look for:
- `🎤 User transcript finalized: ...`
- `✅ Greeting text sent: ...`
- `🤖 Agent response finalized: ...`
- `✅ Agent response sent via data channel`

### Frontend Console

Open DevTools → Console and look for:
- `[LiveKit] Data received: user_transcript`
- `[LiveKit] Data received: agent_response`
- `[LiveKitVoiceButton] Calling onTranscript with: ...`
- `[LiveKitVoiceButton] Calling onResponse with: ...`

### If Messages Don't Appear

1. **Check backend is sending:**
   ```bash
   grep "Data sent\|publish_data" agent_debug.log
   ```

2. **Check frontend is receiving:**
   - Open DevTools → Network → WS (WebSockets)
   - Find LiveKit connection
   - Check messages tab for data frames

3. **Check callbacks are wired:**
   ```javascript
   // In console:
   console.log('VoiceInput handlers:', window.voiceInputHandlers);
   ```

## Known Limitations

1. **Accumulated Responses:** If agent sends multiple chunks, they accumulate until completion marker
2. **Timeout Delay:** 100ms delay on reset to ensure callback fires - might cause brief visual delay
3. **Greeting Language:** Hardcoded to Chinese - could be made configurable

## Future Improvements

1. Make greeting language match session language setting
2. Add visual indicator when data channel is active
3. Implement retry logic if data channel publish fails
4. Add metrics for message delivery success rate

## Files Modified

### Backend
- `services/livekit_agent.py` - Added greeting text and session hook

### Frontend
- `hooks/useLiveKitRoom.ts` - Added state resets
- `components/LiveKitVoiceButton.tsx` - Improved callbacks

## Rollback Instructions

If issues occur, revert with:

```bash
cd /home/unergy/BestBox
git diff HEAD services/livekit_agent.py > /tmp/backend_changes.patch
git diff HEAD frontend/copilot-demo/ > /tmp/frontend_changes.patch
git checkout HEAD -- services/livekit_agent.py frontend/copilot-demo/
```

## Success Criteria

- ✅ Greeting appears in chat on connection
- ✅ User transcripts appear in chat after speaking
- ✅ Agent responses appear in chat
- ✅ Multiple conversation turns work correctly
- ✅ State resets properly between sessions
- ✅ No duplicate or missing messages

## Next Steps

1. Test all scenarios listed above
2. Monitor logs for any errors
3. Verify chat messages appear correctly
4. Update CLAUDE.md if everything works
5. Consider adding E2E tests for voice flow
