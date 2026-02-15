# OpenClaw BestBox ASR/TTS Integration Design

**Date:** 2026-02-14  
**Status:** Draft  
**Author:** AI Assistant  

## Executive Summary

This document outlines the design for integrating BestBox's local ASR (Automatic Speech Recognition) and TTS (Text-to-Speech) services into OpenClaw, enabling voice interaction capabilities including real-time conversations, voice message transcription, and AI voice responses.

## Goals

1. Enable OpenClaw to use BestBox's local ASR service (port 8003) for speech-to-text
2. Enable OpenClaw to use BestBox's local TTS service (port 8004) for text-to-speech
3. Support WebSocket-based real-time voice conversations via BestBox S2S Gateway (port 8765)
4. Maintain compatibility with existing OpenClaw TTS and media understanding architectures
5. Support both HTTP REST and WebSocket streaming modes

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         OpenClaw                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   BestBox   │  │   BestBox   │  │    BestBox S2S          │  │
│  │  ASR Client │  │  TTS Client │  │   WebSocket Client      │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                      │                │
│  ┌──────┴────────────────┴──────────────────────┴────────────┐  │
│  │              BestBox Extension Manager                      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BestBox Services                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  ASR Service│  │  TTS Service│  │    S2S Gateway          │  │
│  │   :8003     │  │   :8004     │  │    :8765 (WebSocket)    │  │
│  │  (Qwen3)    │  │  (Qwen3)    │  │   (Streaming)           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. BestBox Extension (`extensions/bestbox/`)

New OpenClaw extension providing:
- Configuration management
- Service clients (ASR, TTS, S2S)
- Provider implementations
- Voice conversation manager

**Key Files:**
- `index.ts` - Extension entry point
- `src/config.ts` - Configuration schema
- `src/providers/asr-local.ts` - ASR HTTP client
- `src/providers/tts-local.ts` - TTS HTTP client
- `src/providers/s2s-websocket.ts` - S2S WebSocket client
- `src/voice-conversation.ts` - Conversation orchestrator

### 2. ASR Provider (`asr-local.ts`)

Implements OpenClaw's `MediaUnderstandingProvider` interface.

**Capabilities:**
- Transcribe audio files to text
- Support multiple audio formats (WAV, MP3, OGG)
- Language detection and hints
- Confidence scoring

**API Endpoint:** `POST http://localhost:8003/v1/audio/transcriptions`

**Response Format:**
```json
{
  "text": "Hello, how can I help you?",
  "language": "en",
  "confidence": 0.95
}
```

### 3. TTS Provider (`tts-local.ts`)

Implements OpenClaw's TTS provider pattern.

**Capabilities:**
- Synthesize text to speech
- Voice cloning with reference audio
- Multiple language support
- Streaming audio generation

**API Endpoints:**
- `POST http://localhost:8004/synthesize` - Standard synthesis
- `POST http://localhost:8004/synthesize/stream` - Streaming synthesis

**Request Format:**
```json
{
  "text": "Hello, this is a test.",
  "language": "English",
  "ref_audio": "path/to/reference.wav",
  "ref_text": "Reference text"
}
```

### 4. S2S WebSocket Provider (`s2s-websocket.ts`)

Manages real-time bidirectional voice streaming.

**Features:**
- WebSocket connection to S2S Gateway (:8765)
- Audio streaming (mu-law 8kHz)
- VAD (Voice Activity Detection)
- Automatic turn detection
- Barge-in support

**Connection URL:** `ws://localhost:8765/ws`

### 5. Voice Conversation Manager (`voice-conversation.ts`)

Orchestrates full voice conversations.

**Responsibilities:**
- Session lifecycle management
- Audio buffering and playback
- Turn-taking coordination
- Conversation state tracking
- Error recovery

**Events:**
- `onTranscript` - User speech transcribed
- `onResponse` - AI response audio ready
- `onSpeechStart` - User started speaking
- `onSpeechEnd` - User stopped speaking
- `onError` - Error occurred

## Configuration Schema

```typescript
interface BestBoxConfig {
  enabled: boolean;
  services: {
    asr: {
      enabled: boolean;
      url: string;        // Default: "http://localhost:8003"
      model?: string;     // Default: "qwen3-asr"
      timeoutMs?: number; // Default: 30000
    };
    tts: {
      enabled: boolean;
      url: string;        // Default: "http://localhost:8004"
      model?: string;     // Default: "qwen3-tts"
      timeoutMs?: number; // Default: 30000
      voiceClone?: {
        enabled: boolean;
        refAudioPath?: string;
        refText?: string;
      };
    };
    s2s: {
      enabled: boolean;
      websocketUrl: string; // Default: "ws://localhost:8765"
      reconnectAttempts?: number; // Default: 5
      reconnectDelayMs?: number;  // Default: 1000
    };
  };
  voiceConversation: {
    enabled: boolean;
    autoStart: boolean;
    greeting?: string;
    bargeInEnabled: boolean;  // Allow interrupting AI
    silenceThresholdMs: number; // Default: 800
    maxSessionDurationMs: number; // Default: 600000 (10 min)
  };
}
```

## Integration Points

### 1. Media Understanding Integration

Register BestBox ASR as a provider in `src/media-understanding/providers/index.ts`:

```typescript
import { BestBoxASRProvider } from "../../../extensions/bestbox/src/providers/asr-local";

export function buildMediaUnderstandingRegistry() {
  const registry = new Map<string, MediaUnderstandingProvider>();
  
  // Existing providers...
  registry.set("openai", openaiProvider);
  registry.set("groq", groqProvider);
  
  // Add BestBox ASR
  registry.set("bestbox-asr", new BestBoxASRProvider({
    url: "http://localhost:8003"
  }));
  
  return registry;
}
```

### 2. TTS Integration

Add BestBox as a TTS provider in `src/config/types.tts.ts`:

```typescript
export type TtsProvider = "elevenlabs" | "openai" | "edge" | "bestbox";

export type TtsConfig = {
  // ... existing config
  bestbox?: {
    url?: string;
    model?: string;
    voiceClone?: {
      enabled?: boolean;
      refAudioPath?: string;
      refText?: string;
    };
  };
};
```

Implement `bestboxTTS()` in `src/tts/tts-core.ts`:

```typescript
export async function bestboxTTS(
  text: string,
  config: ResolvedTtsConfig,
  outputFormat: AudioOutputFormat
): Promise<TtsResult> {
  const client = new BestBoxTTSClient(config.bestbox?.url || "http://localhost:8004");
  
  const response = await client.synthesize({
    text,
    language: detectLanguage(text),
    refAudio: config.bestbox?.voiceClone?.refAudioPath,
    refText: config.bestbox?.voiceClone?.refText
  });
  
  return {
    audioBuffer: response.audio,
    contentType: "audio/wav",
    voiceCompatible: false
  };
}
```

### 3. Voice Call Extension Integration

Add BestBox as an STT provider option in `extensions/voice-call/src/config.ts`:

```typescript
export const SttProviderSchema = z.enum([
  "openai-realtime",
  "bestbox-s2s"
]).default("openai-realtime");

export interface VoiceCallConfig {
  // ... existing config
  streaming?: {
    enabled: boolean;
    sttProvider: "openai-realtime" | "bestbox-s2s";
    bestboxS2S?: {
      websocketUrl: string;
      vadThreshold?: number;
      silenceDurationMs?: number;
    };
  };
}
```

## Data Flow

### HTTP Mode (ASR/TTS)

```
User speaks → Audio recording → OpenClaw
                                    │
                                    ▼
                           BestBox ASR Client
                                    │
                                    ▼
                    POST /v1/audio/transcriptions
                          (localhost:8003)
                                    │
                                    ▼
                              Transcription
                                    │
                                    ▼
                         OpenClaw Agent Processing
                                    │
                                    ▼
                           BestBox TTS Client
                                    │
                                    ▼
                         POST /synthesize
                          (localhost:8004)
                                    │
                                    ▼
                              Audio Response
                                    │
                                    ▼
                              Play to User
```

### WebSocket Mode (S2S)

```
User speaks → Audio streaming → OpenClaw
                                     │
                                     ▼
                       WebSocket Connection
                        ws://localhost:8765
                                     │
                                     ▼
                         S2S Gateway (BestBox)
                           ┌───────────────┐
                           │  VAD + ASR    │
                           │  (Real-time)  │
                           └───────┬───────┘
                                   │ Transcript
                                   ▼
                         OpenClaw Agent Processing
                                   │
                                   ▼
                         TTS Synthesis (BestBox)
                                   │
                                   ▼
                         Audio Streaming Back
                                   │
                                   ▼
                              Play to User
```

## Error Handling

### Retry Strategy

| Error Type | Retry Count | Backoff | Action |
|------------|-------------|---------|--------|
| Connection refused | 3 | Exponential | Failover to cloud |
| Timeout | 3 | Linear | Retry immediately |
| Model loading | 5 | 5s fixed | Wait and retry |
| Invalid audio | 0 | - | Return error to user |

### Fallback Chain

1. **Primary:** BestBox local services
2. **Secondary:** OpenAI Whisper (ASR) / OpenAI TTS
3. **Tertiary:** Edge TTS (no API key required)

## Security Considerations

1. **Local Network Only:** BestBox services should be accessible only from localhost or trusted local network
2. **No API Keys:** Local services don't require API keys, reducing credential management complexity
3. **Data Privacy:** Audio data stays on local machine, never sent to cloud services
4. **Rate Limiting:** Implement client-side rate limiting to prevent overwhelming local services

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| ASR Latency | < 500ms | End-to-end transcription |
| TTS Latency | < 1s | First audio chunk |
| S2S Latency | < 200ms | Real-time streaming |
| Concurrent Sessions | 4-8 | Depends on GPU memory |
| Audio Quality | 16kHz+ | Minimum sample rate |

## Dependencies

### OpenClaw Side
- `ws` - WebSocket client library
- `form-data` - For multipart audio uploads
- `@sinclair/typebox` - Configuration validation

### BestBox Side (Prerequisites)
- ASR Service running on port 8003
- TTS Service running on port 8004
- S2S Gateway running on port 8765 (optional)

## Future Enhancements

1. **Voice Cloning UI:** Interface for recording reference audio
2. **Conversation History:** Persistent storage of voice conversations
3. **Multi-language Support:** Automatic language detection and switching
4. **Voice Activity Visualization:** Real-time audio waveform display
5. **Noise Cancellation:** Integration with noise suppression libraries
6. **Speaker Diarization:** Multi-speaker support for meetings

## References

- BestBox ASR Service: `/home/unergy/BestBox/services/asr/main.py`
- BestBox TTS Service: `/home/unergy/BestBox/services/tts/main.py`
- BestBox S2S Gateway: `/home/unergy/BestBox/services/speech/s2s_server.py`
- OpenClaw TTS Core: `/home/unergy/MyCode/openclaw/src/tts/tts-core.ts`
- OpenClaw Media Understanding: `/home/unergy/MyCode/openclaw/src/media-understanding/`
- OpenClaw Voice Call Extension: `/home/unergy/MyCode/openclaw/extensions/voice-call/`

## Appendix A: API Endpoints Reference

### ASR Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/v1/audio/transcriptions` | POST | Transcribe audio file |

### TTS Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/synthesize` | POST | Synthesize speech |

### S2S Gateway Endpoints

| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `/ws` | WebSocket | Real-time streaming |
| `/health` | HTTP | Health check |

## Appendix B: Configuration Examples

### Minimal Configuration
```json
{
  "bestbox": {
    "enabled": true
  }
}
```

### Full Configuration
```json
{
  "bestbox": {
    "enabled": true,
    "services": {
      "asr": {
        "enabled": true,
        "url": "http://localhost:8003",
        "timeoutMs": 30000
      },
      "tts": {
        "enabled": true,
        "url": "http://localhost:8004",
        "voiceClone": {
          "enabled": true,
          "refAudioPath": "./voices/my-voice.wav"
        }
      },
      "s2s": {
        "enabled": true,
        "websocketUrl": "ws://localhost:8765"
      }
    },
    "voiceConversation": {
      "enabled": true,
      "greeting": "Hello! I'm your AI assistant.",
      "bargeInEnabled": true
    }
  },
  "messages": {
    "tts": {
      "provider": "bestbox",
      "auto": "always"
    }
  },
  "tools": {
    "media": {
      "audio": {
        "enabled": true,
        "models": [{ "provider": "bestbox-asr", "model": "qwen3-asr" }]
      }
    }
  }
}
```
