#!/usr/bin/env python3
"""
Automated voice test using audio file - no speaking required!
This test will simulate speech input using the existing audio file.
"""

import asyncio
import logging
import time
import requests
import subprocess
import sys
import os
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutomatedVoiceTest:
    def __init__(self):
        self.audio_file = "data/audio/ground_truth.wav"
        
    def check_services(self):
        """Quick service health check."""
        services = {
            "Agent API": "http://localhost:8000/health",
            "LLM Server": "http://localhost:8080/health"
        }
        
        logger.info("🔍 Checking services...")
        all_healthy = True
        
        for name, url in services.items():
            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    logger.info(f"✅ {name}")
                else:
                    logger.error(f"❌ {name} (status: {response.status_code})")
                    all_healthy = False
            except Exception as e:
                logger.error(f"❌ {name} (error: {e})")
                all_healthy = False
        
        return all_healthy
    
    def test_direct_agent_api(self):
        """Test the agent API directly with text."""
        logger.info("🧪 Testing Agent API with text...")
        
        try:
            payload = {
                "messages": [{"role": "user", "content": "Hello, this is an automated test. Please respond."}],
                "stream": False
            }
            
            start_time = time.time()
            response = requests.post(
                "http://localhost:8000/v1/chat/completions",
                json=payload,
                timeout=30
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info(f"✅ Agent API working ({duration:.2f}s): {content[:100]}...")
                return True
            else:
                logger.error(f"❌ Agent API failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Agent API test failed: {e}")
            return False
    
    def test_speech_recognition(self):
        """Test speech recognition directly using the audio file."""
        logger.info("🎤 Testing speech recognition with audio file...")
        
        if not os.path.exists(self.audio_file):
            logger.error(f"❌ Audio file not found: {self.audio_file}")
            return False
        
        try:
            # Import and test the ASR directly
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from services.speech.asr import StreamingASR, ASRConfig
            
            # Initialize ASR
            config = ASRConfig(
                model_size="Systran/faster-distil-whisper-large-v3",
                device="cpu",
                compute_type="int8"
            )
            asr = StreamingASR(config)
            
            # Load and process audio file
            import numpy as np
            import wave
            
            logger.info(f"📁 Loading audio file: {self.audio_file}")
            
            with wave.open(self.audio_file, 'rb') as wav_file:
                frames = wav_file.readframes(-1)
                sample_rate = wav_file.getframerate()
                audio_data = np.frombuffer(frames, dtype=np.int16)
            
            logger.info(f"🎵 Audio loaded: {len(audio_data)} samples at {sample_rate}Hz")
            
            # Process audio in chunks
            chunk_size = int(sample_rate * 0.1)  # 100ms chunks
            
            start_time = time.time()
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                if len(chunk) > 0:
                    result = asr.feed_audio(chunk)
                    if result and result.get("text"):
                        logger.info(f"🎯 STT Result: {result}")
            
            # Finalize
            final_result = asr.finalize()
            duration = time.time() - start_time
            
            if final_result and final_result.get("text"):
                logger.info(f"✅ Speech recognition working ({duration:.2f}s): '{final_result['text']}'")
                return True, final_result["text"]
            else:
                logger.error("❌ No transcription result")
                return False, ""
                
        except Exception as e:
            logger.error(f"❌ Speech recognition test failed: {e}")
            return False, ""
    
    def test_end_to_end_with_transcription(self, transcription_text):
        """Test end-to-end by sending transcription to agent API."""
        logger.info("🔄 Testing end-to-end with transcription...")
        
        try:
            payload = {
                "messages": [{"role": "user", "content": transcription_text}],
                "stream": False
            }
            
            start_time = time.time()
            response = requests.post(
                "http://localhost:8000/v1/chat/completions",
                json=payload,
                timeout=30
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info(f"✅ End-to-end working ({duration:.2f}s): {content[:100]}...")
                return True
            else:
                logger.error(f"❌ End-to-end failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ End-to-end test failed: {e}")
            return False
    
    def monitor_livekit_logs(self, duration=10):
        """Monitor LiveKit logs for activity."""
        logger.info(f"👀 Monitoring LiveKit logs for {duration} seconds...")
        
        try:
            # Check if there are recent LiveKit session logs
            result = subprocess.run(
                ["tail", "-50", "agent_new.log"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                recent_logs = result.stdout
                
                # Look for session activity
                if "NEW SESSION REQUESTED" in recent_logs:
                    logger.info("✅ LiveKit sessions are being created")
                    
                if "LocalSTT" in recent_logs:
                    logger.info("✅ Speech recognition is being initialized")
                    
                if "TypeError" in recent_logs:
                    logger.warning("⚠️  Found errors in logs - check for issues")
                    
                # Show recent voice pipeline activity
                lines = recent_logs.split('\n')
                voice_lines = [line for line in lines if any(marker in line for marker in ["🎯", "VOICE_PIPELINE", "LocalSTT", "Graph wrapper"])]
                
                if voice_lines:
                    logger.info("📋 Recent voice pipeline activity:")
                    for line in voice_lines[-5:]:  # Show last 5 voice-related lines
                        logger.info(f"   {line}")
                else:
                    logger.warning("⚠️  No recent voice pipeline activity found")
                    
            return True
            
        except Exception as e:
            logger.error(f"Error monitoring logs: {e}")
            return False
    
    def run_complete_test(self):
        """Run the complete automated test suite."""
        logger.info("🚀 Starting Automated Voice Test Suite")
        logger.info("=" * 60)
        logger.info("This test uses an audio file - no speaking required!")
        logger.info("=" * 60)
        
        # 1. Check services
        if not self.check_services():
            logger.error("❌ Some services are not healthy")
            return False
        
        # 2. Test agent API directly
        if not self.test_direct_agent_api():
            logger.error("❌ Agent API not working")
            return False
        
        # 3. Test speech recognition
        stt_working, transcription = self.test_speech_recognition()
        if not stt_working:
            logger.error("❌ Speech recognition not working")
            return False
        
        # 4. Test end-to-end with transcription
        if not self.test_end_to_end_with_transcription(transcription):
            logger.error("❌ End-to-end processing not working")
            return False
        
        # 5. Monitor LiveKit logs
        self.monitor_livekit_logs()
        
        logger.info("=" * 60)
        logger.info("🎉 AUTOMATED TEST COMPLETE!")
        logger.info("✅ Speech recognition: Working")
        logger.info("✅ Agent processing: Working") 
        logger.info("✅ End-to-end flow: Working")
        logger.info("")
        logger.info("💡 The voice pipeline components are working individually.")
        logger.info("💡 If LiveKit voice still doesn't work, the issue is likely in:")
        logger.info("   - Browser microphone permissions")
        logger.info("   - LiveKit WebRTC connection")
        logger.info("   - Frontend voice page integration")
        logger.info("=" * 60)
        
        return True

if __name__ == "__main__":
    test_suite = AutomatedVoiceTest()
    success = test_suite.run_complete_test()
    exit(0 if success else 1)