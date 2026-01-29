# LiveKit Voice Agent System Hang - Fixes Applied

**Date**: 2026-01-25
**Status**: ✅ All fixes implemented

## Summary of Changes

Four critical fixes have been implemented to prevent system hangs and memory exhaustion in the LiveKit voice agent.

## Fix 1: Model Pooling (COMPLETED)

**Problem**: Each session created new STT (~1.5GB) and TTS (~200MB) model instances, causing memory accumulation.

**Solution**: Implemented singleton pattern with shared model instances.

### Files Modified:
- `services/livekit_local.py`
- `services/livekit_agent.py`

### Changes:

**livekit_local.py** - Added shared model management:
```python
# Shared model instances to prevent memory accumulation
_SHARED_ASR_MODEL = None
_SHARED_TTS_ENGINE = None
_MODEL_LOCK = asyncio.Lock()

async def get_shared_asr() -> StreamingASR:
    """Get or create shared ASR model instance."""
    global _SHARED_ASR_MODEL
    async with _MODEL_LOCK:
        if _SHARED_ASR_MODEL is None:
            logger.info("Initializing shared ASR model...")
            _SHARED_ASR_MODEL = StreamingASR(ASRConfig())
            _ = _SHARED_ASR_MODEL.model  # Trigger lazy load
            logger.info("Shared ASR model initialized")
        return _SHARED_ASR_MODEL

async def get_shared_tts() -> StreamingTTS:
    """Get or create shared TTS engine instance."""
    global _SHARED_TTS_ENGINE
    async with _MODEL_LOCK:
        if _SHARED_TTS_ENGINE is None:
            logger.info("Initializing shared TTS engine...")
            _SHARED_TTS_ENGINE = StreamingTTS(TTSConfig(sample_rate=24000, fallback_to_piper=True))
            _ = _SHARED_TTS_ENGINE.tts  # Trigger lazy load
            logger.info("Shared TTS engine initialized")
        return _SHARED_TTS_ENGINE
```

**LocalSTT and LocalTTS** - Updated to accept shared instances:
```python
class LocalSTT(stt.STT):
    def __init__(self, config: ASRConfig = None, asr_instance: StreamingASR = None):
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))
        self.config = config or ASRConfig()
        self._asr = asr_instance if asr_instance is not None else StreamingASR(self.config)

class LocalTTS(tts.TTS):
    def __init__(self, config: TTSConfig = None, tts_instance: StreamingTTS = None):
        super().__init__(capabilities=tts.TTSCapabilities(streaming=True), sample_rate=24000, num_channels=1)
        self.config = config or TTSConfig()
        self.config.sample_rate = 24000
        self._tts = tts_instance if tts_instance is not None else StreamingTTS(self.config)
```

**livekit_agent.py** - Updated to use shared models:
```python
# STT initialization
from services.livekit_local import get_shared_asr
shared_asr = await get_shared_asr()
session_config["stt"] = LocalSTT(config=asr_config, asr_instance=shared_asr)

# TTS initialization
from services.livekit_local import get_shared_tts
shared_tts = await get_shared_tts()
session_config["tts"] = LocalTTS(config=tts_config, tts_instance=shared_tts)
```

**Impact**:
- Memory usage stable across multiple sessions
- First session: loads models (~2GB)
- Subsequent sessions: reuse models (minimal memory increase)
- Expected memory savings: ~1.7GB per additional session

---

## Fix 2: TTS Timeout (COMPLETED)

**Problem**: TTS synthesis calls could block indefinitely, exhausting thread pool.

**Solution**: Added 5-second timeout to all TTS synthesis operations.

### Files Modified:
- `services/livekit_local.py`

### Changes:

**LocalTTSStream._run()** - Added timeout wrapper:
```python
# Synthesize text to PCM bytes with timeout to prevent indefinite blocking
try:
    pcm_bytes = await asyncio.wait_for(
        asyncio.to_thread(self._tts_engine.synthesize, text),
        timeout=5.0  # 5 second timeout
    )
except asyncio.TimeoutError:
    logger.error(f"TTS synthesis timeout (5s) for text: {text[:50]}...")
    continue
```

**Impact**:
- Prevents thread pool exhaustion
- Graceful handling of slow/stuck TTS operations
- System continues functioning even if TTS has issues
- Clear error logging for debugging

---

## Fix 3: Stream Cleanup (COMPLETED)

**Problem**: Audio streams didn't properly release resources on close.

**Solution**: Enhanced cleanup in LocalSpeechStream and LocalTTSStream.

### Files Modified:
- `services/livekit_local.py`

### Changes:

**LocalSpeechStream.aclose()** - Improved cleanup:
```python
async def aclose(self) -> None:
    """Clean up resources on stream close."""
    try:
        # Signal stream end
        await self._input_queue.put(None)
        # Wait for main task to complete
        if hasattr(self, '_main_task'):
            await self._main_task
        logger.debug("LocalSpeechStream closed successfully")
    except Exception as e:
        logger.error(f"Error closing LocalSpeechStream: {e}")
    finally:
        # Don't reset shared ASR model - it's reused across sessions
        await super().aclose()
```

**LocalTTSStream.aclose()** - Enhanced with queue draining:
```python
async def aclose(self):
    """Close the stream and cleanup resources."""
    try:
        self._closed = True
        # Drain pending items from queue
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        # Signal stream end
        await self._input_queue.put(None)
        logger.debug("LocalTTSStream closed successfully")
    except Exception as e:
        logger.error(f"Error closing LocalTTSStream: {e}")
    # Don't reset shared TTS engine - it's reused across sessions
```

**Impact**:
- Proper resource cleanup on disconnect
- No lingering tasks or queues
- Better error logging for troubleshooting
- Prevents resource leaks

---

## Fix 4: Memory Monitoring (COMPLETED)

**Problem**: No visibility into memory usage or automatic cleanup.

**Solution**: Added periodic memory monitoring with automatic garbage collection.

### Files Modified:
- `services/livekit_agent.py`

### Changes:

**Imports** - Added psutil and gc:
```python
import asyncio
import gc
import psutil
```

**Memory Monitor Function**:
```python
async def monitor_memory():
    """
    Monitor memory usage and trigger garbage collection when needed.
    Runs continuously in the background.
    """
    process = psutil.Process()
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            mem_mb = process.memory_info().rss / 1024 / 1024

            if mem_mb > 3000:  # 3GB threshold
                logger.warning(f"High memory usage detected: {mem_mb:.1f}MB - forcing garbage collection")
                gc.collect()
                # Log memory after GC
                mem_after = process.memory_info().rss / 1024 / 1024
                logger.info(f"Memory after GC: {mem_after:.1f}MB (freed {mem_mb - mem_after:.1f}MB)")
            elif mem_mb > 2000:  # 2GB warning threshold
                logger.info(f"Memory usage: {mem_mb:.1f}MB (warning threshold)")
            else:
                logger.debug(f"Memory usage: {mem_mb:.1f}MB (healthy)")
        except Exception as e:
            logger.error(f"Error in memory monitor: {e}")
```

**Startup** - Added to prewarm function:
```python
# Start memory monitoring in background
logger.info("Starting memory monitor...")
asyncio.create_task(monitor_memory())
```

**Impact**:
- Continuous memory monitoring (every 60 seconds)
- Automatic GC trigger at 3GB threshold
- Warning logs at 2GB
- Visibility into memory usage trends
- Proactive prevention of OOM conditions

---

## Testing Recommendations

### 1. Memory Stability Test
```bash
# Start agent
python services/livekit_agent.py dev

# In another terminal, monitor memory
watch -n 5 'ps aux | grep livekit_agent'

# Connect/disconnect from browser 10 times
# Memory should stabilize, not continuously grow
```

**Expected behavior**:
- First connection: ~2GB (model load)
- Subsequent connections: minimal increase (<100MB per session)
- After disconnect: memory drops back to baseline

### 2. Long-Running Test
```bash
# Keep agent running for 1 hour
# Perform periodic voice interactions
# Check logs for memory warnings

# Should see periodic memory logs:
# "Memory usage: XXXMB (healthy)"
```

**Expected behavior**:
- Memory stays below 2.5GB
- No continuous growth
- GC triggers if needed

### 3. Concurrent Connections
```bash
# Open 3 browser tabs
# All connect to voice UI simultaneously
# Verify model sharing works

# Check logs should show:
# "Initializing shared ASR model..." (once only)
# "Initializing shared TTS engine..." (once only)
```

**Expected behavior**:
- Models loaded once
- All sessions share same instances
- Total memory < 3GB

---

## Monitoring in Production

### Key Log Messages to Watch:

**Healthy operation**:
```
Shared ASR model initialized
Shared TTS engine initialized
Memory usage: 1850.2MB (healthy)
LocalSpeechStream closed successfully
LocalTTSStream closed successfully
```

**Warning signs**:
```
Memory usage: 2100.5MB (warning threshold)
High memory usage detected: 3100.2MB - forcing garbage collection
TTS synthesis timeout (5s) for text: ...
Error closing LocalSpeechStream: ...
```

### When to Take Action:

1. **Memory > 3GB consistently**: Check for memory leaks, increase GC frequency
2. **Frequent TTS timeouts**: Investigate TTS performance, check CPU load
3. **Stream close errors**: Check for connection stability issues
4. **GC freeing < 200MB**: May indicate actual memory leak, needs investigation

---

## Prevention Measures Implemented

✅ **Model Pooling**: Prevents memory accumulation from model duplication
✅ **TTS Timeout**: Prevents indefinite blocking and thread exhaustion
✅ **Stream Cleanup**: Ensures proper resource release on disconnect
✅ **Memory Monitoring**: Provides visibility and automatic intervention

## Next Steps

**Critical** - Still needs to be done:
1. Free disk space (currently 98% full - only 26GB free)
   ```bash
   # Find large files
   du -sh /home/unergy/* | sort -h | tail -20
   sudo apt-get clean
   find ~/.cache -size +1G
   ```

**Target**: Get disk usage below 85% to prevent system instability

**Optional** - Additional improvements:
1. Add session limits (max 5 concurrent)
2. Implement circuit breaker for failing TTS
3. Add Prometheus metrics export
4. Set up alerting for memory thresholds

## Verification Checklist

- [x] Model pooling implemented
- [x] TTS timeout added
- [x] Stream cleanup enhanced
- [x] Memory monitoring active
- [ ] Disk space freed (user action required)
- [ ] Long-running test passed (needs testing)
- [ ] Concurrent connections test passed (needs testing)
- [ ] No memory growth over time (needs testing)
