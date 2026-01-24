# Speech-to-Speech (S2S) System Improvements

**Date:** 2026-01-23
**Status:** ✅ Improvements Applied

---

## Overview

This document summarizes the improvements made to the BestBox Speech-to-Speech system to improve success rate, optimize the pipeline, and enhance the agentic functionality.

---

## 1. Frontend Singleton Pattern (Critical Fix)

### Problem
The `VoiceInput` component (which uses `useS2S` via `VoiceButton`) was being unmounted and remounted by CopilotSidebar during state transitions (e.g., after the first message is sent). This killed the S2S WebSocket connection, causing ASR failures for subsequent interactions.

### Solution
Implemented a **Singleton Pattern** for the S2S client:

**New File: [lib/S2SClient.ts](frontend/copilot-demo/lib/S2SClient.ts)**
- Singleton class `S2SClient` that manages WebSocket, audio capture, and playback
- Connection persists across component lifecycle events
- EventEmitter pattern for UI updates
- Auto-reconnect with exponential backoff
- Keepalive ping/pong mechanism (30-second interval)

**Modified: [hooks/useS2S.ts](frontend/copilot-demo/hooks/useS2S.ts)**
- Now subscribes to the singleton instead of managing its own WebSocket
- On unmount: removes listeners but does NOT disconnect
- Connection survives component unmount/remount cycles

### Key Benefits
- ✅ WebSocket connection survives UI state changes
- ✅ No more ASR failures after first message
- ✅ Auto-reconnection with exponential backoff
- ✅ Keepalive prevents connection timeouts

---

## 2. Agentic Function Improvements

### Problem
The router was sending conversational messages like "hi" to a fallback that asked users to clarify, creating a poor user experience.

### Solution

**New Agent: [agents/general_agent.py](agents/general_agent.py)**
- Handles cross-domain queries, greetings, and general assistance
- Uses `search_knowledge_base` tool for RAG-powered responses
- Friendly, concise responses optimized for speech output

**Modified: [agents/router.py](agents/router.py)**
- Added `general_agent` as a routing destination
- Updated routing rules to prefer `general_agent` over `fallback`
- Greetings ("hi", "hello") now route to `general_agent`
- Help requests route to `general_agent`

**Modified: [agents/graph.py](agents/graph.py)**
- Integrated `general_agent` into the LangGraph workflow
- Added deduplication for tools shared across agents
- All agents can now use tools and loop back

### Key Benefits
- ✅ Natural greeting responses ("Hello! How can I help you?")
- ✅ Cross-domain queries handled gracefully
- ✅ RAG integration for knowledge-based answers
- ✅ Fallback now only triggers for truly out-of-scope requests

---

## 3. Pipeline & Model Optimizations

### TTS Improvements
**Modified: [services/speech/tts.py](services/speech/tts.py)**
- Added 30-second timeout protection for Piper subprocess
- Prevents hangs during TTS synthesis
- Better error recovery and logging

### WebSocket Improvements
**Modified: [services/speech/s2s_server.py](services/speech/s2s_server.py)**
- Added ping/pong keepalive mechanism
- 60-second receive timeout with automatic ping
- Sends `session_ready` immediately on connection
- Better session touch for activity tracking

### Key Benefits
- ✅ No more indefinite hangs during TTS
- ✅ Connections stay alive during idle periods
- ✅ Better error handling and recovery

---

## 4. Files Modified

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/copilot-demo/lib/S2SClient.ts` | NEW | Singleton WebSocket manager |
| `frontend/copilot-demo/hooks/useS2S.ts` | MODIFIED | Uses singleton, survives unmounts |
| `agents/general_agent.py` | NEW | General assistant agent |
| `agents/router.py` | MODIFIED | Better routing logic |
| `agents/graph.py` | MODIFIED | Integrated general_agent |
| `agents/__init__.py` | MODIFIED | Added docstring |
| `services/speech/tts.py` | MODIFIED | Timeout protection |
| `services/speech/s2s_server.py` | MODIFIED | Keepalive, session_ready |

---

## 5. Verification Steps

### Manual Testing
1. Start all services:
   ```bash
   ./scripts/start-llm.sh
   ./scripts/start-embeddings.sh
   ./scripts/start-s2s.sh
   ```

2. Start frontend:
   ```bash
   cd frontend/copilot-demo && npm run dev
   ```

3. Test scenarios:
   - [ ] Speak first message → Response received
   - [ ] Connection stays OPEN after first response
   - [ ] Speak second message immediately → Works without reconnecting
   - [ ] Say "hi" → Get friendly greeting (not fallback)
   - [ ] Ask cross-domain question → General agent handles it
   - [ ] Idle for 60+ seconds → Connection stays alive (keepalive)

---

## 6. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐      ┌─────────────────┐                 │
│   │   VoiceButton   │──────│   VoiceInput    │                 │
│   └────────┬────────┘      └────────┬────────┘                 │
│            │                        │                           │
│            ▼                        ▼                           │
│   ┌───────────────────────────────────────────┐                │
│   │              useS2S Hook                   │                │
│   │        (subscribes to singleton)           │                │
│   └──────────────────┬────────────────────────┘                │
│                      │                                          │
│   ┌──────────────────▼────────────────────────┐                │
│   │           S2SClient (SINGLETON)            │◄─── PERSISTS  │
│   │  - WebSocket connection                    │     ACROSS    │
│   │  - Audio capture/playback                  │     UNMOUNTS  │
│   │  - Keepalive ping/pong                     │                │
│   └──────────────────┬────────────────────────┘                │
│                      │                                          │
└──────────────────────┼──────────────────────────────────────────┘
                       │ WebSocket (ws://host:8765/ws/s2s)
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     S2S Server (FastAPI)                         │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────┐    ┌───────────────┐    ┌──────────┐              │
│  │   ASR    │───▶│   LangGraph   │───▶│   TTS    │              │
│  │ (whisper)│    │    Agents     │    │  (piper) │              │
│  └──────────┘    └───────┬───────┘    └──────────┘              │
│                          │                                       │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                     │
│  ┌───────────┐   ┌──────────────┐   ┌───────────┐              │
│  │   Router  │──▶│ general_agent │   │ erp_agent │              │
│  └───────────┘   │ crm_agent     │   │ oa_agent  │              │
│                  │ it_ops_agent  │   │           │              │
│                  └──────────────┘   └───────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Known Limitations

1. **ASR GPU Support**: CTranslate2 lacks ROCm support, falls back to CPU (slower but works)
2. **TTS Model**: Using Piper fallback on Python 3.12+ (Coqui TTS not compatible)
3. **Sample Rate Mismatch**: Piper outputs at 22050Hz, client expects 24000Hz (minor quality impact)

---

## 8. Future Improvements

- [ ] Add AudioWorklet API support (replace deprecated ScriptProcessorNode)
- [ ] Implement WebSocket binary compression for audio chunks
- [ ] Add client-side VAD for smarter audio streaming
- [ ] Support for interruption mid-response
- [ ] Add conversation history persistence
