# Speech-to-Speech (S2S) Implementation Plan for BestBox

**Version:** 1.0  
**Date:** January 23, 2026  
**Status:** Implementation Ready  
**Reference:** [Speech Design Document](../design/speech.md)

---

## Executive Summary

This plan implements a production-grade speech-to-speech (S2S) system for BestBox that enables voice-driven interaction with the existing LangGraph agent infrastructure. The solution follows the modular streaming architecture recommended in the speech design document, leveraging the existing agent backend while adding ASR and TTS services.

### Key Architecture Decision

**Modular S2S Backend** (NOT end-to-end speech LLM)
- Separate ASR → LangGraph → TTS pipeline
- WebSocket streaming for sub-500ms perceived latency
- Thin clients for PC + mobile
- Full tool calling support preserved

---

## 1. Current State Analysis

### 1.1 Existing Infrastructure ✅

| Component | Status | Notes |
|-----------|--------|-------|
| LangGraph Agent | ✅ Ready | Multi-agent router with ERP/CRM/IT/OA agents |
| FastAPI Backend | ✅ Ready | `agent_api.py` with streaming support |
| Tool Integration | ✅ Ready | 4 tool categories implemented |
| Qwen3 LLM | ✅ Ready | Via llama.cpp/vLLM on ROCm |
| Embeddings | ✅ Ready | BGE-M3 for RAG |
| Docker Services | ✅ Ready | Qdrant, PostgreSQL, Redis |

### 1.2 What Needs to Be Added

| Component | Priority | Complexity |
|-----------|----------|------------|
| ASR Service (faster-whisper) | P0 | Medium |
| TTS Service (XTTS v2) | P0 | Medium |
| WebSocket S2S Endpoint | P0 | Medium |
| VAD Integration | P0 | Low |
| Frontend Audio Capture | P1 | Medium |
| Session Management | P1 | Low |
| Mobile Audio Client | P2 | High |

---

## 2. Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                    │
│  ┌───────────────────────────────────┐ ┌─────────────────────────────┐ │
│  │  Web Client (CopilotKit + Audio)  │ │  Mobile Client (Future)    │ │
│  │  - WebAudio API                   │ │  - React Native Audio      │ │
│  │  - VAD (optional client-side)     │ │  - Thin client             │ │
│  └───────────────────┬───────────────┘ └──────────────┬──────────────┘ │
└──────────────────────┼────────────────────────────────┼─────────────────┘
                       │ WebSocket                      │
                       └───────────────┬────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    S2S GATEWAY (New Service)                            │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  FastAPI WebSocket Endpoint (/ws/s2s)                             │ │
│  │                                                                    │ │
│  │  ┌──────────┐   ┌─────────────┐   ┌──────────┐                   │ │
│  │  │   VAD    │ → │  Session    │ → │  Audio   │                   │ │
│  │  │ (webrtc) │   │  Manager    │   │  Router  │                   │ │
│  │  └──────────┘   └─────────────┘   └──────────┘                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────────┐      ┌────────────────┐
│   ASR Service    │       │   LangGraph Agent    │      │   TTS Service  │
│  (faster-whisper)│       │   (Existing)         │      │   (XTTS v2)    │
│                  │──────▶│                      │─────▶│                │
│  - Streaming     │ text  │  - Router            │tokens│  - Streaming   │
│  - VAD filter    │       │  - ERP/CRM/IT/OA     │      │  - Multilingual│
│  - Multi-lingual │       │  - Tool calls        │      │  - Voice clone │
└──────────────────┘       └──────────────────────┘      └────────────────┘
         │                                                        │
         └────────────────────────┬───────────────────────────────┘
                                  ▼
                    ┌────────────────────────────┐
                    │     GPU / ROCm Backend     │
                    │  (AMD Radeon 8060S)        │
                    │  - Whisper large-v3        │
                    │  - Qwen3-14B               │
                    │  - XTTS v2                 │
                    └────────────────────────────┘
```

---

## 3. Implementation Phases

### Phase 1: Core S2S Pipeline (Week 1-2)

**Goal:** Functional speech-to-speech with basic streaming

#### 3.1.1 ASR Service

Create `services/speech/asr.py`:

```python
from faster_whisper import WhisperModel
import webrtcvad
import numpy as np
from collections import deque
import asyncio
from typing import Callable, Optional
import time

class StreamingASR:
    """Streaming ASR with VAD gating for real-time speech recognition."""
    
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",  # ROCm uses "cuda" too
        compute_type: str = "float16",
        language: str = "zh",  # Default Chinese for enterprise
        vad_aggressiveness: int = 2,
        partial_interval: float = 0.25
    ):
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type
        )
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.sample_rate = 16000
        self.frame_ms = 20
        self.frame_size = int(self.sample_rate * self.frame_ms / 1000)
        self.language = language
        self.partial_interval = partial_interval
        
        self.buffer = deque()
        self.speech_buffer = []
        self.last_partial_time = 0
        self.is_speaking = False
        
    def reset(self):
        """Reset all buffers for new session."""
        self.buffer.clear()
        self.speech_buffer.clear()
        self.last_partial_time = 0
        self.is_speaking = False
        
    def feed_audio(self, pcm: np.ndarray) -> Optional[dict]:
        """
        Feed audio chunk and return partial result if available.
        Returns: {"type": "partial", "text": "..."} or None
        """
        self.buffer.extend(pcm.tolist())
        
        result = None
        while len(self.buffer) >= self.frame_size:
            frame = np.array(
                [self.buffer.popleft() for _ in range(self.frame_size)],
                dtype=np.int16
            )
            
            is_speech = self.vad.is_speech(
                frame.tobytes(),
                self.sample_rate
            )
            
            if is_speech:
                self.speech_buffer.extend(frame.tolist())
                self.is_speaking = True
                
                # Emit partial every interval
                now = time.time()
                if now - self.last_partial_time >= self.partial_interval:
                    text = self._transcribe_buffer()
                    if text.strip():
                        result = {"type": "partial", "text": text}
                    self.last_partial_time = now
            else:
                if self.is_speaking and len(self.speech_buffer) > 0:
                    # End of speech detected
                    self.is_speaking = False
                    
        return result
    
    def finalize(self) -> dict:
        """Get final transcription and clear buffers."""
        if not self.speech_buffer:
            return {"type": "final", "text": ""}
            
        text = self._transcribe_buffer(is_final=True)
        self.speech_buffer.clear()
        return {"type": "final", "text": text}
    
    def _transcribe_buffer(self, is_final: bool = False) -> str:
        """Transcribe current speech buffer."""
        if not self.speech_buffer:
            return ""
            
        audio = np.array(self.speech_buffer, dtype=np.int16).astype(np.float32) / 32768.0
        
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=1 if not is_final else 3,
            vad_filter=False,  # We handle VAD ourselves
            condition_on_previous_text=False
        )
        
        return "".join(s.text for s in segments)
```

#### 3.1.2 TTS Service

Create `services/speech/tts.py`:

```python
from TTS.api import TTS
import numpy as np
from typing import Generator, Optional
import io

class StreamingTTS:
    """Streaming TTS with phrase-level synthesis for low latency."""
    
    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        gpu: bool = True,
        speaker_wav: Optional[str] = None
    ):
        self.tts = TTS(model_name=model_name, gpu=gpu)
        self.sample_rate = 24000
        self.speaker_wav = speaker_wav  # For voice cloning
        
    def synthesize(self, text: str, language: str = "zh-cn") -> bytes:
        """Synthesize text to PCM16 audio."""
        wav = self.tts.tts(
            text=text,
            language=language,
            speaker_wav=self.speaker_wav
        )
        pcm = (np.array(wav) * 32767).astype(np.int16)
        return pcm.tobytes()
    
    def synthesize_streaming(
        self,
        text: str,
        chunk_size: int = 4800,  # 200ms at 24kHz
        language: str = "zh-cn"
    ) -> Generator[bytes, None, None]:
        """Yield audio chunks for streaming playback."""
        wav = self.tts.tts(
            text=text,
            language=language,
            speaker_wav=self.speaker_wav
        )
        pcm = (np.array(wav) * 32767).astype(np.int16)
        
        for i in range(0, len(pcm), chunk_size):
            yield pcm[i:i + chunk_size].tobytes()


class SpeechBuffer:
    """Buffer LLM tokens and emit synthesizable phrases."""
    
    def __init__(self, min_chars: int = 30):
        self.buffer = ""
        self.min_chars = min_chars
        # Sentence-ending punctuation for Chinese/English
        self.terminators = ("。", "？", "！", ".", "?", "!", "；", ";")
        
    def add(self, token: str) -> Optional[str]:
        """Add token, return phrase if ready for synthesis."""
        self.buffer += token
        
        # Check for natural break points
        if self.buffer.endswith(self.terminators):
            phrase = self.buffer
            self.buffer = ""
            return phrase
            
        # Or length threshold
        if len(self.buffer) >= self.min_chars:
            # Find last space/punctuation
            for i in range(len(self.buffer) - 1, -1, -1):
                if self.buffer[i] in " ,，、":
                    phrase = self.buffer[:i + 1]
                    self.buffer = self.buffer[i + 1:]
                    return phrase
                    
        return None
    
    def flush(self) -> Optional[str]:
        """Flush remaining buffer."""
        if self.buffer.strip():
            phrase = self.buffer
            self.buffer = ""
            return phrase
        return None
```

#### 3.1.3 WebSocket S2S Endpoint

Create `services/speech/s2s_server.py`:

```python
import asyncio
import json
import uuid
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import logging

from services.speech.asr import StreamingASR
from services.speech.tts import StreamingTTS, SpeechBuffer
from agents.graph import app as agent_app
from agents.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BestBox S2S Gateway")

# Shared model instances (loaded once)
asr_model: StreamingASR = None
tts_model: StreamingTTS = None

@app.on_event("startup")
async def load_models():
    global asr_model, tts_model
    logger.info("Loading ASR model...")
    asr_model = StreamingASR(
        model_size="large-v3",
        device="cuda",
        language="zh"
    )
    logger.info("Loading TTS model...")
    tts_model = StreamingTTS(gpu=True)
    logger.info("S2S models loaded!")

@app.websocket("/ws/s2s")
async def speech_to_speech(ws: WebSocket):
    """
    Main S2S WebSocket endpoint.
    
    Protocol:
    - Client → Server: Binary (PCM16 audio) or JSON control messages
    - Server → Client: JSON (asr_partial, asr_final, llm_token) or Binary (tts_audio)
    """
    await ws.accept()
    session_id = str(uuid.uuid4())
    logger.info(f"S2S session started: {session_id}")
    
    # Per-session state
    asr = StreamingASR(model_size="large-v3", device="cuda", language="zh")
    speech_buffer = SpeechBuffer(min_chars=30)
    conversation_history = []
    
    try:
        while True:
            message = await ws.receive()
            
            # Binary audio data
            if "bytes" in message:
                pcm = np.frombuffer(message["bytes"], dtype=np.int16)
                result = asr.feed_audio(pcm)
                
                if result and result["type"] == "partial":
                    await ws.send_text(json.dumps({
                        "type": "asr_partial",
                        "text": result["text"]
                    }))
            
            # JSON control messages
            elif "text" in message:
                data = json.loads(message["text"])
                
                if data["type"] == "session_start":
                    asr.reset()
                    lang = data.get("lang", "zh")
                    asr.language = lang
                    logger.info(f"Session {session_id} started with lang={lang}")
                    
                elif data["type"] == "audio_end":
                    # Finalize ASR
                    final = asr.finalize()
                    text = final["text"].strip()
                    
                    if text:
                        await ws.send_text(json.dumps({
                            "type": "asr_final",
                            "text": text
                        }))
                        
                        # Run agent
                        asyncio.create_task(
                            run_agent_and_speak(
                                text, 
                                conversation_history,
                                ws,
                                speech_buffer
                            )
                        )
                
                elif data["type"] == "interrupt":
                    # User interrupted - stop TTS
                    speech_buffer.buffer = ""
                    asr.reset()
                    
    except WebSocketDisconnect:
        logger.info(f"S2S session ended: {session_id}")


async def run_agent_and_speak(
    user_text: str,
    history: list,
    ws: WebSocket,
    speech_buffer: SpeechBuffer
):
    """Run LangGraph agent and stream response as speech."""
    global tts_model
    
    # Build message history
    messages = [HumanMessage(content=msg["content"]) if msg["role"] == "user" 
                else AIMessage(content=msg["content"]) 
                for msg in history]
    messages.append(HumanMessage(content=user_text))
    
    inputs: AgentState = {
        "messages": messages,
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {},
        "plan": [],
        "step": 0
    }
    
    try:
        # Stream agent response
        full_response = ""
        
        async for event in agent_app.astream_events(inputs, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token = chunk.content
                    full_response += token
                    
                    # Send token to client
                    await ws.send_text(json.dumps({
                        "type": "llm_token",
                        "token": token
                    }))
                    
                    # Check if ready to speak
                    phrase = speech_buffer.add(token)
                    if phrase:
                        audio = tts_model.synthesize(phrase)
                        await ws.send_bytes(audio)
        
        # Flush remaining text
        remaining = speech_buffer.flush()
        if remaining:
            audio = tts_model.synthesize(remaining)
            await ws.send_bytes(audio)
        
        # Update history
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": full_response})
        
        await ws.send_text(json.dumps({"type": "response_end"}))
        
    except Exception as e:
        logger.error(f"Agent error: {e}")
        await ws.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "s2s-gateway"}
```

#### 3.1.4 Dependencies

Add to `requirements.txt`:

```plaintext
# Speech-to-Speech
faster-whisper>=1.0.0
webrtcvad>=2.0.10
TTS>=0.22.0
sounddevice>=0.4.6
numpy>=1.24.0
```

---

### Phase 2: Frontend Integration (Week 2-3)

**Goal:** Web audio capture and playback in CopilotKit

#### 3.2.1 Audio Capture Hook

Create `frontend/copilot-demo/hooks/useAudioCapture.ts`:

```typescript
import { useCallback, useRef, useState } from 'react';

interface AudioCaptureOptions {
  sampleRate?: number;
  chunkInterval?: number;  // ms between chunks
  onAudioChunk?: (chunk: ArrayBuffer) => void;
}

export function useAudioCapture({
  sampleRate = 16000,
  chunkInterval = 100,
  onAudioChunk,
}: AudioCaptureOptions = {}) {
  const [isRecording, setIsRecording] = useState(false);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const contextRef = useRef<AudioContext | null>(null);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      const context = new AudioContext({ sampleRate });
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);

      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        const pcm16 = new Int16Array(input.length);
        for (let i = 0; i < input.length; i++) {
          pcm16[i] = Math.max(-32768, Math.min(32767, input[i] * 32768));
        }
        onAudioChunk?.(pcm16.buffer);
      };

      source.connect(processor);
      processor.connect(context.destination);

      mediaStreamRef.current = stream;
      processorRef.current = processor;
      contextRef.current = context;
      setIsRecording(true);
    } catch (err) {
      console.error('Failed to start recording:', err);
    }
  }, [sampleRate, onAudioChunk]);

  const stopRecording = useCallback(() => {
    processorRef.current?.disconnect();
    contextRef.current?.close();
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    setIsRecording(false);
  }, []);

  return { isRecording, startRecording, stopRecording };
}
```

#### 3.2.2 S2S WebSocket Hook

Create `frontend/copilot-demo/hooks/useS2S.ts`:

```typescript
import { useCallback, useRef, useState, useEffect } from 'react';
import { useAudioCapture } from './useAudioCapture';

interface S2SMessage {
  type: 'asr_partial' | 'asr_final' | 'llm_token' | 'response_end' | 'error';
  text?: string;
  token?: string;
  message?: string;
}

interface UseS2SOptions {
  serverUrl?: string;
  language?: string;
  onAsrPartial?: (text: string) => void;
  onAsrFinal?: (text: string) => void;
  onLlmToken?: (token: string) => void;
  onTtsAudio?: (audio: ArrayBuffer) => void;
  onResponseEnd?: () => void;
}

export function useS2S({
  serverUrl = 'ws://localhost:8765/ws/s2s',
  language = 'zh',
  onAsrPartial,
  onAsrFinal,
  onLlmToken,
  onTtsAudio,
  onResponseEnd,
}: UseS2SOptions = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);

  // Audio playback
  const playAudio = useCallback((pcmData: ArrayBuffer) => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
    }
    const ctx = audioContextRef.current;
    const int16 = new Int16Array(pcmData);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }
    const buffer = ctx.createBuffer(1, float32.length, 24000);
    buffer.copyToChannel(float32, 0);
    
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start();
  }, []);

  // WebSocket connection
  const connect = useCallback(() => {
    const ws = new WebSocket(serverUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify({
        type: 'session_start',
        lang: language,
        audio: { sample_rate: 16000, format: 'pcm16', channels: 1 }
      }));
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        playAudio(event.data);
        onTtsAudio?.(event.data);
      } else {
        const msg: S2SMessage = JSON.parse(event.data);
        switch (msg.type) {
          case 'asr_partial':
            setCurrentTranscript(msg.text || '');
            onAsrPartial?.(msg.text || '');
            break;
          case 'asr_final':
            setCurrentTranscript(msg.text || '');
            onAsrFinal?.(msg.text || '');
            break;
          case 'llm_token':
            onLlmToken?.(msg.token || '');
            break;
          case 'response_end':
            onResponseEnd?.();
            break;
        }
      }
    };

    ws.onclose = () => setIsConnected(false);
    wsRef.current = ws;
  }, [serverUrl, language, playAudio, onAsrPartial, onAsrFinal, onLlmToken, onTtsAudio, onResponseEnd]);

  // Audio capture
  const { isRecording, startRecording, stopRecording } = useAudioCapture({
    onAudioChunk: (chunk) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(chunk);
      }
    },
  });

  const startListening = useCallback(() => {
    if (!isConnected) connect();
    startRecording();
    setIsListening(true);
  }, [isConnected, connect, startRecording]);

  const stopListening = useCallback(() => {
    stopRecording();
    setIsListening(false);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'audio_end' }));
    }
  }, [stopRecording]);

  const interrupt = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    }
  }, []);

  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  return {
    isConnected,
    isListening,
    currentTranscript,
    startListening,
    stopListening,
    interrupt,
    connect,
  };
}
```

#### 3.2.3 Voice Button Component

Create `frontend/copilot-demo/components/VoiceButton.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { useS2S } from '@/hooks/useS2S';
import { Mic, MicOff, Volume2 } from 'lucide-react';

interface VoiceButtonProps {
  onTranscript?: (text: string) => void;
  onResponse?: (text: string) => void;
}

export function VoiceButton({ onTranscript, onResponse }: VoiceButtonProps) {
  const [responseText, setResponseText] = useState('');
  
  const {
    isConnected,
    isListening,
    currentTranscript,
    startListening,
    stopListening,
    interrupt,
  } = useS2S({
    onAsrFinal: (text) => {
      onTranscript?.(text);
    },
    onLlmToken: (token) => {
      setResponseText((prev) => prev + token);
    },
    onResponseEnd: () => {
      onResponse?.(responseText);
      setResponseText('');
    },
  });

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Transcript display */}
      {currentTranscript && (
        <div className="bg-gray-100 rounded-lg p-3 text-sm text-gray-700 max-w-md">
          <p className="font-medium">You:</p>
          <p>{currentTranscript}</p>
        </div>
      )}
      
      {/* Response display */}
      {responseText && (
        <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-900 max-w-md">
          <p className="font-medium flex items-center gap-1">
            <Volume2 size={16} /> Assistant:
          </p>
          <p>{responseText}</p>
        </div>
      )}
      
      {/* Voice button */}
      <button
        onClick={isListening ? stopListening : startListening}
        className={`
          w-16 h-16 rounded-full flex items-center justify-center
          transition-all duration-200 shadow-lg
          ${isListening 
            ? 'bg-red-500 hover:bg-red-600 animate-pulse' 
            : 'bg-blue-500 hover:bg-blue-600'
          }
        `}
      >
        {isListening ? (
          <MicOff className="w-8 h-8 text-white" />
        ) : (
          <Mic className="w-8 h-8 text-white" />
        )}
      </button>
      
      <p className="text-xs text-gray-500">
        {isListening ? 'Listening... Click to stop' : 'Click to speak'}
      </p>
      
      {/* Connection status */}
      <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
    </div>
  );
}
```

---

### Phase 3: Production Hardening (Week 3-4)

**Goal:** Production-ready with proper error handling, monitoring, and mobile support

#### 3.3.1 Session Management

- Session timeout handling
- Reconnection logic with state recovery
- Memory limits per session

#### 3.3.2 Latency Optimization

| Target | Metric | Optimization |
|--------|--------|--------------|
| ASR partial | <250ms | Reduce chunk size, beam_size=1 |
| LLM first token | <150ms | Temperature ≤0.4, max_tokens=256 |
| TTS first audio | <200ms | Phrase-level synthesis at 30 chars |
| **Total perceived** | **<600ms** | Overlap all stages |

#### 3.3.3 Error Handling

```python
# In s2s_server.py
class S2SSession:
    MAX_AUDIO_BUFFER = 30 * 16000 * 2  # 30 seconds max
    SESSION_TIMEOUT = 300  # 5 minutes
    
    async def handle_error(self, ws, error):
        await ws.send_text(json.dumps({
            "type": "error",
            "code": error.code,
            "message": str(error),
            "recoverable": error.recoverable
        }))
        if not error.recoverable:
            await ws.close()
```

#### 3.3.4 Docker Integration

Add to `docker-compose.yml`:

```yaml
  s2s-gateway:
    build:
      context: .
      dockerfile: Dockerfile.s2s
    container_name: bestbox-s2s
    ports:
      - "8765:8765"
    volumes:
      - ./services/speech:/app/services/speech
      - ./agents:/app/agents
      - ~/.cache/huggingface:/root/.cache/huggingface
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - ASR_MODEL=large-v3
      - TTS_MODEL=xtts_v2
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
    depends_on:
      - redis
    restart: unless-stopped
```

---

## 4. File Structure

```
services/
├── speech/
│   ├── __init__.py
│   ├── asr.py              # StreamingASR class
│   ├── tts.py              # StreamingTTS + SpeechBuffer
│   ├── s2s_server.py       # FastAPI WebSocket gateway
│   ├── vad.py              # Enhanced VAD utilities
│   └── session.py          # Session management
├── agent_api.py            # Existing (unchanged)
└── ...

frontend/copilot-demo/
├── hooks/
│   ├── useAudioCapture.ts  # Mic capture hook
│   └── useS2S.ts           # S2S WebSocket hook
├── components/
│   ├── VoiceButton.tsx     # Voice UI component
│   └── ...
└── ...

scripts/
├── start-s2s.sh            # S2S service launcher
└── ...
```

---

## 5. Integration Points

### 5.1 With Existing LangGraph

The S2S gateway uses the **same** `agent_app` from `agents/graph.py`:

```python
from agents.graph import app as agent_app
```

This means:
- ✅ All tools work (ERP, CRM, IT, OA)
- ✅ Router agent routes correctly
- ✅ State management preserved
- ✅ Memory/context works

### 5.2 With CopilotKit

The VoiceButton can be integrated alongside existing CopilotKit chat:

```tsx
// In page.tsx
<CopilotSidebar>
  <VoiceButton 
    onTranscript={(text) => addUserMessage(text)}
    onResponse={(text) => addAssistantMessage(text)}
  />
</CopilotSidebar>
```

---

## 6. Testing Plan

### 6.1 Unit Tests

```python
# tests/test_asr.py
def test_asr_partial_emission():
    asr = StreamingASR()
    # Feed audio, check partials emitted every 250ms
    
# tests/test_tts.py
def test_speech_buffer_phrases():
    buf = SpeechBuffer(min_chars=30)
    assert buf.add("Hello") is None
    assert buf.add(" world. ") == "Hello world. "
```

### 6.2 Integration Tests

```python
# tests/test_s2s_integration.py
async def test_full_s2s_flow():
    # Connect WebSocket
    # Send audio
    # Verify asr_partial, asr_final, llm_token, tts_audio
```

### 6.3 Latency Benchmarks

```bash
# scripts/benchmark_s2s.py
# Measure end-to-end latency
# Target: <600ms perceived
```

---

## 7. Rollout Checklist

### Phase 1 Completion
- [ ] ASR service running
- [ ] TTS service running
- [ ] WebSocket endpoint functional
- [ ] Basic streaming works

### Phase 2 Completion
- [ ] Web audio capture working
- [ ] Audio playback working
- [ ] VoiceButton integrated
- [ ] CopilotKit sync working

### Phase 3 Completion
- [ ] Session management robust
- [ ] Error handling complete
- [ ] Docker deployment ready
- [ ] Latency targets met (<600ms)
- [ ] Documentation complete

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| ROCm XTTS compatibility | Test on CPU fallback, use Piper as backup |
| High GPU memory | Load models sequentially, consider INT8 |
| Network latency (mobile) | Local PC testing first, optimize later |
| VAD false positives | Tune aggressiveness, add client-side VAD |

---

## 9. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Perceived latency | <600ms | Time from speech end to audio start |
| ASR accuracy (zh) | >90% WER | Standard test set |
| TTS naturalness | MOS >4.0 | User survey |
| Session stability | <1% crashes | Error rate monitoring |

---

## 10. Next Steps

1. **Week 1**: Implement ASR + TTS services
2. **Week 2**: Build WebSocket gateway, integrate with LangGraph
3. **Week 3**: Frontend hooks and VoiceButton
4. **Week 4**: Testing, optimization, documentation

---

## Appendix A: WebSocket Protocol Reference

### Client → Server

| Message Type | Format | Description |
|--------------|--------|-------------|
| `session_start` | JSON | Initialize session |
| Audio chunk | Binary | PCM16 audio |
| `audio_end` | JSON | Signal end of speech |
| `interrupt` | JSON | Cancel current response |

### Server → Client

| Message Type | Format | Description |
|--------------|--------|-------------|
| `asr_partial` | JSON | Partial transcript |
| `asr_final` | JSON | Final transcript |
| `llm_token` | JSON | Streaming LLM token |
| TTS audio | Binary | PCM16 audio |
| `response_end` | JSON | Response complete |
| `error` | JSON | Error occurred |

---

## Appendix B: Model Requirements

| Model | VRAM | Disk | Notes |
|-------|------|------|-------|
| Whisper large-v3 | ~3GB | 3GB | Can share with LLM |
| Qwen3-14B | ~28GB | 28GB | Existing |
| XTTS v2 | ~2GB | 2GB | Multi-speaker |
| **Total** | ~33GB | 33GB | Fits in 98GB available |
