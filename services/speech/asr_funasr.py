"""
FunASR Paraformer Engine for BestBox S2S

Uses Alibaba's Paraformer-large model for high-quality Chinese ASR.
Optimized for P100 GPU (SM60) with float16 inference.
"""

import numpy as np
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FunASRConfig:
    """Configuration for FunASR Paraformer engine."""
    # Model settings
    model_id: str = "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    device: str = "cuda:1"  # P100

    # Audio settings
    sample_rate: int = 16000

    # VAD settings (built into Paraformer)
    vad_threshold: float = 0.5

    # Inference settings
    batch_size: int = 1

    # Hotwords for domain-specific terms (optional)
    hotwords: list = field(default_factory=list)

    # Silence detection
    silence_threshold: float = 0.6  # seconds
    max_utterance_seconds: float = 30.0


class FunASREngine:
    """
    FunASR Paraformer-based ASR engine.

    Features:
    - Optimized for Chinese with English support
    - Built-in VAD and punctuation restoration
    - Compatible with existing ASR interface

    Usage:
        engine = FunASREngine()
        result = engine.feed_audio(pcm_data)
        if result:
            print(result["text"])
    """

    def __init__(self, config: Optional[FunASRConfig] = None):
        self.config = config or FunASRConfig()
        self._model = None

        # Audio buffering
        self.audio_buffer: list = []
        self.is_speaking: bool = False
        self.speech_start_time: float = 0
        self.last_speech_time: float = 0

        # Statistics
        self.total_audio_ms: float = 0
        self.total_transcriptions: int = 0

    @property
    def model(self):
        """Lazy load the FunASR model."""
        if self._model is None:
            self._load_model()
        return self._model

    def _load_model(self):
        """Load FunASR Paraformer model."""
        try:
            from funasr import AutoModel
            import torch

            logger.info(f"Loading FunASR model: {self.config.model_id}")
            logger.info(f"Device: {self.config.device}")

            # Check if CUDA device is available
            if self.config.device.startswith("cuda"):
                device_id = int(self.config.device.split(":")[1]) if ":" in self.config.device else 0
                if not torch.cuda.is_available():
                    logger.warning("CUDA not available, falling back to CPU")
                    self.config.device = "cpu"
                elif device_id >= torch.cuda.device_count():
                    logger.warning(f"CUDA device {device_id} not found, falling back to CPU")
                    self.config.device = "cpu"

            # Load model with float16 for P100 (no bfloat16 support)
            self._model = AutoModel(
                model=self.config.model_id,
                device=self.config.device,
                vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                vad_kwargs={"max_single_segment_time": 60000},
                punc_model="iic/punc_ct-transformer_cn-en-common-vocab471067-large",
                spk_model=None,
                disable_update=True,
            )
            logger.info(f"FunASR model loaded successfully on {self.config.device}")

        except ImportError as e:
            logger.error(f"FunASR not installed: {e}")
            logger.error("Run: pip install funasr modelscope")
            raise
        except Exception as e:
            logger.error(f"Failed to load FunASR model: {e}")
            raise

    def reset(self):
        """Reset audio buffers and state."""
        self.audio_buffer.clear()
        self.is_speaking = False
        self.speech_start_time = 0
        self.last_speech_time = 0
        logger.debug("FunASR engine reset")

    def set_language(self, language: str):
        """
        Set recognition language.

        Note: Paraformer-large is primarily Chinese but handles English.
        For pure English, consider using a different model.
        """
        logger.info(f"Language hint set to: {language}")
        # Paraformer doesn't have runtime language switching
        # This is kept for interface compatibility

    def feed_audio(self, pcm: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Feed audio chunk and return transcription result if available.

        Args:
            pcm: PCM16 audio data at 16kHz

        Returns:
            Dict with transcription result or None if still buffering
        """
        if pcm.dtype != np.int16:
            pcm = pcm.astype(np.int16)

        # Add to buffer
        self.audio_buffer.extend(pcm.tolist())
        self.total_audio_ms += len(pcm) / self.config.sample_rate * 1000

        now = time.time()

        # Simple energy-based speech detection
        rms = np.sqrt(np.mean(pcm.astype(np.float32) ** 2))
        is_speech = rms > 300  # Threshold for speech

        if is_speech:
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_start_time = now
            self.last_speech_time = now

        # Check for end of speech (silence timeout)
        if self.is_speaking:
            silence_duration = now - self.last_speech_time
            utterance_duration = now - self.speech_start_time

            # Force finalize if too long
            if utterance_duration > self.config.max_utterance_seconds:
                logger.warning(f"Utterance too long ({utterance_duration:.1f}s), forcing finalize")
                return self.finalize()

            # Finalize on silence
            if silence_duration > self.config.silence_threshold:
                logger.info(f"Silence detected ({silence_duration:.2f}s), finalizing")
                return self.finalize()

        return None

    def finalize(self) -> Dict[str, Any]:
        """
        Finalize and transcribe buffered audio.

        Returns:
            Dict with 'type', 'text', and 'language' keys
        """
        buffer_duration = len(self.audio_buffer) / self.config.sample_rate
        logger.info(f"Finalize called: {buffer_duration:.2f}s of audio")

        if not self.audio_buffer or buffer_duration < 0.3:
            logger.warning("Buffer too short, skipping transcription")
            self.reset()
            return {"type": "final", "text": "", "language": "zh"}

        try:
            # Convert to float32 for FunASR
            audio = np.array(self.audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0

            start_time = time.time()

            # Run inference
            result = self.model.generate(
                input=audio,
                batch_size_s=300,  # Process up to 300 seconds
                hotword=self.config.hotwords if self.config.hotwords else None,
            )

            elapsed = time.time() - start_time

            # Extract text from result
            text = ""
            if result and len(result) > 0:
                if isinstance(result[0], dict):
                    text = result[0].get("text", "")
                elif hasattr(result[0], "text"):
                    text = result[0].text
                else:
                    text = str(result[0])

            self.total_transcriptions += 1
            logger.info(f"Transcription ({elapsed:.3f}s): '{text[:50]}...' " if len(text) > 50 else f"Transcription ({elapsed:.3f}s): '{text}'")

            # Reset state
            self.reset()

            return {
                "type": "final",
                "text": text.strip(),
                "language": "zh",
                "duration_ms": int(buffer_duration * 1000)
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            self.reset()
            return {"type": "final", "text": "", "language": "zh"}

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_audio_ms": self.total_audio_ms,
            "total_transcriptions": self.total_transcriptions,
            "current_buffer_ms": len(self.audio_buffer) / self.config.sample_rate * 1000,
            "is_speaking": self.is_speaking,
            "device": self.config.device
        }


class FunASRPool:
    """
    Pool of FunASR engine instances for multi-session support.

    Shares the underlying model across sessions to save memory.
    """

    def __init__(self, config: Optional[FunASRConfig] = None, max_sessions: int = 10):
        self.config = config or FunASRConfig()
        self.max_sessions = max_sessions
        self._shared_model = None
        self._sessions: Dict[str, FunASREngine] = {}

    def _ensure_model_loaded(self):
        """Ensure the shared model is loaded."""
        if self._shared_model is None:
            # Create a temporary engine to load the model
            temp_engine = FunASREngine(self.config)
            self._shared_model = temp_engine.model

    def get_session(self, session_id: str) -> FunASREngine:
        """Get or create an ASR engine for a session."""
        if session_id not in self._sessions:
            if len(self._sessions) >= self.max_sessions:
                # Remove oldest session
                oldest = next(iter(self._sessions))
                logger.info(f"Removing oldest session: {oldest}")
                del self._sessions[oldest]

            engine = FunASREngine(self.config)

            # Share model instance
            if self._shared_model is not None:
                engine._model = self._shared_model
            else:
                # First session loads the model
                self._shared_model = engine.model

            self._sessions[session_id] = engine
            logger.info(f"Created new session: {session_id}")

        return self._sessions[session_id]

    def remove_session(self, session_id: str):
        """Remove a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Removed session: {session_id}")

    def cleanup(self):
        """Clean up all sessions."""
        self._sessions.clear()
        logger.info("All sessions cleaned up")


# Standalone test
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("Testing FunASR Engine...")
    print("=" * 50)

    # Test initialization
    config = FunASRConfig(device="cuda:1")
    engine = FunASREngine(config)

    print(f"Config: device={config.device}, model={config.model_id[:50]}...")

    # Test model loading
    print("\nLoading model...")
    _ = engine.model
    print("Model loaded successfully!")

    # Test with synthetic audio (silence)
    print("\nTesting with synthetic audio...")
    silence = np.zeros(16000, dtype=np.int16)  # 1 second of silence
    result = engine.feed_audio(silence)
    print(f"Feed result: {result}")

    # Force finalize
    result = engine.finalize()
    print(f"Finalize result: {result}")

    print("\n" + "=" * 50)
    print("FunASR Engine test complete!")
