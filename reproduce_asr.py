import numpy as np
import time
import logging
from services.speech.asr import StreamingASR, ASRConfig
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)

class MockASR(StreamingASR):
    def _transcribe_buffer(self):
        # Mock transcription
        return "Test Transcription", "en"
    
    @property
    def vad(self):
        if self._vad is None:
             self._vad = MagicMock()
             self._vad.is_speech.return_value = True
        return self._vad

def test_buffer_clear():
    config = ASRConfig()
    config.silence_threshold = 0.5
    asr = MockASR(config)
    
    # 1. Feed "speech" for 1 second
    sample_rate = 16000
    t = np.linspace(0, 1.0, sample_rate)
    audio = (1000 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    
    print("Feeding 1s of speech...")
    asr.vad.is_speech.return_value = True
    chunk_size = int(0.02 * sample_rate) # 20ms
    
    # Feed speech
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i+chunk_size]
        asr.feed_audio(chunk)
    
    print(f"Speech Buffer Duration (Expected ~1.0s): {len(asr.speech_buffer)/sample_rate:.2f}s")
    
    # 2. Feed "silence" for 0.7 seconds
    silence = np.zeros(int(0.7 * sample_rate), dtype=np.int16)
    print("Feeding 0.7s of silence (sleeping to trigger timeout)...")
    asr.vad.is_speech.return_value = False
    
    finalized = False
    for i in range(0, len(silence), chunk_size):
        chunk = silence[i:i+chunk_size]
        res = asr.feed_audio(chunk)
        if res and res.get('type') == 'final':
            print("✅ Finalized Event Received!")
            finalized = True
        time.sleep(0.021) # slightly more than 20ms to ensure time passes
        
    if not finalized:
        print("❌ FAILURE: Did not finalize!")
    
    print(f"Speech Buffer Duration After Finalize (Expected 0.0s): {len(asr.speech_buffer)/sample_rate:.2f}s")
    
    if len(asr.speech_buffer) > 0:
        print("❌ FAILURE: Buffer not cleared!")
    else:
        print("✅ SUCCESS: Buffer cleared.")

    # 3. Feed speech again
    print("Feeding 1s of speech again...")
    asr.vad.is_speech.return_value = True
    # asr.is_speaking should be False if finalize worked
    
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i+chunk_size]
        asr.feed_audio(chunk)
        
    print(f"Speech Buffer Duration 2 (Expected ~1.0s): {len(asr.speech_buffer)/sample_rate:.2f}s")
    
    if len(asr.speech_buffer) > 1.5 * sample_rate:
         print(f"❌ FAILURE: Buffer accumulated! Size: {len(asr.speech_buffer)}")
    else:
         print("✅ SUCCESS: Buffer correct.")

if __name__ == "__main__":
    test_buffer_clear()
