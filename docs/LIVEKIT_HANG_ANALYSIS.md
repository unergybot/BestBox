# LiveKit Voice Agent System Hang - Root Cause Analysis

**Date**: 2026-01-25
**Incident**: System hang during voice interaction testing

## Root Causes Identified

### 1. Memory Accumulation from Model Loading

**Issue**: Each LiveKit agent session creates new `LocalSTT` and `LocalTTS` instances that lazy-load heavy models:
- faster-whisper large-v3 (~1.5GB)
- Piper TTS models (~200MB each)

**Evidence**:
- Agent logs showed memory warnings: "process memory usage is high: 2274.23828125 MB"
- Multiple connection/disconnect cycles accumulated models in memory
- No explicit model cleanup or reuse between sessions

**Location**: `/home/unergy/BestBox/services/livekit_local.py`
```python
# Line 213-216: Each LocalTTSStream creates new LocalTTS instance
local_tts = LocalTTS(TTSConfig(sample_rate=24000, fallback_to_piper=True))
local_tts._tts = tts_engine  # Reuse TTS engine
```

### 2. Synchronous TTS Blocking Event Loop

**Issue**: TTS synthesis runs in thread pool but could still cause blocking:
```python
# Line 238
pcm_bytes = await asyncio.to_thread(self._tts_engine.synthesize, text)
```

**Problem**:
- Piper TTS subprocess calls can be slow (100-500ms)
- Multiple concurrent TTS requests could exhaust thread pool
- No timeout or cancellation mechanism

### 3. Critical Disk Space (98% Full)

**Evidence**:
```
/dev/nvme0n1p2  937G  864G   26G  98% /
```

**Impact**:
- Swap operations fail or cause thrashing
- Temporary file operations for audio/models fail
- System unable to allocate memory pages
- Can cause kernel OOM killer or system freeze

### 4. Missing Stream Cleanup

**Issue**: No explicit cleanup of audio streams or model instances when sessions end:
- `LocalSpeechStream` doesn't release model resources
- `LocalTTSStream` doesn't cancel pending synthesis on close
- WebRTC tracks not explicitly cleaned up

## Phase 3: Reproduction Steps

To reproduce the hang:
1. Start LiveKit agent: `python services/livekit_agent.py dev`
2. Connect from browser to voice UI
3. Speak to trigger STT → LLM → TTS pipeline
4. Disconnect and reconnect multiple times (3-5 cycles)
5. System memory climbs with each cycle
6. Eventually system hangs or OOM killer activates

## Phase 4: Recommended Fixes

### Fix 1: Implement Model Pooling (HIGH PRIORITY)

Create singleton model instances shared across sessions:

```python
# services/livekit_local.py - Add at module level
_SHARED_ASR_MODEL = None
_SHARED_TTS_ENGINE = None
_MODEL_LOCK = asyncio.Lock()

async def get_shared_asr():
    global _SHARED_ASR_MODEL
    async with _MODEL_LOCK:
        if _SHARED_ASR_MODEL is None:
            _SHARED_ASR_MODEL = StreamingASR(ASRConfig())
            # Trigger lazy load
            _ = _SHARED_ASR_MODEL.model
        return _SHARED_ASR_MODEL

async def get_shared_tts():
    global _SHARED_TTS_ENGINE
    async with _MODEL_LOCK:
        if _SHARED_TTS_ENGINE is None:
            _SHARED_TTS_ENGINE = StreamingTTS(TTSConfig())
            # Trigger lazy load
            _ = _SHARED_TTS_ENGINE.tts
        return _SHARED_TTS_ENGINE
```

### Fix 2: Add TTS Timeout and Cancellation

```python
# In LocalTTSStream._run()
try:
    # Add timeout to prevent indefinite blocking
    pcm_bytes = await asyncio.wait_for(
        asyncio.to_thread(self._tts_engine.synthesize, text),
        timeout=5.0  # 5 second timeout
    )
except asyncio.TimeoutError:
    logger.error(f"TTS synthesis timeout for text: {text[:50]}")
    continue
```

### Fix 3: Implement Proper Stream Cleanup

```python
class LocalSpeechStream(stt.RecognizeStream):
    async def aclose(self) -> None:
        """Clean up resources."""
        self._closed = True
        await self._input_queue.put(None)
        if hasattr(self, '_main_task'):
            await self._main_task
        # Don't reset shared ASR model
        await super().aclose()

class LocalTTSStream(tts.SynthesizeStream):
    async def aclose(self):
        """Close and cleanup."""
        self._closed = True
        # Drain queue
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except:
                break
        await self._input_queue.put(None)
```

### Fix 4: Free Disk Space (CRITICAL)

**Immediate action needed**:
```bash
# Find and remove large unnecessary files
du -sh /home/unergy/* | sort -h | tail -20
# Clean package caches
sudo apt-get clean
# Clean old logs
find /var/log -name "*.log" -mtime +30 -exec rm {} \;
# Check for large model downloads
find ~/.cache -size +1G
```

**Target**: Get disk usage below 85% to prevent system instability

### Fix 5: Add Memory Monitoring and Limits

Add to `services/livekit_agent.py`:
```python
import psutil
import gc

async def monitor_memory():
    """Log memory usage periodically."""
    while True:
        await asyncio.sleep(60)  # Check every minute
        process = psutil.Process()
        mem_mb = process.memory_info().rss / 1024 / 1024
        if mem_mb > 3000:  # 3GB threshold
            logger.warning(f"High memory usage: {mem_mb:.1f}MB - forcing GC")
            gc.collect()
```

## Testing Plan

After implementing fixes:

1. **Memory stability test**:
   - Connect/disconnect 10 times
   - Monitor memory with `watch -n 1 'ps aux | grep livekit'`
   - Memory should stabilize around baseline

2. **Long-running test**:
   - Keep agent running for 1 hour
   - Periodic voice interactions
   - Memory should not continuously grow

3. **Concurrent connections test**:
   - Multiple browser tabs connecting
   - Verify model sharing works
   - No memory multiplication

## Verification

Before considering fix complete:
- [ ] Memory usage stable across multiple sessions
- [ ] No memory growth over 1 hour test
- [ ] Disk space freed to <85%
- [ ] TTS timeouts work correctly
- [ ] Stream cleanup verified in logs
- [ ] System doesn't hang under load

## Prevention

To prevent future hangs:
1. Add memory usage alerts at 2GB threshold
2. Implement automatic model cleanup if memory exceeds 3GB
3. Monitor disk space and alert at 90%
4. Add session limits (max 5 concurrent)
5. Implement circuit breaker for failing TTS synthesis
