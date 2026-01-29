
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.speech.tts import StreamingTTS
import time

def test_tts():
    print("Initializing TTS...")
    try:
        tts = StreamingTTS()
        print("TTS initialized.")
        
        text = "Audio check one two three."
        print(f"Synthesizing: '{text}'")
        
        start = time.time()
        audio = tts.synthesize(text)
        duration = time.time() - start
        
        print(f"Synthesis complete in {duration:.2f}s")
        print(f"Audio size: {len(audio)} bytes")
        
        if len(audio) > 0:
            with open("test_tts.wav", "wb") as f:
                # Add simple WAV header for playability (raw PCM16 24kHz mono)
                # ... actually let's just save raw pcm for simplicity or use wave lib
                import wave
                with wave.open("test_tts.wav", "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(audio)
            print("Saved to test_tts.wav")
            return True
        else:
            print("ERROR: Generated empty audio!")
            return False
            
    except Exception as e:
        print(f"ERROR: TTS failed with: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tts()
    sys.exit(0 if success else 1)
