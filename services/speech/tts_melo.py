"""
MeloTTS Engine for BestBox S2S

Uses MyShell's MeloTTS for high-quality Chinese TTS.
Optimized for P100 GPU (SM60) with CPU fallback.
"""

import numpy as np
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class MeloTTSConfig:
    """Configuration for MeloTTS engine."""
    # Device settings
    device: str = "cuda:1"  # P100
    fallback_device: str = "cpu"

    # Model settings
    language: str = "ZH"  # Chinese primary (handles mixed English)

    # Audio settings
    speed: float = 1.0
    output_sample_rate: int = 24000  # Target rate for client

    # MeloTTS native rate is 44100, we'll resample


class MeloTTSEngine:
    """
    MeloTTS-based TTS engine.

    Features:
    - High-quality Chinese voice synthesis
    - Supports mixed Chinese + English text
    - GPU acceleration on P100 with CPU fallback
    - Interface compatible with existing TTS

    Usage:
        engine = MeloTTSEngine()
        audio = engine.synthesize("你好，世界！")
    """

    def __init__(self, config: Optional[MeloTTSConfig] = None):
        self.config = config or MeloTTSConfig()
        self._model = None
        self._speaker_id = None
        self._actual_device = None
        self._native_sample_rate = 44100  # MeloTTS default

    @property
    def model(self):
        """Lazy load the MeloTTS model."""
        if self._model is None:
            self._load_model()
        return self._model

    @property
    def sample_rate(self) -> int:
        """Output sample rate (after resampling)."""
        return self.config.output_sample_rate

    def _load_model(self):
        """Load MeloTTS model with GPU/CPU fallback."""
        try:
            from melo.api import TTS
            import torch

            device = self.config.device

            # Check CUDA availability
            if device.startswith("cuda"):
                device_id = int(device.split(":")[1]) if ":" in device else 0
                if not torch.cuda.is_available():
                    logger.warning("CUDA not available, falling back to CPU")
                    device = self.config.fallback_device
                elif device_id >= torch.cuda.device_count():
                    logger.warning(f"CUDA device {device_id} not found, falling back to CPU")
                    device = self.config.fallback_device

            logger.info(f"Loading MeloTTS model (language={self.config.language}, device={device})")

            self._model = TTS(language=self.config.language, device=device)
            self._actual_device = device

            # Get speaker ID for the language
            speaker_ids = self._model.hps.data.spk2id
            logger.info(f"Available speakers: {list(speaker_ids.keys())}")

            # Use primary language speaker
            if self.config.language in speaker_ids:
                self._speaker_id = speaker_ids[self.config.language]
            else:
                # Fallback to first available speaker
                self._speaker_id = list(speaker_ids.values())[0]

            logger.info(f"MeloTTS loaded successfully on {device}, speaker_id={self._speaker_id}")

        except ImportError as e:
            logger.error(f"MeloTTS not installed: {e}")
            logger.error("Run: pip install melo-tts")
            raise
        except Exception as e:
            logger.error(f"Failed to load MeloTTS: {e}")
            # Try CPU fallback
            if self.config.device != "cpu":
                logger.info("Attempting CPU fallback...")
                try:
                    from melo.api import TTS
                    self._model = TTS(language=self.config.language, device="cpu")
                    self._actual_device = "cpu"
                    speaker_ids = self._model.hps.data.spk2id
                    self._speaker_id = speaker_ids.get(self.config.language, list(speaker_ids.values())[0])
                    logger.info("MeloTTS loaded on CPU (fallback)")
                except Exception as e2:
                    logger.error(f"CPU fallback also failed: {e2}")
                    raise
            else:
                raise

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate."""
        if orig_sr == target_sr:
            return audio

        try:
            from scipy import signal
            # Calculate number of samples in resampled audio
            num_samples = int(len(audio) * target_sr / orig_sr)
            resampled = signal.resample(audio, num_samples)
            return resampled.astype(audio.dtype)
        except ImportError:
            logger.warning("scipy not available, using simple resampling")
            # Simple linear interpolation fallback
            ratio = target_sr / orig_sr
            indices = np.arange(0, len(audio), 1 / ratio)
            indices = indices[indices < len(audio)].astype(int)
            return audio[indices]

    def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        speed: Optional[float] = None
    ) -> bytes:
        """
        Synthesize text to PCM16 audio.

        Args:
            text: Text to synthesize
            language: Language hint (optional, uses config default)
            speed: Speaking speed multiplier (optional)

        Returns:
            PCM16 audio bytes at configured output sample rate
        """
        if not text or not text.strip():
            return b""

        try:
            start_time = time.time()

            speed = speed or self.config.speed

            # Ensure model is loaded
            _ = self.model

            # Synthesize with MeloTTS
            # Returns numpy array at native sample rate (44100)
            audio = self._model.tts_to_file(
                text=text,
                speaker_id=self._speaker_id,
                speed=speed,
                output_path=None,  # Return array, don't save to file
            )

            # Handle case where tts_to_file returns None
            if audio is None:
                # Try alternative method
                audio = self._model.tts(
                    text=text,
                    speaker_id=self._speaker_id,
                    speed=speed,
                )

            if audio is None:
                logger.error("TTS returned None")
                return b""

            # Convert to numpy array if needed
            if not isinstance(audio, np.ndarray):
                audio = np.array(audio)

            # Resample to output rate
            if self._native_sample_rate != self.config.output_sample_rate:
                audio = self._resample(
                    audio,
                    self._native_sample_rate,
                    self.config.output_sample_rate
                )

            # Convert to PCM16
            if audio.dtype != np.int16:
                # Normalize if float
                if np.issubdtype(audio.dtype, np.floating):
                    audio = np.clip(audio, -1.0, 1.0)
                    audio = (audio * 32767).astype(np.int16)
                else:
                    audio = audio.astype(np.int16)

            elapsed = time.time() - start_time
            rtf = elapsed / (len(audio) / self.config.output_sample_rate)
            logger.debug(f"TTS: '{text[:30]}...' -> {len(audio)} samples, RTF={rtf:.2f}")

            return audio.tobytes()

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            import traceback
            traceback.print_exc()
            return b""

    async def synthesize_async(
        self,
        text: str,
        language: Optional[str] = None,
        speed: Optional[float] = None
    ) -> bytes:
        """
        Async version of synthesize.

        Runs synthesis in thread pool to avoid blocking.
        """
        return await asyncio.to_thread(
            self.synthesize,
            text,
            language,
            speed
        )

    def get_available_languages(self) -> List[str]:
        """Get list of supported languages."""
        try:
            if self._model is not None:
                return list(self._model.hps.data.spk2id.keys())
        except:
            pass
        return ["ZH", "EN"]

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "device": self._actual_device or self.config.device,
            "language": self.config.language,
            "output_sample_rate": self.config.output_sample_rate,
            "native_sample_rate": self._native_sample_rate,
            "model_loaded": self._model is not None
        }


class SpeechBuffer:
    """
    Buffer LLM tokens and emit synthesizable phrases.

    Compatible with existing SpeechBuffer interface.
    """

    def __init__(
        self,
        min_chars: int = 30,
        max_chars: int = 200,
        terminators: Optional[tuple] = None
    ):
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.terminators = terminators or (
            # Chinese
            "。", "？", "！", "；",
            # English
            ".", "?", "!", ";",
            # Line breaks
            "\n"
        )
        self.soft_breaks = (",", "，", "、", ":", "：", " ")

        self.buffer = ""
        self.total_chars = 0
        self.phrases_emitted = 0

    def add(self, token: str) -> Optional[str]:
        """Add token, return phrase if ready for synthesis."""
        if not token:
            return None

        self.buffer += token
        self.total_chars += len(token)

        # Check for sentence terminator
        if self.buffer.rstrip().endswith(self.terminators):
            phrase = self.buffer
            self.buffer = ""
            self.phrases_emitted += 1
            return phrase

        # Check max length - force emit
        if len(self.buffer) >= self.max_chars:
            for i in range(len(self.buffer) - 1, -1, -1):
                if self.buffer[i] in self.soft_breaks:
                    phrase = self.buffer[:i + 1]
                    self.buffer = self.buffer[i + 1:]
                    self.phrases_emitted += 1
                    return phrase
            phrase = self.buffer
            self.buffer = ""
            self.phrases_emitted += 1
            return phrase

        # Check min length with soft break
        if len(self.buffer) >= self.min_chars:
            if self.buffer.rstrip().endswith(self.soft_breaks):
                phrase = self.buffer
                self.buffer = ""
                self.phrases_emitted += 1
                return phrase

        return None

    def flush(self) -> Optional[str]:
        """Flush remaining buffer."""
        if self.buffer.strip():
            phrase = self.buffer
            self.buffer = ""
            self.phrases_emitted += 1
            return phrase
        self.buffer = ""
        return None

    def clear(self):
        """Clear buffer without emitting."""
        self.buffer = ""

    def get_stats(self) -> Dict[str, Any]:
        """Get buffering statistics."""
        return {
            "total_chars": self.total_chars,
            "phrases_emitted": self.phrases_emitted,
            "current_buffer_size": len(self.buffer),
            "avg_phrase_length": self.total_chars / max(1, self.phrases_emitted)
        }


# Standalone test
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("Testing MeloTTS Engine...")
    print("=" * 50)

    # Test initialization
    config = MeloTTSConfig(device="cuda:1")
    engine = MeloTTSEngine(config)

    print(f"Config: device={config.device}, language={config.language}")

    # Test model loading
    print("\nLoading model...")
    _ = engine.model
    print(f"Model loaded on {engine._actual_device}")
    print(f"Available languages: {engine.get_available_languages()}")

    # Test synthesis
    print("\nTesting synthesis...")
    test_texts = [
        "你好，世界！",
        "Hello, world!",
        "今天天气怎么样？How is the weather today?",
    ]

    for text in test_texts:
        print(f"\nSynthesizing: '{text}'")
        start = time.time()
        audio = engine.synthesize(text)
        elapsed = time.time() - start
        samples = len(audio) // 2  # PCM16 = 2 bytes per sample
        duration = samples / config.output_sample_rate
        print(f"  -> {samples} samples ({duration:.2f}s audio) in {elapsed:.3f}s")

    print("\n" + "=" * 50)
    print("MeloTTS Engine test complete!")
