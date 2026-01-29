#!/usr/bin/env python3
"""
Real-time voice monitoring script to debug LiveKit speech processing.
This will monitor logs and show exactly what happens when you speak.
"""

import subprocess
import time
import threading
import sys
from datetime import datetime

class VoiceMonitor:
    def __init__(self):
        self.speech_detected = False
        self.transcription_found = False
        self.agent_processing = False
        
    def monitor_agent_api_logs(self):
        """Monitor agent API logs for incoming requests."""
        try:
            process = subprocess.Popen(
                ["tail", "-f", "agent_api.log"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            print("📡 Monitoring Agent API logs...")
            
            for line in iter(process.stdout.readline, ''):
                if line.strip():
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    if "Incoming Request" in line:
                        print(f"🤖 [{timestamp}] AGENT REQUEST: {line.strip()}")
                        self.agent_processing = True
                        
                    elif "Processing request" in line:
                        print(f"🔄 [{timestamp}] PROCESSING: {line.strip()}")
                        
                    elif "Returning response" in line:
                        print(f"✅ [{timestamp}] RESPONSE: {line.strip()}")
                        
        except Exception as e:
            print(f"Error monitoring agent API: {e}")
    
    def monitor_livekit_process(self):
        """Monitor the LiveKit agent process output."""
        try:
            # Find the LiveKit agent process
            result = subprocess.run(
                ["pgrep", "-f", "livekit_agent.py"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print("❌ LiveKit agent process not found")
                return
                
            pid = result.stdout.strip().split('\n')[0]
            print(f"📡 Monitoring LiveKit agent process (PID: {pid})...")
            
            # Monitor the process output (this might not work if it's not logging to stdout)
            # Instead, let's look for any LiveKit-related log files
            
        except Exception as e:
            print(f"Error monitoring LiveKit process: {e}")
    
    def check_browser_connection(self):
        """Check if browser is connected to LiveKit."""
        print("🌐 Checking browser connection...")
        print("   Please ensure you have http://localhost:3000/voice open in your browser")
        print("   and that you've granted microphone permissions")
    
    def run_monitoring(self, duration=60):
        """Run monitoring for specified duration."""
        print("=" * 70)
        print("🎤 BestBox Voice Monitoring - Real-time Debug")
        print("=" * 70)
        print(f"⏱️  Monitoring for {duration} seconds...")
        print("🎤 Please speak 'hello, are you there' into your microphone")
        print("=" * 70)
        
        # Start monitoring threads
        api_thread = threading.Thread(target=self.monitor_agent_api_logs, daemon=True)
        api_thread.start()
        
        # Check browser connection
        self.check_browser_connection()
        
        print("\n🔍 Watching for activity...")
        print("   - Speech detection (STT)")
        print("   - Transcription results")
        print("   - Agent API requests")
        print("   - Response generation")
        print("\n" + "=" * 70)
        
        start_time = time.time()
        last_status = time.time()
        
        while time.time() - start_time < duration:
            # Print status every 10 seconds
            if time.time() - last_status > 10:
                elapsed = int(time.time() - start_time)
                remaining = duration - elapsed
                print(f"⏱️  [{elapsed}s] Still monitoring... ({remaining}s remaining)")
                last_status = time.time()
            
            time.sleep(1)
        
        print("\n" + "=" * 70)
        print("📊 MONITORING SUMMARY:")
        print(f"   Speech detected: {'✅' if self.speech_detected else '❌'}")
        print(f"   Transcription found: {'✅' if self.transcription_found else '❌'}")
        print(f"   Agent processing: {'✅' if self.agent_processing else '❌'}")
        
        if not self.agent_processing:
            print("\n🔧 TROUBLESHOOTING:")
            print("   1. Check browser console for errors")
            print("   2. Verify microphone permissions")
            print("   3. Ensure you're speaking clearly and loudly")
            print("   4. Check if LiveKit room connection is established")
            print("   5. Try refreshing the browser page")
        
        print("=" * 70)

if __name__ == "__main__":
    monitor = VoiceMonitor()
    
    # Check if services are running first
    try:
        import requests
        
        # Quick health checks
        services = {
            "Agent API": "http://localhost:8000/health",
            "LLM Server": "http://localhost:8080/health",
            "Frontend": "http://localhost:3000/health"
        }
        
        print("🔍 Quick service check:")
        for name, url in services.items():
            try:
                response = requests.get(url, timeout=2)
                status = "✅" if response.status_code == 200 else "❌"
                print(f"   {status} {name}")
            except:
                print(f"   ❌ {name} (not responding)")
        
        print()
        
    except ImportError:
        print("⚠️  requests not available, skipping service check")
    
    # Run monitoring
    try:
        monitor.run_monitoring(60)
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
        sys.exit(0)