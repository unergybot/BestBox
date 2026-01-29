# Voice Chat UI Design - Main Page Integration

**Date:** 2026-01-28
**Status:** Approved
**Goal:** Integrate voice chat with text display into localhost:3000 main page

## Overview

Replace the CopilotKit sidebar on the main page with a voice chat interface that shows ASR transcripts and agent responses as text, while TTS plays in the background with optional mute control.

## Requirements

1. **Chat-style UI**: User messages and agent responses in conversation format
2. **Final transcripts only**: Show complete ASR results, not live streaming
3. **Voice + Text**: Display text immediately, play TTS in background
4. **Mute TTS toggle**: User can disable voice output while keeping text
5. **Main page integration**: Replace CopilotKit sidebar at localhost:3000 (/en and /zh)
6. **Keep /voice page**: Preserve existing /voice page for testing

## Architecture

### Component Hierarchy

```
app/[locale]/page.tsx
├── VoiceChatPanel (new)
│   ├── useLiveKitRoom hook (reuse existing)
│   ├── ChatMessageList (new)
│   │   └── ChatMessage components
│   ├── VoiceControls (new)
│   │   ├── Mic toggle
│   │   ├── Mute TTS button
│   │   └── Connection status
│   └── TypingIndicator (new)
```

### Key Technical Decisions

1. **Reuse LiveKit infrastructure**: Use existing `useLiveKitRoom` hook and LiveKit connection
2. **State management**: Local component state for messages, React refs for streaming
3. **Message model**: Simple `{role: 'user' | 'assistant', content: string, timestamp: Date}`
4. **No CopilotKit dependency**: Pure React components for cleaner implementation

### Data Flow

```
ASR Final Transcript
    ↓
User Message Added to Chat
    ↓
LLM Processing (via LiveKit)
    ↓
Agent Response Streaming → Update Chat
    ↓
TTS Audio Plays (unless muted)
```

## Component Design

### VoiceChatPanel Component

**Props:**
```typescript
interface VoiceChatPanelProps {
  serverUrl: string;      // LiveKit server URL
  token: string;          // Room token
  locale: string;         // 'en' | 'zh'
  onClose?: () => void;   // Optional close handler
}
```

**Internal State:**
```typescript
- messages: Message[]           // Chat history
- isTTSMuted: boolean           // TTS mute state
- isProcessing: boolean         // Agent is thinking/responding
- currentTranscript: string     // Temporary holder for transcripts
```

**Message Processing:**

1. **ASR Final Event**:
   - Create user message: `{role: 'user', content: transcript, timestamp: new Date()}`
   - Append to messages array
   - Clear currentTranscript

2. **Agent Response Stream**:
   - Create or update assistant message
   - Append each token to content
   - UI re-renders showing streaming text

3. **TTS Audio**:
   - If `isTTSMuted === true`, skip playback
   - Otherwise, LiveKit handles audio track automatically

## Message Display

### ChatMessage Component

**User Message (right-aligned, blue):**
```tsx
<div className="flex justify-end">
  <div className="max-w-[80%] rounded-lg p-4 bg-blue-600 text-white">
    <div className="flex items-center gap-2 mb-1">
      <span>👤</span>
      <span className="text-xs opacity-70">{timestamp}</span>
    </div>
    <div className="whitespace-pre-wrap">{content}</div>
  </div>
</div>
```

**Agent Message (left-aligned, gray):**
```tsx
<div className="flex justify-start">
  <div className="max-w-[80%] rounded-lg p-4 bg-gray-100 text-gray-900">
    <div className="flex items-center gap-2 mb-1">
      <span>🤖</span>
      <span className="text-xs opacity-70">{timestamp}</span>
    </div>
    <div className="whitespace-pre-wrap">{content}</div>
  </div>
</div>
```

### Streaming Effect

- Find or create latest assistant message
- Append new tokens to content
- React re-renders automatically
- Auto-scroll keeps latest text visible

### Visual Indicators

- **Listening**: 🎤 Microphone icon pulses
- **Processing**: "🤖 Thinking..." placeholder
- **Speaking**: Subtle animation on agent message (if TTS playing)
- **Muted**: 🔇 icon when TTS disabled

## Controls & Interactions

### Control Panel (Header)

```tsx
<div className="flex items-center justify-between p-4 border-b">
  <h2 className="text-xl font-bold">
    {locale === 'zh' ? '语音助手' : 'Voice Assistant'}
  </h2>
  <div className="flex items-center gap-2">
    {/* Connection Status */}
    <StatusDot color={isConnected ? 'green' : 'red'} />

    {/* Mic Toggle */}
    <button onClick={() => setMicEnabled(!micEnabled)}>
      {micEnabled ? '🎤' : '🔇'}
    </button>

    {/* Mute TTS Toggle */}
    <button onClick={() => setIsTTSMuted(!isTTSMuted)}>
      {isTTSMuted ? '🔇 TTS' : '🔊 TTS'}
    </button>

    {/* Clear Chat */}
    <button onClick={clearMessages}>🗑️</button>
  </div>
</div>
```

### User Interactions

1. **Speaking**:
   - Mic auto-enabled on connect
   - User speaks naturally (no push-to-talk)
   - Visual feedback: pulsing mic icon
   - VAD (Voice Activity Detection) handles segmentation

2. **Muting TTS**:
   - Click "🔊 TTS" → "🔇 TTS"
   - Text continues to appear
   - Audio playback suppressed
   - State persists during session

3. **Connection Management**:
   - Auto-connect on mount
   - Show "Connecting..." state
   - Error banner if connection fails
   - Reconnect button on disconnect

4. **Chat Management**:
   - Auto-scroll to latest message
   - Manual scroll up to read history
   - Clear button resets conversation

## Main Page Integration

### Changes to `app/[locale]/page.tsx`

**Remove:**
- `CopilotKit` wrapper
- `CopilotSidebar` component
- `VoiceInput` component

**Add Token Fetching:**
```typescript
const [voiceToken, setVoiceToken] = useState<string | null>(null);
const [isLoadingToken, setIsLoadingToken] = useState(true);

useEffect(() => {
  async function fetchToken() {
    const roomName = `bestbox-main-${Date.now()}`;

    // Dispatch agent to room
    await fetch('/api/livekit/dispatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roomName }),
    });

    // Wait for agent to join
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Get user token
    const response = await fetch('/api/livekit/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        roomName,
        participantName: `user-${Date.now()}`
      }),
    });

    const data = await response.json();
    setVoiceToken(data.token);
    setIsLoadingToken(false);
  }

  fetchToken();
}, []);
```

### Layout Structure

```tsx
<div className="flex h-screen">
  {/* Main Content (left) */}
  <div className="flex-1 overflow-auto">
    <DashboardContent locale={locale} />
  </div>

  {/* Voice Chat Sidebar (right) */}
  <div className="w-96 border-l shadow-lg bg-white">
    {isLoadingToken ? (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin text-4xl mb-4">⚙️</div>
          <p>Connecting...</p>
        </div>
      </div>
    ) : voiceToken ? (
      <VoiceChatPanel
        serverUrl={process.env.NEXT_PUBLIC_LIVEKIT_URL!}
        token={voiceToken}
        locale={locale}
      />
    ) : (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-red-600">
          <p>❌ Connection failed</p>
          <button onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      </div>
    )}
  </div>
</div>
```

## Localization

**Translation Keys** (add to `messages/en.json` and `messages/zh.json`):

```json
{
  "VoiceChat": {
    "title": "Voice Assistant",
    "connecting": "Connecting...",
    "connected": "Connected",
    "disconnected": "Disconnected",
    "listening": "Listening...",
    "processing": "Thinking...",
    "micEnabled": "Microphone on",
    "micDisabled": "Microphone off",
    "ttsEnabled": "Voice on",
    "ttsMuted": "Voice muted",
    "clearChat": "Clear conversation",
    "connectionError": "Connection failed. Please refresh."
  }
}
```

Chinese translations:
```json
{
  "VoiceChat": {
    "title": "语音助手",
    "connecting": "连接中...",
    "connected": "已连接",
    "disconnected": "已断开",
    "listening": "聆听中...",
    "processing": "思考中...",
    "micEnabled": "麦克风开启",
    "micDisabled": "麦克风关闭",
    "ttsEnabled": "语音开启",
    "ttsMuted": "语音静音",
    "clearChat": "清空对话",
    "connectionError": "连接失败，请刷新页面"
  }
}
```

## Files to Create/Modify

### New Files
- `components/VoiceChatPanel.tsx` - Main voice chat component
- `components/ChatMessage.tsx` - Individual message component
- `components/VoiceControls.tsx` - Control buttons (mic, TTS mute, clear)
- `components/TypingIndicator.tsx` - "Thinking..." animation

### Modified Files
- `app/[locale]/page.tsx` - Remove CopilotKit, add VoiceChatPanel
- `messages/en.json` - Add VoiceChat translations
- `messages/zh.json` - Add VoiceChat translations (Chinese)

### Unchanged Files
- `app/[locale]/voice/page.tsx` - Keep for testing
- `hooks/useLiveKitRoom.ts` - Reuse as-is
- `components/LiveKitVoicePanel.tsx` - Keep for /voice page

## Testing Checklist

- [ ] Voice chat appears on main page (both /en and /zh)
- [ ] ASR transcripts show as user messages
- [ ] Agent responses stream as text
- [ ] TTS plays in background by default
- [ ] Mute TTS button stops audio (text continues)
- [ ] Mic toggle controls microphone
- [ ] Clear button resets conversation
- [ ] Auto-scroll to latest message
- [ ] Connection status indicator works
- [ ] /voice page still works unchanged
- [ ] Both English and Chinese locales work

## Performance Considerations

**Expected Latency:**
- ASR: ~1s (Whisper on CPU)
- Text appears: Immediately after ASR
- LLM first token: ~1-2s (direct local LLM)
- TTS starts: ~0.05s per word (amy-low model)
- Total perceived latency: ~2-3s from speech end to response start

**Optimizations:**
- Streaming text reduces perceived latency
- TTS plays in background, non-blocking
- LocalTTS uses fast amy-low model
- Connection persists between messages

## Success Criteria

1. Users can speak and see transcripts immediately as chat messages
2. Agent responses appear as streaming text
3. TTS plays automatically but can be muted
4. Experience feels natural and responsive
5. Works identically in English and Chinese
6. /voice page remains available for testing raw LiveKit
