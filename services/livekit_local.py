
import asyncio
import logging
import time
import uuid
from typing import AsyncIterable
import numpy as np

from livekit import agents, rtc
from livekit.agents import stt, tts
from livekit.agents.types import APIConnectOptions
from livekit.agents.utils import aio

from services.speech.asr import StreamingASR, ASRConfig
from services.speech.tts import StreamingTTS, TTSConfig

logger = logging.getLogger("livekit.local")

# Shared model instances to prevent memory accumulation
_SHARED_ASR_MODEL = None
_SHARED_TTS_ENGINE = None
_MODEL_LOCK = asyncio.Lock()

async def get_shared_asr() -> StreamingASR:
    """
    Get a NEW ASR instance for the session, but sharing the heavy Whisper model.
    This prevents state pollution (buffers) between sessions while saving memory.
    """
    global _SHARED_ASR_MODEL
    async with _MODEL_LOCK:
        if _SHARED_ASR_MODEL is None:
            logger.info("🔧 Initializing PRIMARY ASR model holder...")
            _SHARED_ASR_MODEL = StreamingASR(ASRConfig())
            # Trigger lazy load of model in a thread to avoid blocking
            # We need the model loaded to share it
            try:
                # Accessing .model property triggers load
                await asyncio.to_thread(lambda: _SHARED_ASR_MODEL.model)
                logger.info(f"✅ Primary ASR model loaded (ID: {id(_SHARED_ASR_MODEL)})")
            except Exception as e:
                logger.error(f"❌ Failed to load primary ASR model: {e}")
                raise
        else:
             logger.info(f"♻️  Using existing Primary ASR model (ID: {id(_SHARED_ASR_MODEL)})")
    
    # Create a FRESH instance for this session
    # This ensures separate buffers/state
    session_asr = StreamingASR(ASRConfig())
    
    # Inject the shared heavy model
    session_asr._model = _SHARED_ASR_MODEL.model
    # Do NOT share VAD (it's cheap and might have state)
    
    logger.info(f"🆕 Created FRESH StreamingASR session (ID: {id(session_asr)}) sharing model {id(session_asr._model)}")
    return session_asr

async def get_shared_tts() -> StreamingTTS:
    """Get or create shared TTS engine instance."""
    global _SHARED_TTS_ENGINE
    async with _MODEL_LOCK:
        if _SHARED_TTS_ENGINE is None:
            logger.info("🔧 Initializing shared TTS engine (first session)...")
            _SHARED_TTS_ENGINE = StreamingTTS(TTSConfig(sample_rate=24000, fallback_to_piper=True))
            # Trigger lazy load
            _ = _SHARED_TTS_ENGINE.tts
            logger.info(f"✅ Shared TTS engine initialized (ID: {id(_SHARED_TTS_ENGINE)})")
        else:
            logger.info(f"♻️  Reusing existing shared TTS engine (ID: {id(_SHARED_TTS_ENGINE)})")
        return _SHARED_TTS_ENGINE

# Simple resampling helper
def resample_16k(pcm: np.ndarray, orig_sr: int) -> np.ndarray:
    """
    Resample audio to 16kHz using proper resampling techniques.
    
    Args:
        pcm: Audio data as numpy array
        orig_sr: Original sample rate
        
    Returns:
        Resampled audio at 16kHz
    """
    if orig_sr == 16000:
        return pcm
    
    try:
        # Try to use scipy for proper resampling if available
        from scipy import signal
        target_sr = 16000
        num_samples = int(len(pcm) * target_sr / orig_sr)
        resampled = signal.resample(pcm, num_samples).astype(np.int16)
        return resampled
    except ImportError:
        # Fallback to simple decimation for common cases
        if orig_sr == 48000:
            # 48k -> 16k is 3:1 ratio
            return pcm[::3]
        if orig_sr == 32000:
            # 32k -> 16k is 2:1 ratio
            return pcm[::2]
        if orig_sr == 24000:
            # 24k -> 16k is 3:2 ratio - use every 3rd sample, skip 1
            indices = np.arange(0, len(pcm), 1.5).astype(int)
            indices = indices[indices < len(pcm)]
            return pcm[indices]
        
        # For other rates, use linear interpolation fallback
        target_sr = 16000
        ratio = orig_sr / target_sr
        indices = np.arange(0, len(pcm), ratio).astype(int)
        indices = indices[indices < len(pcm)]
        return pcm[indices]


class LocalSTT(stt.STT):
    def __init__(self, config: ASRConfig = None, asr_instance: StreamingASR = None):
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))
        self.config = config or ASRConfig()
        # Use provided ASR instance (shared) or create new one (fallback)
        self._asr = asr_instance if asr_instance is not None else StreamingASR(self.config)

    def _recognize_impl(self, buffer: AsyncIterable[rtc.AudioFrame], language: str = None) -> AsyncIterable[stt.SpeechEvent]:
        """
        Required abstract method implementation for LiveKit agents 1.x
        This is the main recognition method called by the framework.
        """
        return self.recognize(buffer, language)

    async def recognize(self, buffer: AsyncIterable[rtc.AudioFrame], language: str = None) -> AsyncIterable[stt.SpeechEvent]:
        # Reset ASR state
        self._asr.reset()
        if language:
            self._asr.set_language(language)

        async for frame in buffer:
            # Convert AudioFrame to int16 numpy array
            # Frame data is bytes, 16-bit, system endian (usually little)
            # LiveKit AudioFrame usually has sample_rate and num_channels
            
            # StreamingASR expects raw int16 bytes or numpy array
            pcm = np.frombuffer(frame.data, dtype=np.int16)
            
            # Feed to ASR (blocking call moved to thread)
            # Note: StreamingASR logic is slightly different, it handles partial emissions internally
            # We need to bridge the gap.
            
            result = await asyncio.to_thread(self._asr.feed_audio, pcm)
            
            if result:
                if result["type"] == "partial":
                     yield stt.SpeechEvent(
                         type=stt.SpeechEventType.INTERIM_TRANSCRIPT,
                         alternatives=[stt.SpeechData(text=result["text"], confidence=1.0, language=language or "")]
                     )
        
        # Finalize
        final = await asyncio.to_thread(self._asr.finalize)
        if final and final["text"]:
            yield stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[stt.SpeechData(text=final["text"], confidence=1.0, language=language or "")]
            )

    # Note: Stream API in LiveKit agents might be different in 0.8.x
    # We implement recognize() which is the main entry point for `SpeechHandle`.
    # However, `VoicePipelineAgent` uses `stt.stream()`.
    # Let's implement stream() using the base class helper if available, or simple adaptation.

    def stream(self, language: str = None, **kwargs) -> stt.RecognizeStream:
        """
        Return a RecognizeStream for streaming STT recognition.
        Required for LiveKit Voice Pipeline Agent to work.
        """
        # Accept any additional parameters (like conn_options) via **kwargs
        return LocalSpeechStream(self, self._asr, language=language)


class LocalSpeechStream(stt.RecognizeStream):
    def __init__(self, local_stt: 'LocalSTT', asr: StreamingASR, *, language: str = None):
        # Pass required parameters to parent RecognizeStream
        # Create a minimal APIConnectOptions if needed
        try:
            from livekit.agents.types import APIConnectOptions
            conn_options = APIConnectOptions()
        except:
            conn_options = None
            
        super().__init__(stt=local_stt, conn_options=conn_options)
        self._asr = asr
        self._language = language
        self._asr.reset()
        if language:
            self._asr.set_language(language)
        self._queue = asyncio.Queue()
        self._input_queue = asyncio.Queue()
        self._main_task = asyncio.create_task(self._run())

    def push_frame(self, frame: rtc.AudioFrame) -> None:
        if not hasattr(self, "_first_frame_logged"):
            logger.info(f"LocalSpeechStream: First frame pushed! (SR={frame.sample_rate}, Ch={frame.num_channels})")
            self._first_frame_logged = True
        self._input_queue.put_nowait(frame)

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

    async def _run(self):
        first_frame_time = None
        frame_count = 0

        try:
            while True:
                frame = await self._input_queue.get()
                if frame is None:
                    break
                    
                # Track first frame
                if first_frame_time is None:
                    first_frame_time = time.time()
                    logger.info(f"🎤 STT: Started receiving audio (SR={frame.sample_rate}Hz, Ch={frame.num_channels})")

                frame_count += 1
                pcm = np.frombuffer(frame.data, dtype=np.int16)
                
                # Resample if needed
                if frame.sample_rate != 16000:
                    pcm = resample_16k(pcm, frame.sample_rate)
                
                # DEBUG: Calculate energy
                energy = np.sqrt(np.mean(pcm.astype(float)**2))
                if energy > 500: # Arbitrary threshold for "loud enough"
                     if not hasattr(self, "_last_energy_log") or time.time() - self._last_energy_log > 1.0:
                          logger.info(f"🎯 VOICE_PIPELINE: Audio energy detected: {energy:.2f}")
                          self._last_energy_log = time.time()

                result = await asyncio.to_thread(self._asr.feed_audio, pcm)

                if result:
                    # FORCE LOGGING TO INFO
                    logger.setLevel(logging.INFO)
                    
                    elapsed_ms = (time.time() - first_frame_time) * 1000 if first_frame_time else 0
                    logger.info(f"🔍 DEBUG: LocalSpeechStream received result: type={result['type']}, text='{result['text'][:50]}'")
                    
                    detected_lang = result.get("language") or self._language or "en"

                    if result["type"] == "partial":
                         # Only log if text changed significantly or periodically?
                         pass
                         self._event_ch.send_nowait(stt.SpeechEvent(
                             type=stt.SpeechEventType.INTERIM_TRANSCRIPT,
                             alternatives=[stt.SpeechData(text=result["text"], confidence=1.0, language=detected_lang)]
                         ))
                    elif result["type"] == "final":
                         logger.info(f"✅ STT: Final transcript ({elapsed_ms:.0f}ms): '{result['text']}'")
                         logger.info(f"🚀 EMITTING FINAL_TRANSCRIPT EVENT to Agent")
                         try:
                             self._event_ch.send_nowait(stt.SpeechEvent(
                                 type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                                 alternatives=[stt.SpeechData(text=result["text"], confidence=1.0, language=detected_lang)]
                             ))
                             logger.info(f"✅ FINAL_TRANSCRIPT EVENT SENT")
                         except Exception as e:
                             logger.error(f"❌ FAILED TO EMIT EVENT: {e}", exc_info=True)
        
        finally:
            # Always finalize on close (End of stream or Cancellation/Disconnect)
            logger.info("🎤 STT: Stream closed, finalizing...")
            try:
                # Use a shielded execution or just try to finalize if loop active
                finalize_start = time.time()
                final = await asyncio.to_thread(self._asr.finalize)
                finalize_duration = (time.time() - finalize_start) * 1000

                if final and final["text"]:
                     logger.info(f"✅ STT: Close-time Finalize ({finalize_duration:.0f}ms): '{final['text']}'")
                     final_lang = final.get("language") or self._language or "en"
                     try:
                         self._event_ch.send_nowait(stt.SpeechEvent(
                            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                            alternatives=[stt.SpeechData(text=final["text"], confidence=1.0, language=final_lang)]
                        ))
                     except Exception as e:
                         logger.warning(f"Could not emit final event on close: {e}")
                else:
                    logger.info("🎤 STT: No pending speech on close")
            except Exception as e:
                logger.error(f"Error checking pending speech on close: {e}") 
            
            self._event_ch.close()


class LocalTTS(tts.TTS):
    def __init__(self, config: TTSConfig = None, tts_instance: StreamingTTS = None):
        super().__init__(capabilities=tts.TTSCapabilities(streaming=True), sample_rate=48000, num_channels=1)
        self.config = config or TTSConfig()
        self.config.sample_rate = 48000 # Match livekit standard target
        # Use provided TTS instance (shared) or create new one (fallback)
        self._tts = tts_instance if tts_instance is not None else StreamingTTS(self.config)

    def _synthesize_impl(self, text: str):
        """
        Required abstract method implementation for LiveKit agents 1.x
        Note: VoicePipelineAgent uses stream(), not this method
        """
        raise NotImplementedError("Use stream() method for voice pipeline")

    def synthesize(self, text: str):
        """
        Non-streaming synthesis (not used by VoicePipelineAgent)
        """
        raise NotImplementedError("Use stream() method for voice pipeline")

    def stream(self, **kwargs) -> tts.SynthesizeStream:
        """
        Return a SynthesizeStream for streaming TTS synthesis.
        Required for LiveKit Voice Pipeline Agent to work.
        """
        # Accept any additional parameters (like conn_options) via **kwargs
        print("DEBUG: [LocalTTS] stream() called")
        logger.info("🔊 LocalTTS.stream() called - creating LocalTTSStream")
        stream = LocalTTSStream(tts_engine=self._tts)
        logger.info(f"🔊 LocalTTS.stream() returning stream: {stream}")
        return stream


# LocalSynthesizedAudio class removed - we create SynthesizedAudio directly in LocalTTSStream


class LocalTTSStream(tts.SynthesizeStream):
    """
    Streaming TTS adapter for LiveKit Voice Pipeline Agent.
    Implements the SynthesizeStream interface required by LiveKit Agents 1.x
    """
    def __init__(self, tts_engine: StreamingTTS):
        print("DEBUG: [LocalTTSStream] __init__ called")
        logger.info("🔊 TTS: LocalTTSStream.__init__ called")
        # Create a wrapper LocalTTS instance to pass to parent, using the shared engine
        local_tts = LocalTTS(TTSConfig(sample_rate=48000, fallback_to_piper=True), tts_instance=tts_engine)

        # Create a minimal APIConnectOptions if needed
        try:
            from livekit.agents.types import APIConnectOptions
            conn_options = APIConnectOptions()
        except:
            conn_options = None

        super().__init__(tts=local_tts, conn_options=conn_options)
        self._tts_engine = tts_engine
        self._closed = False
        logger.info("🔊 TTS: LocalTTSStream initialized")

    async def _run(self, output_emitter) -> None:
        """
        Required abstract method for SynthesizeStream.
        Runs the synthesis loop and emits audio frames using output_emitter callback.
        """
        import uuid
        import traceback
        import datetime
        
        debug_file = open("tts_debug.txt", "a")
        def log_debug(msg):
             print(f"DEBUG: {msg}")
             debug_file.write(f"{datetime.datetime.now()} - {msg}\n")
             debug_file.flush()
        
        log_debug("[LocalTTSStream] _run() called STARTED")
        logger.info("🔊 TTS: LocalTTSStream._run() called - starting synthesis loop")

        try:
            # Initialize emitter ONCE at the start of _run()
            # CRITICAL: Only call this ONCE per _run() instance!
            request_id = f"tts_{uuid.uuid4().hex[:8]}"
            
            log_debug(f"Initializing emitter with request_id={request_id}")
            output_emitter.initialize(
                request_id=request_id,
                sample_rate=48000,
                num_channels=1,
                mime_type="audio/pcm"
            )
            log_debug(f"🔊 TTS: Emitter initialized successfully")

            while not self._closed:
                try:
                    log_debug("Waiting for text input...")
                    text = await self._input_ch.recv()
                    log_debug(f"Received text: {str(text)[:50]}")
                except aio.ChanClosed:
                    log_debug("Input channel closed")
                    break

                if isinstance(text, tts.SynthesizeStream._FlushSentinel):
                    log_debug("Received FlushSentinel")
                    continue

                # Synthesize text to PCM bytes with timeout
                log_debug(f"Processing text: '{text[:20]}...'")
                synth_start = time.time()
                pcm_bytes = None
                
                # Check for FILE: prefix (Debugging/Ground Truth)
                if text.startswith("FILE:"):
                    try:
                        file_path = text[5:].strip()
                        if os.path.exists(file_path):
                            logger.info(f"📂 TTS: Playing WAV file directly: {file_path}")
                            import wave
                            with wave.open(file_path, "rb") as wf:
                                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 48000:
                                     logger.warning(f"⚠️ TTS: Wav file format mismatch! Playing anyway. (Ch={wf.getnchannels()}, W={wf.getsampwidth()}, R={wf.getframerate()})")
                                pcm_bytes = wf.readframes(wf.getnframes())
                                synth_duration = 0
                        else:
                             logger.error(f"❌ TTS: File not found: {file_path}")
                    except Exception as e:
                        logger.error(f"❌ TTS: Error reading file: {e}")

                # If not a file (or failed), synthesize
                if pcm_bytes is None: 
                    try:
                        log_debug(f"Calling synthesize_async for '{text[:20]}...'")
                        # Use new async synthesis to avoid threadpool exhaustion
                        pcm_bytes = await self._tts_engine.synthesize_async(text)
                        
                        synth_duration = (time.time() - synth_start) * 1000
                        log_debug(f"Synthesis returned {len(pcm_bytes) if pcm_bytes else 0} bytes in {synth_duration:.0f}ms")
                    except Exception as e:
                        log_debug(f"Synthesis ERROR: {e}")
                        logger.error(f"❌ TTS: Synthesis error: {e}")
                        continue

                if not pcm_bytes:
                    log_debug("PCM bytes is empty/None")
                    logger.warning(f"⚠️  TTS: No audio generated for text: {text[:50]}...")
                    continue

                if pcm_bytes:
                    # Piper usually outputs 22050Hz. LiveKit/WebRTC requires 48000Hz.
                    # 1. Convert bytes to int16 array
                    pcm_orig = np.frombuffer(pcm_bytes, dtype=np.int16)
                    
                    # 2. Resample 22050 -> 48000
                    # For simplicity, we use linear interpolation
                    orig_sr = 22050 # Known Piper rate from json configs
                    target_sr = 48000
                    
                    # Handle energy check before resampling
                    energy = np.sqrt(np.mean(pcm_orig.astype(float)**2))
                    logger.info(f"✅ TTS: Synthesized {len(pcm_orig)/orig_sr*1000:.0f}ms raw audio (Energy: {energy:.2f})")
                    
                    duration_sec = len(pcm_orig) / orig_sr
                    num_target_samples = int(duration_sec * target_sr)
                    
                    # Linear interpolation
                    indices = np.linspace(0, len(pcm_orig) - 1, num_target_samples)
                    pcm_48k = np.interp(indices, np.arange(len(pcm_orig)), pcm_orig).astype(np.int16)
                    
                    # 3. Chunk into 20ms frames (960 samples @ 48kHz)
                    SAMPLES_PER_FRAME = 960 # 48000 * 0.02
                    total_samples = len(pcm_48k)

                    # NOTE: Don't call initialize() again - already done at start of _run
                    # Calling it multiple times destroys previous tasks

                    # 4. Pace the emission
                    start_time = time.perf_counter()
                    for frame_idx, i in enumerate(range(0, total_samples, SAMPLES_PER_FRAME)):
                        upper = min(i + SAMPLES_PER_FRAME, total_samples)
                        chunk = pcm_48k[i:upper]
                        
                        # Pad last chunk if needed to maintain 20ms boundary
                        if len(chunk) < SAMPLES_PER_FRAME:
                            chunk = np.pad(chunk, (0, SAMPLES_PER_FRAME - len(chunk)))
                            
                        # Emit frame
                        output_emitter.push(chunk.tobytes())
                        
                        # Calculate when the next frame should be sent to maintain 20ms rhythm
                        # This compensates for any processing time spent in the loop
                        next_frame_time = start_time + (frame_idx + 1) * 0.02
                        sleep_duration = next_frame_time - time.perf_counter()
                        if sleep_duration > 0:
                            await asyncio.sleep(sleep_duration)
                        
                    # Signal completion of this text block
                    output_emitter.flush()
                    logger.info(f"🚀 TTS: Pushed {total_samples} samples (~{total_samples/target_sr:.2f}s) in 20ms chunks")

        except Exception as e:
            log_debug(f"CRITICAL ERROR in LocalTTSStream._run: {e}")
            log_debug(traceback.format_exc())
            logger.error(f"❌ TTS: LocalTTSStream error: {e}", exc_info=True)
            raise e
        finally:
            log_debug("[LocalTTSStream] _run() FINISHED/CLEANUP")
            try:
                debug_file.close()
            except:
                pass

    async def aclose(self):
        """Close the stream and cleanup resources."""
        try:
            self._closed = True
            logger.debug("LocalTTSStream closed successfully")
        except Exception as e:
            logger.error(f"Error closing LocalTTSStream: {e}")
        # Don't reset shared TTS engine - it's reused across sessions

