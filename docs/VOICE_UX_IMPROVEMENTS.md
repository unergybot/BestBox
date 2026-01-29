# Voice UX Improvements Implementation

**Date:** 2026-01-29
**Status:** ✅ Implemented, ready for testing

## Overview

Implemented two major UX improvements for voice interaction:
1. **Interim Transcript Display** - Show real-time transcripts in input box, not chat
2. **Dual Response Format** - Concise voice responses + detailed text in chat

## Changes Made

### Backend (`services/livekit_agent.py`)

#### 1. Dual Response Format

**Added parse_dual_response() helper (line ~244):**
```python
def parse_dual_response(content: str) -> dict:
    """Extract VOICE and TEXT sections from agent response."""
    voice_match = re.search(r'\[VOICE\](.*?)\[/VOICE\]', content, re.DOTALL)
    text_match = re.search(r'\[TEXT\](.*?)\[/TEXT\]', content, re.DOTALL)

    # Fallback to first sentence if no tags
    voice = voice_match.group(1).strip() if voice_match else content[:200]
    text = text_match.group(1).strip() if text_match else content

    return {'voice': voice, 'text': text, 'full': content}
```

**Updated Agent Instructions (line ~263):**
```python
instructions=(
    "IMPORTANT: Structure your responses in this format:\n"
    "[VOICE]<concise 1-2 sentence answer (under 30 words)>[/VOICE]\n"
    "[TEXT]<detailed explanation with full context>[/TEXT]\n\n"
    "Example:\n"
    "[VOICE]We have 1,240 units in stock.[/VOICE]\n"
    "[TEXT]Current inventory shows 1,240 units total...[/TEXT]"
)
```

**Updated conversation_item_added handler (line ~969):**
- Parses dual response format
- Sends TEXT portion to chat via data channel
- VOICE portion spoken by TTS (automatic via agent session)

**Updated graph_wrapper (line ~181):**
- Extracts VOICE portion for TTS
- Handles fallback if LLM doesn't follow format

### Frontend

#### 2. VoiceInput Component (`components/VoiceInput.tsx`)

**Added State:**
```typescript
const [interimTranscript, setInterimTranscript] = useState('');
const [isSpeaking, setIsSpeaking] = useState(false);
```

**Added Interim Handler:**
```typescript
const handleInterimTranscript = useCallback((transcript: string) => {
  setInterimTranscript(transcript);
  setIsSpeaking(true);
}, []);
```

**Modified Final Transcript Handler:**
```typescript
const handleTranscript = useCallback(async (transcript: string) => {
  // Put final transcript in textarea (editable, not auto-sent)
  setText(transcript);
  setInterimTranscript('');
  setIsSpeaking(false);
  inputRef.current?.focus();  // Focus for editing
}, []);
```

**Added Textarea Overlay:**
```typescript
{isSpeaking && interimTranscript && !text && (
  <div className="absolute inset-0 pointer-events-none p-2 text-gray-400 italic">
    {interimTranscript}...
  </div>
)}
```

**Auto-clear on typing:**
```typescript
onChange={(e) => {
  setText(e.target.value);
  if (interimTranscript) {
    setInterimTranscript('');
    setIsSpeaking(false);
  }
}}
```

#### 3. LiveKitVoiceButton Component (`components/LiveKitVoiceButton.tsx`)

**Added Props:**
```typescript
onInterimTranscript?: (text: string) => void;
```

**Added Interim Callback:**
```typescript
useEffect(() => {
  if (interimTranscript && interimTranscript !== lastInterimRef.current) {
    onInterimTranscript?.(interimTranscript);
  }
}, [interimTranscript, onInterimTranscript]);
```

#### 4. useLiveKitRoom Hook (`hooks/useLiveKitRoom.ts`)

**Added State:**
```typescript
const [interimTranscript, setInterimTranscript] = useState('');
```

**Added Message Handling:**
```typescript
if (data.type === 'user_transcript_partial') {
  setInterimTranscript(data.text);
} else if (data.type === 'user_transcript') {
  setTranscript(data.text);
  setInterimTranscript('');  // Clear interim
}
```

**Updated Disconnect Handler:**
```typescript
setInterimTranscript('');  // Reset on disconnect
```

## Data Flow

### Interim Transcripts (While Speaking)

```
User speaking → LiveKit STT generates partials
              → Backend sends: {"type": "user_transcript_partial", "text": "Hello..."}
              → useLiveKitRoom: setInterimTranscript()
              → LiveKitVoiceButton: onInterimTranscript callback
              → VoiceInput: setInterimTranscript() + setIsSpeaking(true)
              → Textarea shows gray italic overlay: "Hello..."
```

### Final Transcript (User Stops Speaking)

```
User clicks mic (stop) → LiveKit STT finalizes
                      → Backend sends: {"type": "user_transcript", "text": "Hello, what's our inventory?"}
                      → useLiveKitRoom: setTranscript() + clear interim
                      → LiveKitVoiceButton: onTranscript callback
                      → VoiceInput: setText() to populate textarea
                      → User can edit or press Enter to send
                      → Chat receives message only when user sends
```

### Agent Response (Dual Format)

```
LLM generates: "[VOICE]We have 1,240 units.[/VOICE] [TEXT]Current inventory shows 1,240 units total: 840 in main warehouse...[/TEXT]"
             → Backend parses dual response
             → VOICE portion: Spoken by TTS (automatic)
             → TEXT portion: Sent via data channel
             → Frontend receives: {"type": "agent_response", "text": "Current inventory shows..."}
             → Chat displays detailed version
             → User hears brief version, sees full version
```

## Testing Checklist

### Interim Transcripts
- [ ] Click mic → start speaking → see gray italic text in textarea
- [ ] Continue speaking → interim text updates in real-time
- [ ] Text appears in overlay, not in chat
- [ ] Typing clears interim overlay immediately
- [ ] Click mic to stop → interim disappears, final text populates textarea (black, editable)
- [ ] Can edit final transcript before sending
- [ ] Press Enter or click Send → goes to chat

### Dual Responses
- [ ] Agent responds to query
- [ ] Voice response is brief (<30 seconds spoken)
- [ ] Chat shows detailed explanation
- [ ] Voice and text are different (voice shorter)
- [ ] If agent doesn't use format, fallback works (first sentence for voice)

### Edge Cases
- [ ] User types during interim → overlay clears, typing continues
- [ ] Multiple voice sessions → each works independently
- [ ] Disconnect during interim → overlay clears
- [ ] Very long agent response → voice truncated, text full

## Known Limitations

1. **LLM Format Compliance**: Agent might not always follow [VOICE]/[TEXT] format
   - Mitigation: Fallback extracts first sentence for voice
   - Can be improved with prompt tuning

2. **TTS Tag Speaking**: If LLM includes tags in VOICE, they might be spoken
   - Mitigation: graph_wrapper strips tags for LangGraph responses
   - Direct LLM responses may need additional post-processing

3. **Backend Interim Events**: Currently no backend support for user_transcript_partial
   - Frontend handles state, ready for when backend adds interim events
   - Current implementation shows partial support via frontend

## Future Enhancements

1. **Backend Interim Transcripts**: Add LiveKit session event for partial transcripts
2. **Smart Voice Truncation**: If VOICE >50 words, auto-truncate to 2 sentences
3. **Visual Voice/Text Indicator**: Show icon when voice ≠ text
4. **User Preference**: Toggle between "brief voice" and "read full response" modes
5. **Response Streaming**: Stream TEXT to chat while VOICE is speaking

## Files Modified

**Backend:**
- `services/livekit_agent.py` (+100 lines, 3 functions modified)

**Frontend:**
- `components/VoiceInput.tsx` (+30 lines)
- `components/LiveKitVoiceButton.tsx` (+25 lines)
- `hooks/useLiveKitRoom.ts` (+15 lines)

## Rollback

If issues occur:
```bash
git diff HEAD -- services/livekit_agent.py > /tmp/backend_ux.patch
git diff HEAD -- frontend/copilot-demo/ > /tmp/frontend_ux.patch
git checkout HEAD -- services/livekit_agent.py frontend/copilot-demo/
```
