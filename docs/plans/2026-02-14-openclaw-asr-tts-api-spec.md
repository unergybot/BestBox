# OpenClaw BestBox ASR/TTS API Specification

**Date:** 2026-02-14  
**Version:** 1.0.0  
**Status:** Draft  

## Overview

This document specifies the APIs for integrating BestBox's local ASR/TTS services with OpenClaw. It covers both HTTP REST APIs and WebSocket protocols.

## BestBox Services

### Service Endpoints

| Service | URL | Protocol | Description |
|---------|-----|----------|-------------|
| ASR | `http://localhost:8003` | HTTP | Speech-to-text transcription |
| TTS | `http://localhost:8004` | HTTP | Text-to-speech synthesis |
| S2S | `ws://localhost:8765` | WebSocket | Real-time bidirectional streaming |

## ASR API

### Health Check

Check if the ASR service is running and the model is loaded.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "ok",
  "model": "Qwen/Qwen3-ASR-0.6B",
  "device": "cuda",
  "model_loaded": true
}
```

**Status Codes:**
- `200` - Service healthy
- `503` - Model still loading

### Transcribe Audio

Transcribe an audio file to text.

**Endpoint:** `POST /v1/audio/transcriptions`

**Content-Type:** `multipart/form-data`

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Audio file (WAV, MP3, OGG) |
| `model` | String | No | Model name (ignored, uses loaded model) |
| `language` | String | No | Language hint (e.g., "en", "zh") |

**Request Example:**
```bash
curl -X POST http://localhost:8003/v1/audio/transcriptions \
  -F "file=@recording.wav" \
  -F "language=en"
```

**Response:**
```json
{
  "text": "Hello, how can I help you today?",
  "language": "en",
  "confidence": 0.95,
  "duration_seconds": 3.5
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `text` | String | Transcribed text |
| `language` | String | Detected language code |
| `confidence` | Float | Confidence score (0-1) |
| `duration_seconds` | Float | Audio duration in seconds |

**Status Codes:**
- `200` - Success
- `400` - Invalid request
- `415` - Unsupported audio format
- `503` - Model not loaded

**Supported Audio Formats:**
- WAV (PCM, 16-bit, 16kHz or 44.1kHz)
- MP3 (various bitrates)
- OGG (Vorbis)

### Streaming Transcription (WebSocket)

Real-time transcription via WebSocket.

**Endpoint:** `ws://localhost:8003/ws/transcribe`

**Protocol:**

1. **Connect:** Client connects to WebSocket endpoint
2. **Configure:** Server sends configuration message
3. **Stream:** Client sends audio chunks
4. **Receive:** Server sends partial and final transcripts

**Message Types:**

#### Client → Server

**Audio Chunk:**
```json
{
  "type": "audio",
  "data": "base64-encoded-audio-data"
}
```

**End of Stream:**
```json
{
  "type": "end"
}
```

#### Server → Client

**Configuration:**
```json
{
  "type": "config",
  "sample_rate": 16000,
  "format": "pcm16"
}
```

**Partial Transcript:**
```json
{
  "type": "partial",
  "text": "Hello, how can",
  "language": "en",
  "is_final": false
}
```

**Final Transcript:**
```json
{
  "type": "final",
  "text": "Hello, how can I help you today?",
  "language": "en",
  "confidence": 0.95,
  "duration_seconds": 3.5
}
```

**Error:**
```json
{
  "type": "error",
  "message": "Invalid audio format",
  "code": "INVALID_FORMAT"
}
```

## TTS API

### Health Check

Check if the TTS service is running and the model is loaded.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "ok",
  "model": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
  "device": "cuda",
  "model_loaded": true
}
```

### Synthesize Speech

Synthesize text to speech audio.

**Endpoint:** `POST /synthesize`

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | String | Yes | Text to synthesize |
| `language` | String | Yes | Target language (e.g., "Chinese", "English") |
| `ref_audio` | String | No | Path to reference audio for voice cloning |
| `ref_text` | String | No | Transcript of reference audio |
| `speed` | Float | No | Speech speed multiplier (0.5-2.0, default: 1.0) |

**Request Example:**
```json
{
  "text": "Hello, this is a test of the BestBox TTS system.",
  "language": "English",
  "speed": 1.0
}
```

**Voice Cloning Example:**
```json
{
  "text": "This will be spoken in my cloned voice.",
  "language": "English",
  "ref_audio": "/path/to/reference.wav",
  "ref_text": "This is the reference text that was spoken."
}
```

**Response:**

**Success (200):**
- Content-Type: `audio/wav`
- Body: WAV audio data (PCM, 16-bit, 24kHz)

**Error (400/500):**
```json
{
  "error": "Invalid language",
  "message": "Language 'French' is not supported"
}
```

**Status Codes:**
- `200` - Success, returns audio data
- `400` - Invalid request
- `413` - Text too long
- `503` - Model not loaded

**Supported Languages:**
- Chinese (中文)
- English
- Japanese
- Korean
- German
- French
- Spanish
- Italian

### Streaming Synthesis

Stream audio chunks for long text synthesis.

**Endpoint:** `POST /synthesize/stream`

**Request Body:** Same as `/synthesize`

**Response:**

**Content-Type:** `audio/wav` (streaming)

Server sends audio chunks as they are generated using chunked transfer encoding.

**Example:**
```bash
curl -X POST http://localhost:8004/synthesize/stream \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a very long text that will be streamed...",
    "language": "English"
  }' \
  --output audio.wav
```

## S2S Gateway API (WebSocket)

The S2S (Speech-to-Speech) Gateway provides real-time bidirectional voice conversation capabilities.

### Connection

**Endpoint:** `ws://localhost:8765/ws`

**Protocol Upgrade:**
```
GET /ws HTTP/1.1
Host: localhost:8765
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```

### Session Lifecycle

```
┌─────────┐    Connect     ┌─────────┐
│ Client  │ ──────────────> │  S2S    │
│         │                 │ Gateway │
│         │ <────────────── │         │
│         │   Config        │         │
│         │                 │         │
│         │ ──────────────> │         │
│         │  Audio Stream   │         │
│         │                 │         │
│         │ <────────────── │         │
│         │  Transcripts    │         │
│         │                 │         │
│         │ <────────────── │         │
│         │  Audio Response │         │
│         │                 │         │
│         │ ──────────────> │         │
│         │    Disconnect   │         │
└─────────┘                 └─────────┘
```

### Message Protocol

All messages are JSON objects with a `type` field.

#### Client → Server

**Initialize Session:**
```json
{
  "type": "init",
  "config": {
    "asr_model": "qwen3-asr",
    "tts_model": "qwen3-tts",
    "language": "en",
    "vad_threshold": 0.5,
    "silence_duration_ms": 800
  }
}
```

**Audio Data:**
```json
{
  "type": "audio",
  "data": "base64-encoded-mulaw-audio",
  "timestamp": 1234567890
}
```

*Note:* Audio should be mu-law encoded, 8kHz, mono.

**End of Turn:**
```json
{
  "type": "end_turn"
}
```

**Ping (Keepalive):**
```json
{
  "type": "ping",
  "timestamp": 1234567890
}
```

**Close:**
```json
{
  "type": "close"
}
```

#### Server → Client

**Session Ready:**
```json
{
  "type": "ready",
  "session_id": "sess_abc123",
  "config": {
    "sample_rate": 8000,
    "audio_format": "mulaw"
  }
}
```

**Partial Transcript:**
```json
{
  "type": "partial",
  "text": "Hello, how can",
  "language": "en",
  "timestamp": 1234567890
}
```

**Final Transcript:**
```json
{
  "type": "transcript",
  "text": "Hello, how can I help you today?",
  "language": "en",
  "confidence": 0.95,
  "timestamp": 1234567890
}
```

**Speech Start (VAD):**
```json
{
  "type": "speech_start",
  "timestamp": 1234567890
}
```

**Speech End (VAD):**
```json
{
  "type": "speech_end",
  "timestamp": 1234567890
}
```

**AI Response Text:**
```json
{
  "type": "response_text",
  "text": "I'd be happy to help you with that!",
  "timestamp": 1234567890
}
```

**AI Response Audio:**
```json
{
  "type": "response_audio",
  "data": "base64-encoded-mulaw-audio",
  "timestamp": 1234567890,
  "is_final": false
}
```

**Pong (Keepalive Response):**
```json
{
  "type": "pong",
  "timestamp": 1234567890,
  "latency_ms": 50
}
```

**Error:**
```json
{
  "type": "error",
  "code": "ASR_ERROR",
  "message": "Failed to transcribe audio",
  "timestamp": 1234567890
}
```

**Session End:**
```json
{
  "type": "session_end",
  "reason": "client_disconnect",
  "duration_seconds": 120
}
```

### Error Codes

| Code | Description | Action |
|------|-------------|--------|
| `INVALID_AUDIO` | Audio format not supported | Check audio encoding |
| `ASR_ERROR` | ASR service error | Retry or fallback |
| `TTS_ERROR` | TTS service error | Retry or fallback |
| `SESSION_TIMEOUT` | Session expired due to inactivity | Reconnect |
| `RATE_LIMITED` | Too many requests | Wait and retry |
| `MODEL_LOADING` | Models still initializing | Wait and retry |
| `INTERNAL_ERROR` | Unexpected server error | Report issue |

### Reconnection

If the WebSocket connection drops:

1. Wait for exponential backoff (1s, 2s, 4s, 8s, max 30s)
2. Reconnect with same `session_id` if available
3. If reconnection fails after 5 attempts, start new session

**Reconnection Request:**
```json
{
  "type": "init",
  "session_id": "sess_abc123",  // Previous session ID
  "resume": true
}
```

## OpenClaw Integration APIs

### Extension Configuration

OpenClaw configuration schema for BestBox:

```typescript
interface BestBoxConfig {
  enabled: boolean;
  services: {
    asr: {
      enabled: boolean;
      url: string;
      model?: string;
      timeoutMs?: number;
    };
    tts: {
      enabled: boolean;
      url: string;
      model?: string;
      timeoutMs?: number;
      voiceClone?: {
        enabled: boolean;
        refAudioPath?: string;
        refText?: string;
      };
    };
    s2s: {
      enabled: boolean;
      websocketUrl: string;
      reconnectAttempts?: number;
      reconnectDelayMs?: number;
    };
  };
  voiceConversation: {
    enabled: boolean;
    autoStart: boolean;
    greeting?: string;
    bargeInEnabled: boolean;
    silenceThresholdMs: number;
    maxSessionDurationMs: number;
  };
}
```

### Media Understanding Provider

BestBox ASR implements OpenClaw's `MediaUnderstandingProvider` interface:

```typescript
interface MediaUnderstandingProvider {
  readonly name: string;
  readonly capabilities: MediaUnderstandingCapability[];
  
  transcribe(
    audio: Buffer,
    options?: TranscribeOptions
  ): Promise<TranscriptionResult>;
  
  supportsLanguage(language: string): boolean;
}
```

**Implementation:**
```typescript
class BestBoxASRProvider implements MediaUnderstandingProvider {
  readonly name = "bestbox-asr";
  readonly capabilities = ["audio-transcription"];
  
  constructor(private config: ASRConfig) {
    this.client = new BestBoxASRClient(config);
  }
  
  async transcribe(
    audio: Buffer,
    options?: TranscribeOptions
  ): Promise<TranscriptionResult> {
    const result = await this.client.transcribe(audio, {
      language: options?.language
    });
    
    return {
      text: result.text,
      language: result.language,
      confidence: result.confidence
    };
  }
  
  supportsLanguage(language: string): boolean {
    // BestBox supports multiple languages
    const supported = ["en", "zh", "ja", "ko", "de", "fr", "es", "it"];
    return supported.includes(language.toLowerCase().slice(0, 2));
  }
}
```

### TTS Provider

BestBox TTS implements OpenClaw's TTS provider pattern:

```typescript
type TtsProvider = "elevenlabs" | "openai" | "edge" | "bestbox";

interface TtsResult {
  audioBuffer: Buffer;
  contentType: string;
  voiceCompatible: boolean;
}

async function bestboxTTS(
  text: string,
  config: ResolvedTtsConfig
): Promise<TtsResult> {
  const client = new BestBoxTTSClient(config.bestbox?.url);
  
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

### Voice Conversation API

High-level API for voice conversations:

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
}

// Usage example
const conversation = new VoiceConversation({
  s2sUrl: "ws://localhost:8765",
  bargeInEnabled: true
});

conversation.onTranscript((event) => {
  console.log("User:", event.text);
});

conversation.onResponse((event) => {
  playAudio(event.audio);
});

await conversation.start();
```

## Rate Limits & Quotas

### HTTP APIs

| Endpoint | Rate Limit | Burst |
|----------|-----------|-------|
| ASR Transcribe | 10 req/s | 20 |
| TTS Synthesize | 5 req/s | 10 |
| Health Check | 100 req/s | 200 |

### WebSocket

| Metric | Limit |
|--------|-------|
| Max concurrent sessions | 8 |
| Max session duration | 1 hour |
| Max audio chunk size | 64 KB |
| Min audio chunk interval | 20ms |

## Error Handling

### HTTP Errors

All HTTP errors follow RFC 7807 (Problem Details):

```json
{
  "type": "https://bestbox.local/errors/asr-timeout",
  "title": "ASR Timeout",
  "status": 504,
  "detail": "ASR service took too long to respond",
  "instance": "/v1/audio/transcriptions/req_123"
}
```

### WebSocket Errors

WebSocket errors use the error message type:

```json
{
  "type": "error",
  "code": "ASR_ERROR",
  "message": "Failed to transcribe audio: model not loaded",
  "recoverable": true,
  "retry_after_ms": 5000
}
```

## Versioning

API versions are specified in the URL path:
- Current: `/v1/`
- Beta: `/v1beta/`

Breaking changes will increment the major version number.

## Security

### Authentication

Local services do not require authentication. Access should be restricted to localhost or trusted local network via firewall rules.

### CORS

HTTP APIs allow CORS from `localhost` origins for development:
```
Access-Control-Allow-Origin: http://localhost:*
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

### Input Validation

All inputs are validated:
- Audio file size: max 10MB
- Text length: max 4096 characters
- Language codes: validated against supported list

## Examples

### Complete Voice Conversation Flow

```typescript
import { VoiceConversation } from "openclaw/extensions/bestbox";

// Initialize
const conversation = new VoiceConversation({
  asrUrl: "http://localhost:8003",
  ttsUrl: "http://localhost:8004",
  s2sUrl: "ws://localhost:8765",
  greeting: "Hello! How can I help you?"
});

// Set up event handlers
conversation.onTranscript((event) => {
  console.log("User said:", event.text);
});

conversation.onResponse((event) => {
  console.log("AI said:", event.text);
  playAudio(event.audio);
});

conversation.onStateChange((state) => {
  console.log("State:", state);
});

// Start conversation
await conversation.start();

// Stream audio from microphone
const microphone = getMicrophoneStream();
microphone.onData((chunk) => {
  conversation.sendAudio(chunk);
});

// Stop after 5 minutes
setTimeout(() => {
  conversation.stop();
}, 5 * 60 * 1000);
```

### Batch Transcription

```typescript
import { BestBoxASRClient } from "openclaw/extensions/bestbox";

const client = new BestBoxASRClient({
  url: "http://localhost:8003"
});

const files = [
  "./recording1.wav",
  "./recording2.wav",
  "./recording3.wav"
];

const results = await Promise.all(
  files.map(async (file) => {
    const audio = await fs.readFile(file);
    return client.transcribe(audio);
  })
);

console.log(results);
// [
//   { text: "Hello world", language: "en", confidence: 0.95 },
//   { text: "你好世界", language: "zh", confidence: 0.92 },
//   ...
// ]
```

### Voice Cloning

```typescript
import { BestBoxTTSClient } from "openclaw/extensions/bestbox";

const client = new BestBoxTTSClient({
  url: "http://localhost:8004"
});

// Synthesize with cloned voice
const result = await client.synthesize({
  text: "This is my custom voice speaking!",
  language: "English",
  refAudio: "./my-voice-sample.wav",
  refText: "This is the text I spoke in the sample."
});

// Save audio
await fs.writeFile("./output.wav", result.audio);
```

## Appendix A: Audio Format Specifications

### Input Audio (ASR)

| Property | Value |
|----------|-------|
| Format | WAV, MP3, OGG |
| Sample Rate | 16000 Hz (preferred) or 44100 Hz |
| Channels | Mono or Stereo (converted to mono) |
| Bit Depth | 16-bit |
| Max Duration | 60 seconds |
| Max File Size | 10 MB |

### Output Audio (TTS)

| Property | Value |
|----------|-------|
| Format | WAV |
| Sample Rate | 24000 Hz |
| Channels | Mono |
| Bit Depth | 16-bit |
| Encoding | PCM |

### Streaming Audio (S2S)

| Property | Value |
|----------|-------|
| Format | μ-law (mu-law) |
| Sample Rate | 8000 Hz |
| Channels | Mono |
| Bit Depth | 8-bit |
| Frame Size | 160 samples (20ms) |

## Appendix B: Language Codes

| Language | Code | TTS | ASR |
|----------|------|-----|-----|
| English (US) | `en` | ✓ | ✓ |
| Chinese (Simplified) | `zh` | ✓ | ✓ |
| Japanese | `ja` | ✓ | ✓ |
| Korean | `ko` | ✓ | ✓ |
| German | `de` | ✓ | ✓ |
| French | `fr` | ✓ | ✓ |
| Spanish | `es` | ✓ | ✓ |
| Italian | `it` | ✓ | ✓ |

## Appendix C: HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful request |
| 400 | Bad Request | Invalid parameters |
| 404 | Not Found | Endpoint not found |
| 413 | Payload Too Large | File too large |
| 415 | Unsupported Media Type | Invalid audio format |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Model not loaded |
| 504 | Gateway Timeout | Request timeout |

## Appendix D: WebSocket Close Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 1000 | Normal Closure | Clean disconnect |
| 1001 | Going Away | Server shutting down |
| 1006 | Abnormal Closure | Connection lost |
| 1008 | Policy Violation | Protocol error |
| 1011 | Server Error | Internal error |
| 1012 | Service Restart | Server restarting |
| 1013 | Try Again Later | Rate limited |

## Change Log

### Version 1.0.0 (2026-02-14)
- Initial API specification
- Support for ASR, TTS, and S2S services
- HTTP REST and WebSocket protocols
- Integration with OpenClaw extension system
