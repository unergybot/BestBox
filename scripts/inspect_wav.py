import wave
import sys

try:
    with wave.open("data/audio/ground_truth.wav", "rb") as wf:
        print(f"Channels: {wf.getnchannels()}")
        print(f"Sample Width: {wf.getsampwidth()} bytes")
        print(f"Sample Rate: {wf.getframerate()} Hz")
        print(f"Frames: {wf.getnframes()}")
        print(f"Duration: {wf.getnframes() / wf.getframerate():.2f} seconds")
except Exception as e:
    print(f"Error: {e}")
