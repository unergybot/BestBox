#!/usr/bin/env python3
"""
Debug script to monitor LiveKit agent logs in real-time.
Run this while testing voice functionality to see exactly what's happening.
"""

import subprocess
import threading
import time
import sys
from datetime import datetime

def monitor_livekit_process():
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
        print(f"📡 Found LiveKit agent process (PID: {pid})")
        
        # The LiveKit agent logs to stdout/stderr, but since it's running in background,
        # we need to check if there are any log files or use journalctl
        
        print("🔍 Monitoring LiveKit agent activity...")
        print("   Looking for voice pipeline logs with 🎯 VOICE_PIPELINE prefix")
        
    except Exception as e:
        print(f"Error monitoring LiveKit process: {e}")

def tail_log_file(filename):
    """Tail a log file and filter for voice pipeline messages."""
    try:
        process = subprocess.Popen(
            ["tail", "-f", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"📡 Monitoring {filename}...")
        
        for line in iter(process.stdout.readline, ''):
            if line.strip():
                # Filter for our voice pipeline logs
                if "🎯 VOICE_PIPELINE" in line or "LocalSTT" in line or "bestbox-voice" in line:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[{timestamp}] {line.strip()}")
                    
    except FileNotFoundError:
        print(f"⚠️  Log file {filename} not found")
    except Exception as e:
        print(f"Error monitoring {filename}: {e}")

def main():
    print("=" * 80)
    print("🎤 BestBox Voice Debug Monitor")
    print("=" * 80)
    print("This script monitors LiveKit agent logs for voice processing activity.")
    print("Look for logs with 🎯 VOICE_PIPELINE prefix to track the speech flow.")
    print("=" * 80)
    
    # Check if LiveKit agent is running
    result = subprocess.run(
        ["pgrep", "-f", "livekit_agent.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("❌ LiveKit agent is not running!")
        print("Please start it with: ./scripts/start-livekit-agent.sh dev")
        return
    
    pid = result.stdout.strip().split('\n')[0]
    print(f"✅ LiveKit agent is running (PID: {pid})")
    
    # Start monitoring threads for different log sources
    threads = []
    
    # Monitor agent_api.log for any requests that make it through
    api_thread = threading.Thread(target=tail_log_file, args=("agent_api.log",), daemon=True)
    api_thread.start()
    threads.append(api_thread)
    
    print("\n🎤 INSTRUCTIONS:")
    print("1. Open http://localhost:3000/voice in your browser")
    print("2. Grant microphone permissions")
    print("3. Speak clearly: 'hello, are you there'")
    print("4. Watch for voice pipeline logs below")
    print("5. Press Ctrl+C to stop monitoring")
    print("\n" + "=" * 80)
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped")
        sys.exit(0)

if __name__ == "__main__":
    main()