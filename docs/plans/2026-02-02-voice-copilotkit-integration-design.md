# Voice Input CopilotKit Integration Design

**Date:** 2026-02-02
**Status:** Ready for Implementation

## Problem

Voice input via S2S WebSocket correctly transcribes speech (ASR works), but:
1. User transcript doesn't appear in CopilotKit chat
2. Agent is not triggered via CopilotKit flow
3. S2S backend echoes "我收到了：..." instead of proper agent response

## Root Causes

1. **Stale closure bug** in `VoiceInput.tsx`: `handleTranscript` callback has empty dependency array, capturing stale `appendMessage` reference
2. **S2S backend calls agent directly** instead of letting CopilotKit handle it

## Solution: CopilotKit as Central Hub

Voice becomes just another input method. S2S only handles ASR, CopilotKit handles agent routing.

### Data Flow

```
User speaks → S2S WebSocket → ASR → asr_final to frontend
                                          ↓
                              VoiceInput.handleTranscript()
                                          ↓
                              appendMessage(user message)
                                          ↓
                              CopilotKit processes normally
                                          ↓
                              API route → Agent API :8000
                                          ↓
                              Response in CopilotKit chat
```

## Implementation Steps

### Step 1: Fix stale closure in VoiceInput.tsx

**File:** `frontend/copilot-demo/components/VoiceInput.tsx`

Change `handleTranscript` dependency array from `[]` to `[appendMessage]`:

```tsx
const handleTranscript = useCallback(async (transcript: string) => {
    if (!transcript) return;
    await appendMessage(
        new TextMessage({
            role: MessageRole.User,
            content: transcript,
        })
    );
    setText('');
    setInterimTranscript('');
    setIsSpeaking(false);
}, [appendMessage]);  // <-- Add appendMessage
```

### Step 2: Remove onResponse from VoiceButton

**File:** `frontend/copilot-demo/components/VoiceInput.tsx`

Remove `onResponse={handleResponse}` from VoiceButton since CopilotKit will handle responses:

```tsx
<VoiceButton
    language={locale}
    size="sm"
    showText={false}
    onTranscript={handleTranscript}
    // onResponse removed - CopilotKit handles responses
/>
```

Also remove or comment out the `handleResponse` callback since it's no longer needed.

### Step 3: S2S backend - ASR only mode

**File:** `services/speech/s2s_server.py`

Remove agent invocation after ASR finalization. In two places:

**Location 1:** `handle_audio_chunk` function (around line 556-559)
```python
# Remove these lines:
# asyncio.create_task(
#     run_agent_and_speak(ws, session, text)
# )
```

**Location 2:** `handle_control` function, `stop_listening` handler (around line 604-606)
```python
# Remove these lines:
# asyncio.create_task(
#     run_agent_and_speak(ws, session, text)
# )
```

The S2S server will now only:
- Receive audio
- Run ASR
- Send `asr_final` with transcript
- NOT call the agent

## Testing

1. Start services: `./scripts/start-all-services.sh`
2. Open frontend at localhost:3000
3. Click voice button, speak a query like "我们最大的供应商是谁"
4. Verify:
   - User message appears in chat
   - CopilotKit processes the request
   - Agent response appears (not "我收到了：...")

## Rollback

If issues occur, revert the three file changes. The S2S echo mode will continue working as a fallback.
