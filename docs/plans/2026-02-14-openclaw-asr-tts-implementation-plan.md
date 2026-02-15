# OpenClaw BestBox ASR/TTS Implementation Plan

**Date:** 2026-02-14  
**Status:** Draft  
**Priority:** High  
**Estimated Duration:** 5-7 days  

## Overview

This document provides a detailed implementation plan for integrating BestBox's local ASR/TTS services into OpenClaw, enabling full voice conversation capabilities.

## Phase 1: Foundation (Day 1-2)

### 1.1 Create Extension Structure

**Location:** `/home/unergy/MyCode/openclaw/extensions/bestbox/`

**Tasks:**
- [ ] Create directory structure
- [ ] Initialize npm package
- [ ] Set up TypeScript configuration
- [ ] Create base configuration files

**Directory Structure:**
```
extensions/bestbox/
├── index.ts                    # Extension entry point
├── package.json                # Package manifest
├── tsconfig.json              # TypeScript config
├── openclaw.plugin.json       # Plugin manifest
├── src/
│   ├── config.ts              # Configuration schema
│   ├── types.ts               # Type definitions
│   ├── providers/
│   │   ├── asr-local.ts       # ASR HTTP client
│   │   ├── tts-local.ts       # TTS HTTP client
│   │   └── s2s-websocket.ts   # S2S WebSocket client
│   ├── clients/
│   │   ├── asr-client.ts      # ASR API client
│   │   ├── tts-client.ts      # TTS API client
│   │   └── s2s-client.ts      # S2S WebSocket client
│   └── voice-conversation.ts  # Conversation manager
├── test/
│   ├── asr-local.test.ts
│   ├── tts-local.test.ts
│   └── voice-conversation.test.ts
└── README.md
```

**Deliverables:**
- Extension skeleton with all files created
- TypeScript compilation working
- Basic configuration schema defined

### 1.2 Implement ASR Client

**File:** `src/clients/asr-client.ts`

**Tasks:**
- [ ] Create HTTP client for ASR service
- [ ] Implement audio file upload
- [ ] Handle response parsing
- [ ] Add error handling and retries

**API Methods:**
```typescript
class BestBoxASRClient {
  constructor(options: ASRClientOptions);
  
  // Transcribe audio file
  async transcribe(audioBuffer: Buffer, options?: TranscribeOptions): Promise<TranscriptionResult>;
  
  // Health check
  async health(): Promise<HealthStatus>;
  
  // Stream audio for real-time transcription
  async createStream(): Promise<ASRStream>;
}
```

**Deliverables:**
- Working ASR client
- Unit tests passing
- Error handling verified

### 1.3 Implement TTS Client

**File:** `src/clients/tts-client.ts`

**Tasks:**
- [ ] Create HTTP client for TTS service
- [ ] Implement text synthesis
- [ ] Support voice cloning
- [ ] Handle audio streaming

**API Methods:**
```typescript
class BestBoxTTSClient {
  constructor(options: TTSClientOptions);
  
  // Synthesize text to speech
  async synthesize(request: SynthesisRequest): Promise<SynthesisResult>;
  
  // Synthesize with voice cloning
  async synthesizeWithCloning(request: CloningRequest): Promise<SynthesisResult>;
  
  // Stream synthesis (for long text)
  async synthesizeStream(request: SynthesisRequest): AsyncIterable<AudioChunk>;
  
  // Health check
  async health(): Promise<HealthStatus>;
}
```

**Deliverables:**
- Working TTS client
- Voice cloning support
- Unit tests passing

## Phase 2: Provider Integration (Day 2-3)

### 2.1 ASR Provider Implementation

**File:** `src/providers/asr-local.ts`

**Tasks:**
- [ ] Implement `MediaUnderstandingProvider` interface
- [ ] Integrate with OpenClaw's media understanding system
- [ ] Register in provider registry
- [ ] Handle audio format conversion

**Integration Points:**
- Update `src/media-understanding/providers/index.ts`
- Add to provider registry
- Configure in media understanding settings

**Deliverables:**
- ASR provider working with OpenClaw
- Can transcribe voice messages
- Configuration examples provided

### 2.2 TTS Provider Implementation

**File:** `src/providers/tts-local.ts`

**Tasks:**
- [ ] Implement TTS provider pattern
- [ ] Add BestBox to TTS provider enum
- [ ] Update TTS configuration types
- [ ] Implement `bestboxTTS()` function

**Integration Points:**
- Update `src/config/types.tts.ts`
- Update `src/tts/tts-core.ts`
- Add to provider switch statement

**Deliverables:**
- TTS provider working with OpenClaw
- Can synthesize AI responses
- Configuration examples provided

### 2.3 Configuration Schema

**File:** `src/config.ts`

**Tasks:**
- [ ] Define configuration types
- [ ] Implement validation schema
- [ ] Add default values
- [ ] Document all options

**Configuration Schema:**
```typescript
export const BestBoxConfigSchema = z.object({
  enabled: z.boolean().default(true),
  services: z.object({
    asr: z.object({
      enabled: z.boolean().default(true),
      url: z.string().url().default("http://localhost:8003"),
      model: z.string().optional(),
      timeoutMs: z.number().default(30000)
    }),
    tts: z.object({
      enabled: z.boolean().default(true),
      url: z.string().url().default("http://localhost:8004"),
      model: z.string().optional(),
      timeoutMs: z.number().default(30000),
      voiceClone: z.object({
        enabled: z.boolean().default(false),
        refAudioPath: z.string().optional(),
        refText: z.string().optional()
      }).optional()
    }),
    s2s: z.object({
      enabled: z.boolean().default(false),
      websocketUrl: z.string().url().default("ws://localhost:8765"),
      reconnectAttempts: z.number().default(5),
      reconnectDelayMs: z.number().default(1000)
    })
  }),
  voiceConversation: z.object({
    enabled: z.boolean().default(false),
    autoStart: z.boolean().default(false),
    greeting: z.string().optional(),
    bargeInEnabled: z.boolean().default(true),
    silenceThresholdMs: z.number().default(800),
    maxSessionDurationMs: z.number().default(600000)
  })
});
```

**Deliverables:**
- Complete configuration schema
- Validation working
- Type definitions complete

## Phase 3: WebSocket & Real-time (Day 3-4)

### 3.1 S2S WebSocket Client

**File:** `src/clients/s2s-client.ts`

**Tasks:**
- [ ] Implement WebSocket connection manager
- [ ] Handle connection lifecycle
- [ ] Implement reconnection logic
- [ ] Manage audio streaming

**API Methods:**
```typescript
class BestBoxS2SClient {
  constructor(options: S2SClientOptions);
  
  // Connect to S2S Gateway
  async connect(): Promise<void>;
  
  // Send audio chunk
  sendAudio(audioChunk: Buffer): void;
  
  // Events
  onTranscript(callback: (text: string) => void): void;
  onPartialTranscript(callback: (text: string) => void): void;
  onSpeechStart(callback: () => void): void;
  onSpeechEnd(callback: () => void): void;
  onAudioResponse(callback: (audio: Buffer) => void): void;
  onError(callback: (error: Error) => void): void;
  
  // Disconnect
  disconnect(): void;
  
  // Check connection status
  isConnected(): boolean;
}
```

**Deliverables:**
- Working WebSocket client
- Reconnection logic verified
- Event handling working

### 3.2 Voice Conversation Manager

**File:** `src/voice-conversation.ts`

**Tasks:**
- [ ] Implement conversation orchestration
- [ ] Manage session state
- [ ] Handle turn-taking
- [ ] Implement barge-in support

**API Methods:**
```typescript
class VoiceConversation {
  constructor(options: ConversationOptions);
  
  // Start conversation
  async start(): Promise<void>;
  
  // Send audio input
  sendAudio(audioBuffer: Buffer): void;
  
  // Stop conversation
  async stop(): Promise<void>;
  
  // Events
  onTranscript(callback: (event: TranscriptEvent) => void): void;
  onResponse(callback: (event: ResponseEvent) => void): void;
  onStateChange(callback: (state: ConversationState) => void): void;
  onError(callback: (error: Error) => void): void;
  
  // Get current state
  getState(): ConversationState;
  
  // Check if active
  isActive(): boolean;
}
```

**Conversation States:**
- `idle` - Waiting to start
- `connecting` - Establishing connection
- `listening` - Waiting for user speech
- `processing` - Transcribing and processing
- `responding` - AI is speaking
- `error` - Error occurred
- `closed` - Conversation ended

**Deliverables:**
- Working conversation manager
- State machine implemented
- Event system working

### 3.3 Voice Call Extension Integration

**File:** Updates to `extensions/voice-call/`

**Tasks:**
- [ ] Add BestBox as STT provider option
- [ ] Update voice call configuration
- [ ] Integrate with media stream handler
- [ ] Test end-to-end voice calls

**Integration:**
```typescript
// In extensions/voice-call/src/config.ts
export const SttProviderSchema = z.enum([
  "openai-realtime",
  "bestbox-s2s"
]);

// In extensions/voice-call/src/media-stream.ts
if (config.sttProvider === "bestbox-s2s") {
  const s2sProvider = new BestBoxS2SProvider({
    websocketUrl: config.bestboxS2S?.websocketUrl
  });
  // Use S2S provider for streaming
}
```

**Deliverables:**
- Voice call extension supports BestBox
- Can make voice calls with local ASR/TTS
- End-to-end test passing

## Phase 4: CLI & UI Integration (Day 4-5)

### 4.1 CLI Commands

**File:** `src/cli.ts` (in extension)

**Tasks:**
- [ ] Add `claw voice chat` command
- [ ] Add `claw voice transcribe` command
- [ ] Add `claw voice synthesize` command
- [ ] Add `claw voice test` command

**Commands:**
```bash
# Start voice conversation
claw voice chat --provider bestbox

# Transcribe audio file
claw voice transcribe ./recording.wav --provider bestbox

# Synthesize text to speech
claw voice synthesize "Hello, world!" --provider bestbox --output hello.wav

# Test BestBox services
claw voice test --asr --tts --s2s

# Configure voice settings
claw voice config --greeting "Hello!" --barge-in --voice-clone ./my-voice.wav
```

**Deliverables:**
- CLI commands working
- Help documentation complete
- Examples provided

### 4.2 TUI Integration

**File:** Updates to OpenClaw TUI

**Tasks:**
- [ ] Add voice conversation UI
- [ ] Show transcription in real-time
- [ ] Display conversation state
- [ ] Add voice activity indicator

**UI Components:**
- Voice conversation panel
- Transcription display
- Audio waveform visualization
- Status indicators (listening/processing/speaking)
- Settings panel

**Deliverables:**
- TUI voice mode working
- Real-time transcription visible
- Visual feedback implemented

## Phase 5: Testing & Documentation (Day 5-7)

### 5.1 Unit Tests

**Files:** `test/*.test.ts`

**Tasks:**
- [ ] Test ASR client
- [ ] Test TTS client
- [ ] Test S2S client
- [ ] Test conversation manager
- [ ] Test configuration validation

**Test Coverage:**
- [ ] ASR transcribe success/failure
- [ ] TTS synthesize success/failure
- [ ] S2S connection/disconnection
- [ ] Audio format conversion
- [ ] Error handling
- [ ] Retry logic
- [ ] Configuration validation

**Deliverables:**
- All unit tests passing
- Coverage > 80%

### 5.2 Integration Tests

**Files:** `test/*.e2e.test.ts`

**Tasks:**
- [ ] Test ASR provider integration
- [ ] Test TTS provider integration
- [ ] Test voice conversation end-to-end
- [ ] Test with actual BestBox services

**Test Scenarios:**
- [ ] Transcribe voice message
- [ ] Synthesize AI response
- [ ] Full voice conversation
- [ ] Voice cloning
- [ ] Error recovery
- [ ] Service fallback

**Deliverables:**
- Integration tests passing
- Test documentation complete

### 5.3 Documentation

**Files:**
- `README.md`
- `docs/SETUP.md`
- `docs/API.md`
- `docs/TROUBLESHOOTING.md`

**Documentation Sections:**
- Installation and setup
- Configuration guide
- Usage examples
- API reference
- Troubleshooting guide
- FAQ

**Deliverables:**
- Complete documentation
- Code examples
- Configuration templates

## Milestones

### Milestone 1: Foundation Complete (Day 2)
- Extension structure created
- ASR and TTS clients working
- Unit tests passing

### Milestone 2: Provider Integration (Day 3)
- ASR provider integrated with OpenClaw
- TTS provider integrated with OpenClaw
- Can transcribe and synthesize

### Milestone 3: Real-time Voice (Day 4)
- S2S WebSocket client working
- Voice conversation manager working
- Can have real-time voice conversations

### Milestone 4: CLI & UI (Day 5)
- CLI commands working
- TUI integration complete
- User-friendly interface

### Milestone 5: Release Ready (Day 7)
- All tests passing
- Documentation complete
- Ready for use

## Risk Management

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BestBox API changes | Medium | High | Abstract client layer, version pinning |
| WebSocket instability | Medium | Medium | Implement robust reconnection |
| Performance issues | Low | High | Benchmark early, optimize as needed |
| Audio format issues | Medium | Medium | Support common formats, conversion |
| Configuration complexity | Low | Medium | Provide defaults, clear docs |

## Dependencies

### Required Before Starting
- [ ] BestBox ASR service running on port 8003
- [ ] BestBox TTS service running on port 8004
- [ ] OpenClaw development environment set up
- [ ] Node.js 18+ installed

### External Dependencies
- `ws` - WebSocket client
- `form-data` - Multipart form data
- `@sinclair/typebox` - Schema validation

## Success Criteria

1. **Functional:** Can transcribe voice messages using BestBox ASR
2. **Functional:** Can synthesize AI responses using BestBox TTS
3. **Functional:** Can have real-time voice conversations via WebSocket
4. **Performance:** ASR latency < 500ms, TTS latency < 1s
5. **Quality:** All tests passing, coverage > 80%
6. **Usability:** CLI commands working, documentation complete
7. **Integration:** Works seamlessly with existing OpenClaw features

## Appendix: Development Commands

```bash
# Set up development environment
cd /home/unergy/MyCode/openclaw/extensions/bestbox
npm install

# Build extension
npm run build

# Run tests
npm test

# Run integration tests
npm run test:e2e

# Test with BestBox
curl http://localhost:8003/health
curl http://localhost:8004/health

# Start S2S Gateway
# (In BestBox directory)
./scripts/start-s2s.sh

# Test WebSocket
wscat -c ws://localhost:8765/ws
```

## Appendix: Configuration Templates

### Template 1: Basic Setup
```json
{
  "bestbox": {
    "enabled": true
  }
}
```

### Template 2: With Voice Conversation
```json
{
  "bestbox": {
    "enabled": true,
    "services": {
      "s2s": {
        "enabled": true
      }
    },
    "voiceConversation": {
      "enabled": true,
      "greeting": "Hello! How can I help?"
    }
  }
}
```

### Template 3: With Voice Cloning
```json
{
  "bestbox": {
    "enabled": true,
    "services": {
      "tts": {
        "voiceClone": {
          "enabled": true,
          "refAudioPath": "./my-voice.wav",
          "refText": "This is my voice reference."
        }
      }
    }
  }
}
```

### Template 4: Production
```json
{
  "bestbox": {
    "enabled": true,
    "services": {
      "asr": {
        "url": "http://bestbox-asr:8003",
        "timeoutMs": 60000
      },
      "tts": {
        "url": "http://bestbox-tts:8004",
        "timeoutMs": 60000
      },
      "s2s": {
        "websocketUrl": "ws://bestbox-s2s:8765",
        "reconnectAttempts": 10
      }
    }
  }
}
```
