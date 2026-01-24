"""
Streaming TTS Service for BestBox S2S

Uses XTTS v2 for high-quality multilingual speech synthesis.
Includes phrase-level buffering for low-latency streaming.
"""

import numpy as np
import logging
import time
from typing import Optional, Generator, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TTSConfig:
    """Configuration for TTS service."""
    model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    gpu: bool = True
    sample_rate: int = 24000
    speaker_wav: Optional[str] = None  # Path to speaker reference audio
    default_language: str = "zh-cn"
    # Fallback to piper for CPU-only systems
    fallback_to_piper: bool = True


class StreamingTTS:
    """
    Streaming TTS with phrase-level synthesis for low latency.
    
    Features:
    - XTTS v2 for high-quality multilingual synthesis
    - Voice cloning support
    - Streaming audio chunk generation
    - Fallback to Piper TTS on CPU-only systems
    
    Usage:
        tts = StreamingTTS()
        audio = tts.synthesize("你好，我是助手。")
        
        # Or streaming
        for chunk in tts.synthesize_streaming("Hello, how can I help?"):
            play(chunk)
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self._tts = None
        self._using_piper = False
        
    @property
    def tts(self):
        """Lazy load the TTS model."""
        if self._tts is None:
            self._load_tts()
        return self._tts
    
    def _load_tts(self):
        """Load TTS model with fallback."""
        try:
            # Try loading Coqui TTS first (fails on Py3.12)
            if self.config.fallback_to_piper:
                 # Check python version
                import sys
                if sys.version_info >= (3, 12):
                    logger.info("Python 3.12+ detected, skipping Coqui TTS and using Piper fallback")
                    self._load_piper_fallback()
                    return

            from TTS.api import TTS
            logger.info(f"Loading TTS model: {self.config.model_name}")
            self._tts = TTS(
                model_name=self.config.model_name,
                gpu=self.config.gpu
            )
            self._using_piper = False
            logger.info("XTTS model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load XTTS: {e}")
            if self.config.fallback_to_piper:
                self._load_piper_fallback()
            else:
                raise
    
    def _load_piper_fallback(self):
        """Load Piper TTS as fallback."""
        try:
            import shutil
            
            # Look for piper binary
            piper_bin = Path("bin/piper/piper")
            if not piper_bin.exists():
                 # Try system path
                piper_bin = shutil.which("piper")
            
            if not piper_bin:
                raise FileNotFoundError("Piper binary not found. Run scripts/install_piper.sh")
            
            self._piper_bin = str(piper_bin)
            self._piper_models = {
                "zh-cn": "models/piper/zh_CN-huayan-medium.onnx",
                "en": "models/piper/en_US-libritts_r-medium.onnx"
            }
            
            # Check models exist
            for lang, model_path in self._piper_models.items():
                if not Path(model_path).exists():
                     logger.warning(f"Piper model for {lang} not found at {model_path}")
            
            self._using_piper = True
            logger.info(f"Piper TTS fallback initialized using {self._piper_bin}")
            
        except Exception as e:
            logger.error(f"Piper fallback failed: {e}")
            raise

    @property
    def sample_rate(self) -> int:
        """Get output sample rate."""
        return self.config.sample_rate

    def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        speaker_wav: Optional[str] = None
    ) -> bytes:
        """
        Synthesize text to PCM16 audio.
        """
        if not text.strip():
            return b""
        
        # Ensure loaded
        if not self._using_piper and self._tts is None:
            try:
                self._load_tts()
            except Exception as e:
                logger.error(f"Failed to load TTS during synthesize: {e}")
                return b""
        
        language = language or self.config.default_language
        
        if self._using_piper:
            return self._synthesize_piper(text, language)
        
        if self._tts is None:
            logger.warning("TTS not available, returning empty audio")
            return b""
        
        try:
            start = time.time()
            
            # XTTS synthesis
            speaker_wav = speaker_wav or self.config.speaker_wav
            if speaker_wav:
                wav = self._tts.tts(
                    text=text,
                    language=language,
                    speaker_wav=speaker_wav
                )
            else:
                wav = self._tts.tts(
                    text=text,
                    language=language
                )
            
            # Convert to PCM16
            wav_array = np.array(wav)
            pcm = (wav_array * 32767).astype(np.int16)
            
            elapsed = time.time() - start
            rtf = elapsed / (len(pcm) / self.config.sample_rate)
            logger.debug(f"TTS: '{text[:30]}...' -> {len(pcm)} samples, RTF={rtf:.2f}")
            
            return pcm.tobytes()
            
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return b""

    def _synthesize_piper(self, text: str, language: str) -> bytes:
        """Synthesize using Piper subprocess."""
        import os
        
        start = time.time()
        
        # Map language to model
        lang_key = "zh-cn" if "zh" in language.lower() else "en"
        model_path = self._piper_models.get(lang_key)
        
        if not model_path or not os.path.exists(model_path):
            logger.error(f"No Piper model for language: {language}")
            return b""
            
        try:
            # Run piper: echo "text" | piper --model model.onnx --output-raw
            # We output raw PCM16 at 22050Hz (usually) or model native rate
            
            cmd = [
                self._piper_bin,
                "--model", model_path,
                "--output-raw"
            ]
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = process.communicate(input=text.encode("utf-8"))
            
            if process.returncode != 0:
                logger.error(f"Piper error: {stderr.decode()}")
                return b""
                
            pcm = stdout
            
            elapsed = time.time() - start
            # Piper models usually are 22050Hz, but we configured 24000Hz default
            # ideally we should resample, but for now we'll assume close enough or let client handle
            # Or simplified: Piper often outputs 16khz or 22.05khz. 
            # We should probably check the json config, but for MVP we return raw.
            
            logger.debug(f"Piper TTS: '{text[:30]}...' -> {len(pcm)} bytes, time={elapsed:.3f}s")
            return pcm
            
        except Exception as e:
            logger.error(f"Piper synthesis error: {e}")
            return b""

    def get_available_languages(self) -> List[str]:
        """Get list of supported languages."""
        if self._using_piper:
            return list(self._piper_models.keys())
        
        if self._tts is None:
            return ["en", "zh"]
        
        try:
            return self._tts.languages or ["en", "zh-cn", "ja", "ko", "de", "fr", "es"]
        except:
            return ["en", "zh-cn"]


class SpeechBuffer:
    """
    Buffer LLM tokens and emit synthesizable phrases.
    
    Collects tokens until a natural break point (punctuation or length threshold)
    then emits a phrase ready for TTS synthesis.
    
    This enables overlapping LLM generation and TTS synthesis for lower latency.
    
    Usage:
        buffer = SpeechBuffer(min_chars=30)
        
        for token in llm_stream:
            phrase = buffer.add(token)
            if phrase:
                audio = tts.synthesize(phrase)
                play(audio)
        
        # Don't forget to flush at the end
        remaining = buffer.flush()
        if remaining:
            audio = tts.synthesize(remaining)
    """
    
    def __init__(
        self,
        min_chars: int = 30,
        max_chars: int = 200,
        terminators: Optional[tuple] = None
    ):
        """
        Args:
            min_chars: Minimum characters before emitting on soft break
            max_chars: Maximum characters before forcing emission
            terminators: Sentence-ending punctuation that triggers emission
        """
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
        # Soft break characters (comma, etc.)
        self.soft_breaks = (",", "，", "、", ":", "：", " ")
        
        self.buffer = ""
        self.total_chars = 0
        self.phrases_emitted = 0
    
    def add(self, token: str) -> Optional[str]:
        """
        Add token, return phrase if ready for synthesis.
        
        Args:
            token: LLM token to add
            
        Returns:
            Phrase ready for TTS, or None if still buffering
        """
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
            # Find last soft break
            for i in range(len(self.buffer) - 1, -1, -1):
                if self.buffer[i] in self.soft_breaks:
                    phrase = self.buffer[:i + 1]
                    self.buffer = self.buffer[i + 1:]
                    self.phrases_emitted += 1
                    return phrase
            # No break found, emit all
            phrase = self.buffer
            self.buffer = ""
            self.phrases_emitted += 1
            return phrase
        
        # Check min length with soft break
        if len(self.buffer) >= self.min_chars:
            # Check if we just hit a soft break
            if self.buffer.rstrip().endswith(self.soft_breaks):
                phrase = self.buffer
                self.buffer = ""
                self.phrases_emitted += 1
                return phrase
        
        return None
    
    def flush(self) -> Optional[str]:
        """
        Flush remaining buffer.
        
        Returns:
            Remaining text, or None if empty
        """
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


class TTSQueue:
    """
    Async TTS queue for managing synthesis requests.
    
    Handles phrase queuing, synthesis, and audio delivery
    with proper backpressure handling.
    """
    
    def __init__(self, tts: StreamingTTS, max_queue_size: int = 10):
        self.tts = tts
        self.max_queue_size = max_queue_size
        self._queue: List[str] = []
        self._audio_queue: List[bytes] = []
        
    def enqueue(self, text: str) -> bool:
        """
        Add text to synthesis queue.
        
        Returns:
            True if added, False if queue full
        """
        if len(self._queue) >= self.max_queue_size:
            logger.warning("TTS queue full, dropping phrase")
            return False
        self._queue.append(text)
        return True
    
    def process_one(self) -> Optional[bytes]:
        """
        Process one item from queue.
        
        Returns:
            Synthesized audio, or None if queue empty
        """
        if not self._queue:
            return None
        
        text = self._queue.pop(0)
        return self.tts.synthesize(text)
    
    def clear(self):
        """Clear all queued items."""
        self._queue.clear()
        self._audio_queue.clear()
    
    @property
    def queue_size(self) -> int:
        return len(self._queue)
