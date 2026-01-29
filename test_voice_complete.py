#!/usr/bin/env python3
"""
Complete voice test to debug the LiveKit integration issue.
This script will:
1. Check all service statuses
2. Test the LiveKit agent connection
3. Monitor logs during a voice test
4. Identify where the speech-to-response pipeline is breaking
"""

import asyncio
import logging
import subprocess
import time
import requests
import json
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VoiceTestSuite:
    def __init__(self):
        self.base_url = "http://localhost"
        self.services = {
            "agent_api": 8000,
            "llm_server": 8080,
            "livekit_server": 7880,
            "frontend": 3000,
            "qdrant": 6333,
            "postgres": 5432
        }
        
    def check_service_health(self, service_name: str, port: int) -> bool:
        """Check if a service is responding."""
        try:
            if service_name == "livekit_server":
                # LiveKit uses WebSocket, just check if port is open
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                return result == 0
            elif service_name in ["postgres", "qdrant"]:
                # Database services, check port
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                return result == 0
            else:
                # HTTP services
                response = requests.get(f"{self.base_url}:{port}/health", timeout=5)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {service_name}: {e}")
            return False
    
    def check_all_services(self):
        """Check health of all required services."""
        logger.info("🔍 Checking service health...")
        results = {}
        
        for service, port in self.services.items():
            is_healthy = self.check_service_health(service, port)
            results[service] = is_healthy
            status = "✅" if is_healthy else "❌"
            logger.info(f"{status} {service} (port {port}): {'Healthy' if is_healthy else 'Unhealthy'}")
        
        return results
    
    def test_agent_api_direct(self):
        """Test the agent API directly with a text message."""
        logger.info("🧪 Testing Agent API directly...")
        
        try:
            payload = {
                "messages": [{"role": "user", "content": "Hello, this is a test message"}],
                "stream": False
            }
            
            response = requests.post(
                f"{self.base_url}:8000/v1/chat/completions",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info(f"✅ Agent API working: {content[:100]}...")
                return True
            else:
                logger.error(f"❌ Agent API failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Agent API test failed: {e}")
            return False
    
    def check_livekit_processes(self):
        """Check LiveKit related processes."""
        logger.info("🔍 Checking LiveKit processes...")
        
        try:
            # Check for LiveKit server
            result = subprocess.run(["pgrep", "-f", "livekit-server"], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"✅ LiveKit server running (PID: {result.stdout.strip()})")
            else:
                logger.error("❌ LiveKit server not running")
            
            # Check for LiveKit agent
            result = subprocess.run(["pgrep", "-f", "livekit_agent.py"], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"✅ LiveKit agent running (PID: {result.stdout.strip()})")
            else:
                logger.error("❌ LiveKit agent not running")
                
            # Check for agent processes (multiprocessing workers)
            result = subprocess.run(["pgrep", "-f", "multiprocessing.forkserver"], capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                logger.info(f"✅ Found {len(pids)} LiveKit worker processes")
            else:
                logger.warning("⚠️  No LiveKit worker processes found")
                
        except Exception as e:
            logger.error(f"Error checking processes: {e}")
    
    def test_livekit_token_generation(self):
        """Test LiveKit token generation endpoint."""
        logger.info("🧪 Testing LiveKit token generation...")
        
        try:
            response = requests.post(
                f"{self.base_url}:3000/api/livekit/token",
                json={"room": "test-room", "participant": "test-user"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "token" in data:
                    logger.info("✅ LiveKit token generation working")
                    return True
                else:
                    logger.error(f"❌ Token generation failed: {data}")
                    return False
            else:
                logger.error(f"❌ Token endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Token generation test failed: {e}")
            return False
    
    def test_livekit_dispatch(self):
        """Test LiveKit agent dispatch endpoint."""
        logger.info("🧪 Testing LiveKit agent dispatch...")
        
        try:
            response = requests.post(
                f"{self.base_url}:3000/api/livekit/dispatch",
                json={"room": "test-room"},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ LiveKit agent dispatch working")
                return True
            else:
                logger.error(f"❌ Agent dispatch failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Agent dispatch test failed: {e}")
            return False
    
    def monitor_logs_for_speech(self, duration: int = 30):
        """Monitor logs for speech processing activity."""
        logger.info(f"👂 Monitoring logs for {duration} seconds...")
        logger.info("🎤 Please speak 'hello, are you there' now...")
        
        # Start monitoring agent API logs
        try:
            process = subprocess.Popen(
                ["tail", "-f", "agent_api.log"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            start_time = time.time()
            speech_detected = False
            agent_processing = False
            
            while time.time() - start_time < duration:
                line = process.stdout.readline()
                if line:
                    line = line.strip()
                    
                    # Look for speech-related activity
                    if "LocalSTT" in line or "speech" in line.lower() or "audio" in line.lower():
                        if not speech_detected:
                            logger.info(f"🎤 Speech activity detected: {line}")
                            speech_detected = True
                        
                    # Look for agent processing
                    if "Incoming Request" in line or "Processing request" in line:
                        if not agent_processing:
                            logger.info(f"🤖 Agent processing detected: {line}")
                            agent_processing = True
                
                time.sleep(0.1)
            
            process.terminate()
            
            if speech_detected and agent_processing:
                logger.info("✅ Speech-to-agent pipeline working")
                return True
            elif speech_detected:
                logger.warning("⚠️  Speech detected but no agent processing")
                return False
            else:
                logger.error("❌ No speech activity detected")
                return False
                
        except Exception as e:
            logger.error(f"Error monitoring logs: {e}")
            return False
    
    def run_complete_test(self):
        """Run the complete voice test suite."""
        logger.info("🚀 Starting BestBox Voice Test Suite")
        logger.info("=" * 60)
        
        # 1. Check service health
        service_results = self.check_all_services()
        unhealthy_services = [name for name, healthy in service_results.items() if not healthy]
        
        if unhealthy_services:
            logger.error(f"❌ Unhealthy services: {unhealthy_services}")
            logger.error("Please start missing services before continuing")
            return False
        
        logger.info("✅ All services are healthy")
        
        # 2. Test agent API directly
        if not self.test_agent_api_direct():
            logger.error("❌ Agent API not working - voice will not work")
            return False
        
        # 3. Check LiveKit processes
        self.check_livekit_processes()
        
        # 4. Test LiveKit endpoints
        if not self.test_livekit_token_generation():
            logger.error("❌ LiveKit token generation failed")
            return False
            
        if not self.test_livekit_dispatch():
            logger.error("❌ LiveKit agent dispatch failed")
            return False
        
        logger.info("✅ All preliminary tests passed")
        logger.info("=" * 60)
        
        # 5. Monitor for speech activity
        logger.info("🎤 VOICE TEST: Please open http://localhost:3000/voice in your browser")
        logger.info("🎤 Then speak 'hello, are you there' clearly into your microphone")
        logger.info("🎤 Monitoring will start in 5 seconds...")
        
        time.sleep(5)
        
        speech_working = self.monitor_logs_for_speech(30)
        
        logger.info("=" * 60)
        if speech_working:
            logger.info("🎉 VOICE TEST PASSED: Speech-to-response pipeline is working!")
        else:
            logger.error("💥 VOICE TEST FAILED: Speech is not triggering agent responses")
            logger.info("🔧 Debugging suggestions:")
            logger.info("   1. Check browser console for WebRTC errors")
            logger.info("   2. Verify microphone permissions in browser")
            logger.info("   3. Check LiveKit agent logs for STT activity")
            logger.info("   4. Ensure speech is loud and clear")
        
        return speech_working

if __name__ == "__main__":
    test_suite = VoiceTestSuite()
    success = test_suite.run_complete_test()
    exit(0 if success else 1)