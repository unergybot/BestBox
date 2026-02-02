# FunASR + MeloTTS on P100 - Design Document

**Date:** 2026-02-01
**Status:** Approved
**Author:** Claude Code + User

---

## Summary

Replace the current ASR (faster-whisper) and TTS (Piper/XTTS) stack with FunASR Paraformer + MeloTTS, optimized for P100 GPU (SM60, CUDA 11.x) with Chinese as the primary language.

---

## Requirements

| Requirement | Value |
|-------------|-------|
| Primary language | Chinese (Mandarin) with occasional English |
| Latency tolerance | 1-3 seconds acceptable |
| Voice quality | Natural/expressive |
| ASR GPU | P100 (cuda:1) |
| TTS GPU | P100 (cuda:1) |
| LLM GPU | RTX 3080 (cuda:0) - reserved, not touched |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        S2S Pipeline                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Browser/Client                                                 │
│       │                                                         │
│       ▼ PCM16 16kHz                                            │
│  ┌─────────────────┐                                           │
│  │  S2S Gateway    │ WebSocket :8765                           │
│  │  (FastAPI)      │                                           │
│  └────────┬────────┘                                           │
│           │                                                     │
│     ┌─────┴─────┐                                              │
│     ▼           ▼                                              │
│ ┌───────────┐ ┌───────────┐                                    │
│ │ ASR       │ │ TTS       │                                    │
│ │ FunASR    │ │ MeloTTS   │                                    │
│ │ Paraformer│ │ Chinese   │                                    │
│ │ (P100)    │ │ (P100)    │                                    │
│ └─────┬─────┘ └─────┬─────┘                                    │
│       │             │                                           │
│       ▼             │                                           │
│ ┌───────────┐       │                                           │
│ │ LangGraph │◄──────┘                                          │
│ │ Agent API │ :8000                                            │
│ │ (RTX 3080)│                                                  │
│ └───────────┘                                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## P100 VRAM Budget

```
┌─────────────────────────────────────┐
│           P100 (16GB)               │
├─────────────────────────────────────┤
│ FunASR Paraformer-large  ~1.0 GB    │
│ MeloTTS                  ~0.5 GB    │
│ CUDA overhead            ~1.0 GB    │
├─────────────────────────────────────┤
│ Available headroom       ~13.5 GB   │
└─────────────────────────────────────┘
```

---

## Component Design

### ASR: FunASR Paraformer

**File:** `services/speech/asr_funasr.py`

**Model:** `iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch`

Features included:
- VAD (voice activity detection) - built-in
- Punctuation restoration - built-in
- 16kHz input - matches current pipeline

**Configuration:**

| Setting | Value | Reason |
|---------|-------|--------|
| `device` | `cuda:1` | P100 |
| `dtype` | `float16` | P100 doesn't support bfloat16 |
| `batch_size` | 1 | Streaming, single user |
| `hotword` | Optional | Can boost domain terms |

**Interface:**
```python
class FunASREngine:
    def feed_audio(self, pcm: np.ndarray) -> Optional[Dict]
    def finalize(self) -> Dict[str, Any]
    def reset(self)
    def set_language(self, lang: str)  # "zh", "en", or "auto"
```

---

### TTS: MeloTTS

**File:** `services/speech/tts_melo.py`

**Model:** MeloTTS Chinese (supports mixed Chinese + English)

**Configuration:**

| Setting | Value | Reason |
|---------|-------|--------|
| `device` | `cuda:1` | P100 primary |
| `fallback_device` | `cpu` | If CUDA fails |
| `language` | `ZH` | Chinese primary |
| `speed` | `1.0` | Normal speaking rate |
| `sample_rate` | `44100→24000` | Resample for client |

**Interface:**
```python
class MeloTTSEngine:
    def synthesize(self, text: str, language: str = "zh") -> bytes
    async def synthesize_async(self, text: str, language: str = "zh") -> bytes

    @property
    def sample_rate(self) -> int  # 24000 after resampling
```

---

## S2S Server Integration

**File:** `services/speech/s2s_server.py`

**Environment Variables:**
```bash
export ASR_ENGINE="${ASR_ENGINE:-funasr}"   # "funasr" or "whisper"
export TTS_ENGINE="${TTS_ENGINE:-melo}"     # "melo" or "piper"
export ASR_DEVICE="${ASR_DEVICE:-cuda:1}"
export TTS_DEVICE="${TTS_DEVICE:-cuda:1}"
```

**Backward Compatibility:**
- Old engines remain as fallback
- No breaking changes to WebSocket protocol
- Same audio formats (PCM16 16kHz in, PCM16 24kHz out)

---

## Dependencies

**New file:** `requirements-speech.txt`

```txt
# FunASR
funasr>=1.0.0
modelscope>=1.9.0

# MeloTTS
melo-tts>=0.1.0

# Shared
torch>=2.0.0
torchaudio>=2.0.0
numpy
scipy
```

**Model Storage:**

| Model | Size | Location |
|-------|------|----------|
| Paraformer-large | ~1GB | `~/.cache/modelscope/` |
| MeloTTS-Chinese | ~180MB | `~/.cache/melo/` |

---

## Implementation Checklist

```
Phase 1: ASR (FunASR)
├── [ ] Create services/speech/asr_funasr.py
├── [ ] Implement FunASRConfig dataclass
├── [ ] Implement FunASREngine class
├── [ ] Implement FunASRPool for session management
└── [ ] Test standalone

Phase 2: TTS (MeloTTS)
├── [ ] Create services/speech/tts_melo.py
├── [ ] Implement MeloTTSEngine class
├── [ ] Add 44.1kHz → 24kHz resampling
└── [ ] Test standalone

Phase 3: Integration
├── [ ] Update s2s_server.py with engine selection
├── [ ] Update scripts/start-s2s.sh with new env vars
├── [ ] Create scripts/install-speech-p100.sh
└── [ ] Add requirements-speech.txt

Phase 4: Testing
├── [ ] Test ASR with Chinese audio sample
├── [ ] Test ASR with English audio sample
├── [ ] Test TTS with Chinese text
├── [ ] Test TTS with mixed Chinese+English
├── [ ] End-to-end WebSocket test
└── [ ] Latency benchmark
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| ASR accuracy (Chinese) | >95% CER |
| TTS latency | <500ms per sentence |
| End-to-end latency | <2s |
| P100 VRAM usage | <4GB |

---

## Rollback Plan

If FunASR + MeloTTS fails:
1. Set `ASR_ENGINE=whisper` and `TTS_ENGINE=piper`
2. Original engines still present in codebase
3. No data migration needed

---

## References

- [FunASR GitHub](https://github.com/alibaba-damo-academy/FunASR)
- [MeloTTS GitHub](https://github.com/myshell-ai/MeloTTS)
- [Paraformer Model](https://modelscope.cn/models/iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch)
