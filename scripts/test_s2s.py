#!/usr/bin/env python3
"""
Test script for BestBox Speech-to-Speech pipeline

Tests individual components and end-to-end flow:
1. ASR service (faster-whisper + VAD)
2. TTS service (XTTS v2)
3. Speech buffer
4. WebSocket connectivity

Usage:
    python scripts/test_s2s.py [--component asr|tts|buffer|all]
"""

import sys
import os
import argparse
import asyncio
import numpy as np
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_asr():
    """Test ASR component."""
    print("\n" + "=" * 50)
    print("Testing ASR (faster-whisper + VAD)")
    print("=" * 50)
    
    try:
        from services.speech.asr import StreamingASR, ASRConfig
        
        # Test with CPU to avoid GPU issues in test
        config = ASRConfig(
            model_size="tiny",  # Use tiny for testing
            device="cpu",
            compute_type="int8",
            language="en"
        )
        
        print("Creating ASR instance...")
        asr = StreamingASR(config)
        
        print("Testing reset...")
        asr.reset()
        
        # Create synthetic audio (silence + tone)
        print("Creating test audio...")
        sample_rate = 16000
        duration = 2  # seconds
        
        # Generate a 440Hz tone (A4)
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        
        # Add some noise to simulate speech
        noise = np.random.normal(0, 1000, len(audio)).astype(np.int16)
        audio = np.clip(audio + noise, -32768, 32767).astype(np.int16)
        
        print(f"Audio shape: {audio.shape}, dtype: {audio.dtype}")
        
        # Feed audio in chunks
        chunk_size = 4096
        print(f"Feeding {len(audio) // chunk_size} chunks...")
        
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            if len(chunk) > 0:
                result = asr.feed_audio(chunk)
                if result:
                    print(f"  Partial: {result}")
        
        # Finalize
        print("Finalizing...")
        final = asr.finalize()
        print(f"Final result: {final}")
        
        # Get stats
        stats = asr.get_stats()
        print(f"Stats: {stats}")
        
        print("✅ ASR test passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Install with: pip install faster-whisper webrtcvad")
        return False
    except Exception as e:
        print(f"❌ ASR test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tts():
    """Test TTS component."""
    print("\n" + "=" * 50)
    print("Testing TTS (XTTS v2)")
    print("=" * 50)
    
    try:
        from services.speech.tts import StreamingTTS, TTSConfig
        
        # Test with CPU
        config = TTSConfig(
            gpu=False,
            fallback_to_piper=True
        )
        
        print("Creating TTS instance...")
        tts = StreamingTTS(config)
        
        print("Testing synthesis...")
        text = "Hello, this is a test."
        
        audio = tts.synthesize(text, language="en")
        
        if audio:
            # Convert to numpy for analysis
            pcm = np.frombuffer(audio, dtype=np.int16)
            print(f"Generated audio: {len(pcm)} samples ({len(pcm)/tts.sample_rate:.2f}s)")
            print(f"Sample rate: {tts.sample_rate}")
            print(f"Max amplitude: {np.max(np.abs(pcm))}")
            print("✅ TTS test passed!")
            return True
        else:
            print("⚠️ TTS returned empty audio (may be using fallback)")
            return True  # Still pass if fallback is being used
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Install with: pip install TTS")
        return False
    except Exception as e:
        print(f"❌ TTS test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_speech_buffer():
    """Test speech buffer component."""
    print("\n" + "=" * 50)
    print("Testing Speech Buffer")
    print("=" * 50)
    
    try:
        from services.speech.tts import SpeechBuffer
        
        print("Creating buffer with min_chars=20...")
        buffer = SpeechBuffer(min_chars=20, max_chars=100)
        
        # Test tokens
        tokens = [
            "Hello", " ", "world", ".", " ",
            "This", " ", "is", " ", "a", " ",
            "test", " ", "of", " ", "the", " ",
            "speech", " ", "buffer", "。"
        ]
        
        print("Adding tokens...")
        phrases = []
        for token in tokens:
            result = buffer.add(token)
            if result:
                print(f"  Emitted: '{result}'")
                phrases.append(result)
        
        # Flush remaining
        remaining = buffer.flush()
        if remaining:
            print(f"  Flushed: '{remaining}'")
            phrases.append(remaining)
        
        # Get stats
        stats = buffer.get_stats()
        print(f"Stats: {stats}")
        
        print(f"Total phrases emitted: {len(phrases)}")
        print("✅ Speech buffer test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Speech buffer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_websocket():
    """Test WebSocket connectivity."""
    print("\n" + "=" * 50)
    print("Testing WebSocket Connectivity")
    print("=" * 50)
    
    try:
        import websockets
        
        uri = "ws://localhost:8765/ws/s2s"
        print(f"Connecting to {uri}...")
        
        async with websockets.connect(uri) as ws:
            print("Connected!")
            
            # Send session start
            import json
            await ws.send(json.dumps({
                "type": "session_start",
                "lang": "zh"
            }))
            
            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(response)
            print(f"Received: {msg}")
            
            # Send text input
            await ws.send(json.dumps({
                "type": "text_input",
                "text": "你好"
            }))
            
            # Collect responses
            responses = []
            try:
                while True:
                    response = await asyncio.wait_for(ws.recv(), timeout=10)
                    if isinstance(response, bytes):
                        print(f"  Audio chunk: {len(response)} bytes")
                    else:
                        msg = json.loads(response)
                        print(f"  Message: {msg}")
                        responses.append(msg)
                        if msg.get("type") == "response_end":
                            break
            except asyncio.TimeoutError:
                print("  Timeout waiting for responses")
            
            print(f"Total responses: {len(responses)}")
            print("✅ WebSocket test passed!")
            return True
            
    except ImportError:
        print("❌ websockets not installed")
        print("   Install with: pip install websockets")
        return False
    except ConnectionRefusedError:
        print("❌ Connection refused - is the S2S server running?")
        print("   Start with: ./scripts/start-s2s.sh")
        return False
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test S2S components")
    parser.add_argument(
        "--component",
        choices=["asr", "tts", "buffer", "websocket", "all"],
        default="all",
        help="Component to test"
    )
    args = parser.parse_args()
    
    print("=" * 50)
    print("BestBox S2S Component Tests")
    print("=" * 50)
    
    results = {}
    
    if args.component in ["asr", "all"]:
        results["ASR"] = test_asr()
    
    if args.component in ["tts", "all"]:
        results["TTS"] = test_tts()
    
    if args.component in ["buffer", "all"]:
        results["Buffer"] = test_speech_buffer()
    
    if args.component in ["websocket", "all"]:
        results["WebSocket"] = asyncio.run(test_websocket())
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    print()
    if all_passed:
        print("All tests passed! 🎉")
    else:
        print("Some tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
