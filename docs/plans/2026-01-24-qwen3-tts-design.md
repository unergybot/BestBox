# Qwen3-TTS Integration Design for BestBox

**Date:** 2026-01-24
**Status:** Approved for Implementation
**Goal:** Demo-ready Chinese TTS with fast startup and voice cloning

---

## Executive Summary

Integrate Qwen3-TTS as a standalone service to provide high-quality Chinese text-to-speech for BestBox demos. The solution prioritizes fast startup (~10s for S2S, ~20s for TTS), demo reliability, and impressive voice cloning capabilities while maintaining the existing service architecture.

**Key Decisions:**
- **Model:** Qwen3-TTS-1.7B (Base + CustomVoice)
- **Architecture:** Standalone FastAPI service (port 8083)
- **Language:** Chinese-only (zh-cn)
- **Startup:** Independent loading, doesn't block S2S Gateway
- **Fallback:** Multi-tier (Qwen3 → Piper → Silence)

---

## Requirements

### Functional Requirements
1. ✅ Synthesize Chinese text to speech in <500ms (warm)
2. ✅ Support voice cloning from 3-second audio samples
3. ✅ Integrate with S2S Gateway for audio responses
4. ✅ Maintain fast S2S startup (~10s)
5. ✅ Provide health check endpoint for orchestration
6. ✅ Gracefully degrade if TTS unavailable

### Non-Functional Requirements
1. ✅ GPU utilization on AMD Radeon 8060S via ROCm
2. ✅ Memory: <5GB VRAM (both models loaded)
3. ✅ Disk: ~14GB for model storage
4. ✅ Real-Time Factor (RTF): <0.3 for responsive demos
5. ✅ Reliability: Multi-level fallback prevents demo failure

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    BestBox Services                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  S2S Gateway (8765)          Agent API (8000)                │
│       │                            │                          │
│       └────────┬───────────────────┘                          │
│                │                                              │
│                ▼                                              │
│         Qwen3-TTS Service (8083)                             │
│                │                                              │
│         ┌──────┴──────┐                                      │
│         │             │                                       │
│    1.7B-Base    1.7B-CustomVoice                            │
│    (loaded)     (lazy-loaded)                                │
│                                                               │
│                ▼                                              │
│         AMD Radeon 8060S                                     │
│         (ROCm CUDA backend)                                  │
└─────────────────────────────────────────────────────────────┘
```

### Service Tiers

**Modified startup orchestration:**

```
Tier 1: Docker Infrastructure
  - Qdrant, PostgreSQL, Redis

Tier 2: LLM Inference Services
  - LLM Server (8080) - Qwen2.5-14B
  - Embeddings (8081) - BGE-M3
  - Reranker (8082) - BGE-reranker

Tier 2.5: TTS Service (NEW)
  - Qwen3-TTS (8083) - 1.7B models

Tier 2.6: Orchestration
  - Agent API (8000)

Tier 3: Optional Services
  - S2S Gateway (8765)
```

**Startup sequence ensures:**
1. S2S Gateway can start even if TTS is loading
2. TTS health check prevents Agent API from using unavailable service
3. Graceful degradation to Piper fallback

---

## API Design

### Endpoint 1: Health Check

```http
GET /health

Response 200 OK:
{
  "status": "ok",
  "model_loaded": true,
  "models": ["base", "customvoice"],
  "gpu_available": true,
  "device": "cuda:0"
}
```

### Endpoint 2: Standard Synthesis

```http
POST /synthesize
Content-Type: application/json

{
  "text": "你好，欢迎使用BestBox智能助手",
  "language": "zh",
  "stream": false
}

Response 200 OK:
Content-Type: audio/pcm
<Binary PCM16 audio @ 24kHz>
```

### Endpoint 3: Voice Cloning

```http
POST /synthesize/clone
Content-Type: application/json

{
  "text": "使用克隆的声音说话",
  "voice_sample": "<base64-encoded PCM16 or WAV>",
  "language": "zh"
}

Response 200 OK:
Content-Type: audio/pcm
<Binary PCM16 audio @ 24kHz>
```

---

## File Structure

```
services/tts/
├── __init__.py
├── main.py                    # FastAPI app (3 endpoints)
├── qwen3_engine.py           # Core TTS engine wrapper
└── config.py                 # Model paths, device config

scripts/
├── start-tts.sh              # Service startup script
└── install-qwen3-tts.sh      # Download models from HuggingFace

data/
└── voice_samples/            # Optional: pre-configured samples
    └── demo_voice.wav

~/models/tts/
├── Qwen3-TTS-12Hz-1.7B-Base/          # ~7GB
├── Qwen3-TTS-12Hz-1.7B-CustomVoice/   # ~7GB
└── Qwen3-TTS-Tokenizer-12Hz/          # Shared tokenizer
```

---

## Implementation Details

### GPU Memory Management

**Current VRAM allocation:**
- Qwen2.5-14B LLM: ~8.1GB
- BGE-M3 Embeddings: ~1GB
- BGE-reranker: ~0.5GB
- **Subtotal:** ~9.6GB

**With Qwen3-TTS added:**
- 1.7B-Base (FP16): ~2.5GB
- 1.7B-CustomVoice (lazy): ~2.5GB
- **Peak total:** ~14.6GB / 96GB available ✅

### Model Loading Strategy

```python
class Qwen3Engine:
    def __init__(self):
        # Startup: Load immediately
        self.tokenizer = load_tokenizer()      # ~500MB
        self.base_model = load_base()          # ~2.5GB

        # Lazy: Load on first clone request
        self._customvoice_model = None

    def synthesize_clone(self, text, voice):
        if self._customvoice_model is None:
            logger.info("Lazy-loading CustomVoice...")
            self._customvoice_model = load_customvoice()
        # ... synthesis
```

### Performance Optimization

**ROCm optimizations:**
```python
# FP16 for 2x speed
torch_dtype=torch.float16

# Optimize kernel launches
torch.backends.cudnn.benchmark = True

# PyTorch 2.0 compilation
model = torch.compile(model, mode="reduce-overhead")
```

**Phrase caching:**
```python
# Pre-synthesize common demo phrases
DEMO_CACHE = {
    "你好，我是BestBox智能助手": <audio>,
    "请问有什么可以帮您？": <audio>,
    # ... warmup on startup
}
```

**Expected performance on AMD Radeon 8060S:**
- Cold start (first synthesis): ~1-1.5s
- Warm synthesis: ~300-400ms
- Real-Time Factor (RTF): ~0.2-0.25
- Streaming first chunk: ~150-200ms

---

## Integration with S2S Gateway

**Modified `services/speech/tts.py`:**

```python
class StreamingTTS:
    def __init__(self):
        # Check if Qwen3-TTS service available
        if self._check_qwen3_service():
            self._backend = "qwen3"
        else:
            self._backend = "piper"

    def synthesize(self, text: str) -> bytes:
        # Try Qwen3-TTS first
        if self._backend == "qwen3":
            try:
                resp = requests.post(
                    "http://127.0.0.1:8083/synthesize",
                    json={"text": text},
                    timeout=10
                )
                if resp.status_code == 200:
                    return resp.content
                else:
                    # Fallback to Piper for session
                    self._backend = "piper"
            except:
                self._backend = "piper"

        # Fallback: Piper
        return self._synthesize_piper(text, "zh-cn")
```

**S2S Gateway startup check:**

```python
# In services/speech/s2s_server.py
@app.on_event("startup")
async def startup_event():
    try:
        resp = httpx.get("http://127.0.0.1:8083/health", timeout=2)
        if resp.json().get("status") == "ok":
            logger.info("✅ Qwen3-TTS service detected")
            global tts_available
            tts_available = True
    except:
        logger.warning("⚠️ Qwen3-TTS not available")
        tts_available = False
```

---

## Error Handling & Fallback

**Three-tier fallback strategy:**

```
Level 1: Qwen3-TTS Service
  ├─ Success → Return audio
  ├─ GPU OOM → Clear cache, retry once
  ├─ Timeout (>10s) → Fall to Level 2
  └─ Service down → Fall to Level 2

Level 2: Piper TTS Fallback
  ├─ Success → Return audio (lower quality)
  ├─ Piper not installed → Fall to Level 3
  └─ Piper fails → Fall to Level 3

Level 3: Silent Audio Fallback
  └─ Return silence, log warning, demo continues (text-only)
```

**Graceful degradation matrix:**

| Failure | S2S Behavior | User Impact |
|---------|--------------|-------------|
| Qwen3 service down | Falls back to Piper | Lower voice quality |
| Piper missing | Returns silence | Text responses only |
| GPU OOM | Clears cache, retries | 1-2s delay |
| Network timeout | Switches to Piper | Session uses backup |
| All TTS fails | Returns silence | Chat works, no audio |

---

## Testing Strategy

### Unit Tests

```python
# tests/test_tts_service.py
def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["model_loaded"] == True

def test_basic_synthesis():
    resp = client.post("/synthesize", json={"text": "你好世界"})
    assert resp.status_code == 200
    assert len(resp.content) > 0

def test_voice_cloning():
    voice_sample = load_demo_voice()
    resp = client.post("/synthesize/clone", json={
        "text": "克隆测试",
        "voice_sample": voice_sample.hex()
    })
    assert resp.status_code == 200
```

### Integration Tests

```bash
# scripts/test-demo-flow.sh
1. Start all services
2. Test S2S → Agent → TTS pipeline
3. Test voice cloning demo
4. Measure end-to-end latency
5. Verify fallback behavior
```

### Demo Rehearsal

```python
# scripts/demo_rehearsal.py
async def rehearsal():
    # Scenario 1: Greeting (verify <3s latency)
    # Scenario 2: Complex query (verify streaming)
    # Scenario 3: Voice cloning (verify CustomVoice loads)
    # Report: Pass/Fail + performance metrics
```

### Pre-Demo Checklist

```bash
# scripts/pre-demo-checklist.sh
✅ LLM Server healthy
✅ Qwen3-TTS healthy
✅ Agent API healthy
✅ S2S Gateway healthy
✅ TTS synthesis working
✅ GPU available
✅ Disk space sufficient
```

---

## Installation Steps

### Phase 1: Download Models (~15 minutes)

```bash
# Install dependencies
pip install transformers torch torchaudio accelerate

# Download models (14GB total)
huggingface-cli download Qwen/Qwen3-TTS-Tokenizer-12Hz
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
```

### Phase 2: Service Setup (~30 minutes)

```bash
# Create service files
services/tts/config.py
services/tts/qwen3_engine.py
services/tts/main.py

# Create startup script
scripts/start-tts.sh

# Update orchestration
scripts/start-all-services.sh (add Tier 2.5)
```

### Phase 3: Integration (~2 hours)

```bash
# Modify S2S Gateway TTS backend
services/speech/tts.py (add Qwen3 backend)

# Update startup checks
services/speech/s2s_server.py (check TTS availability)

# Test end-to-end
./scripts/start-all-services.sh
python scripts/demo_rehearsal.py
```

---

## Performance Targets

### Latency Budget (User speaks → hears response)

```
Target: <3 seconds total

- ASR (CPU fallback):      ~500-800ms
- Agent/LLM processing:    ~1000-1500ms
- TTS synthesis (Qwen3):   ~300-500ms
- Network/buffering:       ~100-200ms

Expected: 2-3 seconds ✅
```

### TTS Performance Baselines

| Metric | Target | Expected (AMD 8060S) |
|--------|--------|---------------------|
| Cold start | <2s | ~1-1.5s |
| Warm synthesis | <500ms | ~300-400ms |
| RTF | <0.3 | ~0.2-0.25 |
| Streaming first chunk | <200ms | ~150-200ms |
| GPU memory (FP16) | <3GB | ~2.5GB |

---

## Implementation Roadmap

### Phase 1: Foundation (Day 1 - 2 hours)
1. Run `scripts/install-qwen3-tts.sh`
2. Create service structure
3. Implement `/health` and `/synthesize` endpoints
4. Test standalone service

### Phase 2: Integration (Day 1-2 - 3 hours)
5. Create startup scripts
6. Update orchestration
7. Modify S2S TTS backend
8. Test full service stack

### Phase 3: Voice Cloning (Day 2 - 2 hours)
9. Implement `/synthesize/clone` endpoint
10. Add lazy CustomVoice loading
11. Test with demo samples
12. Create showcase demo

### Phase 4: Testing (Day 3 - 3 hours)
13. Write unit tests
14. Create integration tests
15. Build demo rehearsal
16. Performance benchmarks
17. Pre-demo checklist

### Phase 5: Documentation (Day 3 - 1 hour)
18. Write this design doc ✅
19. Update CLAUDE.md
20. Commit changes
21. Final demo validation

**Total: ~11 hours over 3 days**

---

## Success Criteria

Before marking complete:
- [ ] All services start via `start-all-services.sh`
- [ ] TTS synthesizes Chinese in <500ms
- [ ] Voice cloning works with demo sample
- [ ] `demo_rehearsal.py` passes all scenarios
- [ ] `pre-demo-checklist.sh` shows 100% healthy
- [ ] Documentation committed to git

---

## Trade-offs & Alternatives Considered

### Why Qwen3-TTS over OuteTTS?
- ✅ Qwen3: Excellent Chinese support (primary requirement)
- ❌ OuteTTS: English-optimized, poor Chinese quality

### Why standalone service vs. integrated?
- ✅ Standalone: Fast S2S startup, isolated failures
- ❌ Integrated: Simpler but blocks S2S startup

### Why 1.7B vs. 0.6B model?
- ✅ 1.7B: Better voice quality for demos
- ✅ Memory: 2.5GB acceptable with 96GB available
- ⚠️ 0.6B: Faster but lower quality

### Why not Qwen2.5-Omni (integrated LLM+TTS)?
- ❌ Not available in GGUF for llama.cpp
- ❌ Would require replacing entire LLM stack
- ❌ Higher complexity, lower reliability

---

## Future Enhancements (Post-MVP)

1. **Streaming TTS** - Generate audio chunks during synthesis for lower perceived latency
2. **Multi-speaker support** - Pre-configured voice profiles for different scenarios
3. **Emotion control** - Use VoiceDesign model for expressive synthesis
4. **GPU sharing optimization** - Unified memory pool with LLM server
5. **Production hardening** - Rate limiting, monitoring, auto-restart

---

## References

- [Qwen3-TTS on Hugging Face](https://huggingface.co/collections/Qwen/qwen3-tts)
- [Qwen3-TTS GitHub](https://github.com/QwenLM/Qwen3-TTS)
- [Qwen3-TTS Technical Report](https://arxiv.org/html/2601.15621)
- [llama.cpp TTS support](https://github.com/ggml-org/llama.cpp/pull/10784)

---

## Appendix: Configuration Reference

### Environment Variables

```bash
# TTS Service
TTS_PORT=8083
TTS_DEVICE=cuda              # cuda or cpu
TTS_USE_FP16=true           # Half precision
TTS_MAX_BATCH_SIZE=4        # Concurrent requests
TTS_ENABLE_CACHE=true       # Phrase caching

# Model paths
TTS_MODEL_DIR=~/models/tts
TTS_BASE_MODEL=Qwen3-TTS-12Hz-1.7B-Base
TTS_CUSTOM_MODEL=Qwen3-TTS-12Hz-1.7B-CustomVoice
```

### Service Ports Summary

| Service | Port | Purpose |
|---------|------|---------|
| LLM Server | 8080 | Qwen2.5-14B inference |
| Embeddings | 8081 | BGE-M3 embeddings |
| Reranker | 8082 | BGE-reranker |
| **Qwen3-TTS** | **8083** | **Text-to-speech** |
| Agent API | 8000 | LangGraph orchestration |
| S2S Gateway | 8765 | WebSocket speech interface |
| Qdrant | 6333 | Vector database |
| PostgreSQL | 5432 | Relational database |
| Redis | 6379 | Cache |

---

**Document Version:** 1.0
**Last Updated:** 2026-01-24
**Approved By:** User (brainstorming session)
