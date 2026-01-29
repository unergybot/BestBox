# LiveKit Audio Playback Fix

## Problem Summary

The LiveKit voice test page at `http://localhost:3000/en/voice` was experiencing audio playback issues where users could speak but received no audio response from the agent. 

### Root Cause

Browser autoplay policies require explicit user interaction before audio can be played. The errors in console were:

1. **AudioContext not allowed to start**: `The AudioContext was not allowed to start. It must be resumed (or created) after a user gesture on the page.`
2. **Audio playback blocked**: `NotAllowedError: play() failed because the user didn't interact with the document first.`
3. **Could not playback audio**: Same autoplay policy violation

## Solution Implemented

### 1. Audio Context Initialization with User Gesture

**File**: `frontend/copilot-demo/hooks/useLiveKitRoom.ts`

Added `room.startAudio()` call before connecting to LiveKit. This initializes the AudioContext properly:

```typescript
// CRITICAL: Start audio context before connecting (requires user gesture)
// This must be called in response to a user action (click, tap, etc.)
try {
  await room.startAudio();
  console.log('[LiveKit] Audio context started successfully');
} catch (audioError) {
  console.warn('[LiveKit] Failed to start audio context:', audioError);
  // Continue anyway - audio might work later
}

await room.connect(config.url, config.token);
```

### 2. Enhanced Audio Playback Error Handling

**File**: `frontend/copilot-demo/hooks/useLiveKitRoom.ts`

Improved the `handleTrackSubscribed` event handler to:
- Properly handle `NotAllowedError` exceptions
- Add automatic retry on next user interaction
- Provide clear console logging for debugging

```typescript
const playAudio = async () => {
  try {
    await audioElement.play();
    console.log('[LiveKit] Audio playback started successfully');
  } catch (e: any) {
    if (e.name === 'NotAllowedError') {
      console.warn('[LiveKit] Audio playback blocked by browser. Waiting for user interaction...');
      // Add click listener to resume playback on next user interaction
      const resumeAudio = async () => {
        try {
          await audioElement.play();
          console.log('[LiveKit] Audio playback resumed after user interaction');
          document.removeEventListener('click', resumeAudio);
        } catch (retryError) {
          console.error('[LiveKit] Failed to resume audio:', retryError);
        }
      };
      document.addEventListener('click', resumeAudio, { once: true });
    } else {
      console.error('[LiveKit] Failed to play audio:', e);
    }
  }
};
```

### 3. Disabled Auto-Connect

**File**: `frontend/copilot-demo/app/[locale]/voice/page.tsx`

Changed `autoConnect` from `true` to `false` to ensure connection only happens after explicit user interaction:

```typescript
<LiveKitVoicePanel
  serverUrl={liveKitUrl}
  token={token}
  title="BestBox 语音助手"
  autoConnect={false}  // Changed from true
  className="h-full"
/>
```

### 4. Improved UI/UX

**File**: `frontend/copilot-demo/components/LiveKitVoicePanel.tsx`

Enhanced the connection interface with:
- Large, prominent "Start Voice Session" button
- Clear visual hierarchy with centered layout
- Helpful instructions displayed before connection
- Audio ready notification after successful connection

```typescript
{!isConnected && !isConnecting && !error && (
  <div className="flex-1 flex items-center justify-center p-4">
    <div className="max-w-md text-center">
      <div className="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <span className="text-5xl">🎤</span>
      </div>
      <h3 className="text-2xl font-bold text-gray-800 mb-3">Ready to Start</h3>
      <button onClick={handleToggleConnection}>
        🎙️ Start Voice Session
      </button>
      {/* Instructions */}
    </div>
  </div>
)}
```

Added audio ready notification:
```typescript
{isAudioReady && isConnected && (
  <div className="mx-4 mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
    <p className="text-sm text-green-700">
      ✅ Audio system ready! Start speaking to interact with BestBox.
    </p>
  </div>
)}
```

## Testing Steps

1. **Open the voice page**: Navigate to `http://localhost:3000/en/voice`
2. **Verify initial state**: You should see a large "Start Voice Session" button with instructions
3. **Click the button**: This triggers the user gesture required by browsers
4. **Allow microphone**: Grant microphone permission when prompted
5. **Verify connection**: Should see "🟢 Connected" status and green "Audio system ready" notification
6. **Test speaking**: Speak into your microphone
7. **Verify response**: Agent should respond with audio output

## Technical Details

### Browser Autoplay Policies

Modern browsers (Chrome, Firefox, Safari) implement strict autoplay policies:
- AudioContext cannot start without user gesture
- Audio elements cannot play without user interaction
- These policies prevent unwanted audio/video playback on page load

### LiveKit Audio Lifecycle

1. **User clicks "Start Voice Session"** (user gesture)
2. **`room.startAudio()`** initializes AudioContext
3. **`room.connect()`** establishes WebRTC connection
4. **Remote audio tracks subscribed** when agent joins
5. **`track.attach()`** creates audio element
6. **`audioElement.play()`** starts playback (now allowed due to earlier user gesture)

### Error Recovery

If audio still fails to play after connection:
- Click anywhere on the page
- The event listener will retry audio playback
- This handles edge cases where initial gesture wasn't sufficient

## Files Modified

1. `/home/unergy/BestBox/frontend/copilot-demo/hooks/useLiveKitRoom.ts`
   - Added `room.startAudio()` before connect
   - Enhanced error handling for audio playback
   - Added automatic retry mechanism

2. `/home/unergy/BestBox/frontend/copilot-demo/components/LiveKitVoicePanel.tsx`
   - Improved connection UI with prominent start button
   - Added audio ready state tracking
   - Added success notification

3. `/home/unergy/BestBox/frontend/copilot-demo/app/[locale]/voice/page.tsx`
   - Disabled autoConnect to require explicit user interaction

## Verification

Services confirmed running:
- ✅ LiveKit Server: `ws://localhost:7880`
- ✅ LiveKit Agent: Multiple worker processes active
- ✅ Next.js Frontend: `http://localhost:3000`
- ✅ Voice Page: Accessible at `http://localhost:3000/en/voice`

## Expected Console Output

After applying fixes, you should see:

```
[LiveKit] Connecting to: ws://localhost:7880
[LiveKit] Audio context started successfully
[LiveKit] Connected to room
[LiveKit] Agent audio track subscribed
[LiveKit] Audio playback started successfully
[LiveKit] Connection successful
```

## Troubleshooting

If audio still doesn't work:

1. **Check browser console**: Look for any remaining errors
2. **Verify microphone permission**: Check browser settings
3. **Try clicking page**: If blocked, click anywhere to trigger retry
4. **Check LiveKit agent**: Ensure `services/livekit_agent.py` is running
5. **Verify token**: Check `/api/livekit/token` endpoint responds correctly

## Related Documentation

- [docs/E2E_LIVEKIT_INTEGRATION.md](./E2E_LIVEKIT_INTEGRATION.md)
- [docs/LIVEKIT_INTEGRATION.md](./LIVEKIT_INTEGRATION.md)
- [Chrome Autoplay Policy](https://developer.chrome.com/blog/autoplay/)
- [Web Audio API Autoplay](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices#autoplay_policy)
