"""
Streaming ASR Service for BestBox S2S

Uses faster-whisper (CTranslate2) with VAD gating for real-time speech recognition.
Optimized for AMD ROCm performance (CPU Fallback enabled for stability).
"""

import numpy as np
import logging
import time
from collections import deque
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ASRConfig:
    """Configuration for streaming ASR."""
    model_size: str = "tiny"   # Optimized for CPU usage and speed
    device: str = "cpu"         # Force CPU to avoid ROCm/CUDA errors
    compute_type: str = "int8"  # Optimized for CPU speed
    language: str = "en"        # English - explicit for .en models
    sample_rate: int = 16000
    frame_ms: int = 20
    vad_aggressiveness: int = 3   # Strict (3) to prevent noise from keeping VAD open
    partial_interval: float = 1.0 # Buffer more audio before inference to reduce CPU load
    max_buffer_seconds: float = 30.0
    max_utterance_seconds: float = 15.0  # Force finalize after this duration to prevent infinite loops
    silence_threshold: float = 0.6       # Silence duration to trigger finalization


class StreamingASR:
    def __init__(self, config: Optional[ASRConfig] = None):
        self.config = config or ASRConfig()
        self._model = None
        self._vad = None
        
        # Audio buffering
        self.frame_size = int(self.config.sample_rate * self.config.frame_ms / 1000)
        self.max_buffer_samples = int(self.config.sample_rate * self.config.max_buffer_seconds)
        
        # State
        self.buffer = deque(maxlen=self.max_buffer_samples)
        self.speech_buffer: list = []
        self.last_partial_time: float = 0
        self.is_speaking: bool = False
        self.speech_start_time: float = 0
        self._last_emit: float = 0  # Track last partial emission time
        
        # Statistics
        self.total_audio_ms: float = 0
        self.total_speech_ms: float = 0
        
    @property
    def model(self):
        """Lazy load the Faster-Whisper model."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(f"Loading faster-whisper model: {self.config.model_size} on {self.config.device}")
                
                self._model = WhisperModel(
                    self.config.model_size,
                    device=self.config.device,
                    compute_type=self.config.compute_type
                )
                logger.info("Faster-Whisper model loaded successfully")
            except ImportError:
                logger.error("faster-whisper not installed. Run: pip install faster-whisper")
                raise
            except Exception as e:
                logger.warning(f"Failed to load model on {self.config.device}: {e}")
                if self.config.device != "cpu":
                    logger.info("Falling back to CPU...")
                    self.config.device = "cpu"
                    self.config.compute_type = "int8"
                    self._model = WhisperModel(
                        self.config.model_size,
                        device="cpu",
                        compute_type="int8"
                    )
                    logger.info("Model loaded on CPU (fallback)")
                else:
                    raise
        return self._model
    
    @property
    def vad(self):
        """Lazy load the VAD."""
        if self._vad is None:
            try:
                import webrtcvad
                self._vad = webrtcvad.Vad(self.config.vad_aggressiveness)
                logger.info(f"VAD initialized with aggressiveness={self.config.vad_aggressiveness}")
            except ImportError:
                logger.error("webrtcvad not installed. Run: pip install webrtcvad")
                raise
        return self._vad
    
    def reset(self):
        """Reset buffers."""
        self.buffer.clear()
        self.speech_buffer.clear()
        self.last_partial_time = 0
        self.is_speaking = False
        self.speech_start_time = 0
        self._last_emit = 0  # Reset partial emission timer
        logger.debug("ASR state reset")
    
    def set_language(self, language: str):
        """Set recognition language. Empty string = auto-detect."""
        self.config.language = language if language and language != "auto" else ""
        logger.info(f"ASR language set to: {language if language else 'auto-detect'}")
    
    def feed_audio(self, pcm: np.ndarray) -> Optional[Dict[str, Any]]:
        """Feed audio chunk and return partial result."""
        if pcm.dtype != np.int16:
            pcm = pcm.astype(np.int16)
        
        self.buffer.extend(pcm.tolist())
        result = None
        
        while len(self.buffer) >= self.frame_size:
            frame = np.array([self.buffer.popleft() for _ in range(self.frame_size)], dtype=np.int16)
            
            # Always accumulate audio (Push-to-Talk style)
            # We rely on specific 'audio_end' signals or max buffer size
            # and Whisper's internal VAD during inference to filter silence.
            self.speech_buffer.extend(frame.tolist())
            
            # Use VAD + RMS energy check for triggering "partial" updates (activity detection)
            is_speech = self.vad.is_speech(frame.tobytes(), self.config.sample_rate)
            
            # Simple RMS energy check to filter out ambient noise that mimics speech
            # For 16-bit PCM, values are +/- 32768. 
            # 100-200 is a reasonable noise floor for many mics.
            rms = np.sqrt(np.mean(frame.astype(np.float32)**2))
            is_loud_enough = rms > 300  # Adjustable threshold
            
            if is_speech and is_loud_enough:
                if not self.is_speaking:
                    self.is_speaking = True
                    self.speech_start_time = time.time()
                self.last_partial_time = time.time()  # Keep alive
            elif not is_loud_enough and self.is_speaking:
                # If it's too quiet, don't update last_partial_time, 
                # allowing the silence_threshold (0.6s) to eventually trigger finalize.
                pass
            
            # Emit partial if enough time passed AND we recently heard speech
            now = time.time()
            time_since_last_emit = now - self._last_emit
            has_recent_speech = self.is_speaking and (now - self.last_partial_time < 1.0)
            has_enough_audio = len(self.speech_buffer) >= self.config.sample_rate * 0.5  # At least 0.5s of audio
            
            if has_recent_speech and has_enough_audio and time_since_last_emit >= self.config.partial_interval:
                text, lang = self._transcribe_buffer()
                if text.strip():
                    result = {
                        "type": "partial",
                        "text": text,
                        "language": lang,
                        "duration_ms": int((now - self.speech_start_time) * 1000)
                    }
                self._last_emit = now

            # Check for end of speech (silence timeout)
            # If we were speaking, but haven't heard speech for > 1.0s (silence threshold), finalize.
            # We can make this configurable in ASRConfig later.
            silence_duration = now - self.last_partial_time
            if self.is_speaking:
                current_utterance_duration = now - self.speech_start_time
                
                # watchdog: Force finalize if utterance is too long (hallucination guard)
                if current_utterance_duration > self.config.max_utterance_seconds:
                    logger.warning(f"⚠️ ASR Watchdog: Utterance too long ({current_utterance_duration:.1f}s > {self.config.max_utterance_seconds}s). Forcing finalize.")
                    final_res = self.finalize()
                    if final_res and final_res["text"]:
                        result = final_res
                
                # Normal silence detection
                elif silence_duration > self.config.silence_threshold:
                    logger.info(f"Silence detected ({silence_duration:.2f}s), finalizing speech segment.")
                    final_res = self.finalize()
                    logger.info(f"🔍 DEBUG: final_res={final_res}, has_text={bool(final_res and final_res.get('text'))}")
                    if final_res and final_res.get("text"):
                        logger.info(f"🎯 RETURNING FINAL RESULT: '{final_res['text']}'")
                        result = final_res
                    else:
                        logger.warning(f"⚠️  Finalize returned empty text, NOT returning result")
                 
        return result
    
    def finalize(self) -> Dict[str, Any]:
        """Get final transcription."""
        buffer_duration = len(self.speech_buffer) / self.config.sample_rate
        logger.info(f"🔚 Finalize called: buffer has {buffer_duration:.2f}s of audio ({len(self.speech_buffer)} samples). PID: {id(self)}")
        
        if not self.speech_buffer:
            self.is_speaking = False
            logger.warning("⚠️  Finalize: Empty speech buffer!")
            return {"type": "final", "text": ""}

        # Require minimum audio duration for final transcription
        if buffer_duration < 0.3:
            logger.warning(f"⚠️  Finalize: Buffer too short ({buffer_duration:.2f}s < 0.3s), skipping transcription")
            self.speech_buffer.clear()
            self.is_speaking = False
            return {"type": "final", "text": ""}

        text, lang = self._transcribe_buffer()
        logger.info(f"✅ Finalize result: '{text}' ({lang}) (from {buffer_duration:.2f}s audio)")
        
        # CLEAR BUFFER
        prev_len = len(self.speech_buffer)
        self.speech_buffer.clear()
        self.is_speaking = False
        
        # VERIFY CLEAR
        if len(self.speech_buffer) != 0:
             logger.error(f"❌ CRITICAL: speech_buffer.clear() FAILED! Len is {len(self.speech_buffer)}")
        else:
             logger.info(f"✨ Buffer cleared successfully (was {prev_len} samples)")

        return {"type": "final", "text": text.strip(), "language": lang}
    
    def _transcribe_buffer(self) -> tuple[str, str]:
        if not self.speech_buffer:
            return "", "en"
            
        # faster-whisper expects float32
        audio = np.array(self.speech_buffer, dtype=np.int16).astype(np.float32) / 32768.0
        
        try:
            start_time = time.time()
            
            # Use language=None for auto-detection, or specific language if set
            language = self.config.language if self.config.language else None
            
            segments, info = self.model.transcribe(
                audio,
                language=language,
                beam_size=1,
                vad_filter=False,  # Disable aggressive filter as it was deleting real speech
                log_prob_threshold=None,  # Accept all transcripts regardless of log prob
                no_speech_threshold=0.95  # Very lenient - transcribe even if no_speech prob is high
            )
            
            text = " ".join([segment.text for segment in segments])
            
            elapsed = time.time() - start_time
            detected_lang = info.language if hasattr(info, 'language') else 'en'
            logger.info(f"Inference: {elapsed:.3f}s (Audio: {len(audio)/16000:.2f}s, Lang: {detected_lang}) -> '{text[:50]}...'")
            return text.strip(), detected_lang
            
        except Exception as e:
            logger.error(f"Transcribe error: {e}")
            return "", "en"


class ASRPool:
    """Pool of ASR instances."""
    def __init__(self, config: Optional[ASRConfig] = None, max_sessions: int = 10):
        self.config = config or ASRConfig()
        self.max_sessions = max_sessions
        self._shared_model = None
        self._sessions: Dict[str, StreamingASR] = {}
        
    def get_session(self, session_id: str) -> StreamingASR:
        if session_id not in self._sessions:
            if len(self._sessions) >= self.max_sessions:
                oldest = next(iter(self._sessions))
                del self._sessions[oldest]
            
            asr = StreamingASR(self.config)
            # Share model instance
            if self._shared_model is not None:
                asr._model = self._shared_model
                
            self._sessions[session_id] = asr
            
            if self._shared_model is None and asr._model is not None:
                self._shared_model = asr._model
                
        return self._sessions[session_id]
    
    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            
    def cleanup(self):
        self._sessions.clear()
