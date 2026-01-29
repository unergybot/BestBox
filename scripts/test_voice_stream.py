#!/usr/bin/env python3
import asyncio
import websockets
import json
import os
import sys
import time

# Configuration
URI = "ws://localhost:8765/ws/s2s"
AUDIO_FILE = "audio_fixed.pcm"
CHUNK_SIZE = 1024  # bytes

async def run_test():
    if not os.path.exists(AUDIO_FILE):
        print(f"Error: Audio file {AUDIO_FILE} not found.")
        return

    print(f"Connecting to {URI}...")
    try:
        async with websockets.connect(URI) as websocket:
            print("Connected.")

            # Wait for session ready
            msg = await websocket.recv()
            data = json.loads(msg)
            if data.get("type") == "session_ready":
                print(f"Session ready: {data.get('session_id')}")
            else:
                print(f"Unexpected initial message: {msg}")
                return

            # Send audio
            print(f"Sending audio from {AUDIO_FILE}...")
            with open(AUDIO_FILE, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    await websocket.send(chunk)
                    await asyncio.sleep(0.01)  # Simulate real-time

            # Send end of audio
            await websocket.send(json.dumps({"type": "audio_end"}))
            print("Sent audio_end. Waiting for response...")

            # Receive loop
            received_audio_bytes = 0
            start_time = time.time()
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=120.0)
                except asyncio.TimeoutError:
                    print("Timeout waiting for response.")
                    break

                if isinstance(message, bytes):
                    received_audio_bytes += len(message)
                else:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "asr_partial":
                        print(f"[ASR Partial]: {data.get('text')}")
                    elif msg_type == "asr_final":
                        print(f"[ASR Final]: {data.get('text')}")
                    elif msg_type == "llm_token":
                        print(f"[LLM Token]: {data.get('token')}", end="", flush=True)
                    elif msg_type == "response_end":
                        print("\n[Response End]")
                        break
                    elif msg_type == "error":
                        print(f"[Error]: {data.get('message')}")
                        break
                    elif msg_type == "pong":
                        pass
                    else:
                        print(f"[Control]: {data}")

            print(f"\nTest Complete.")
            print(f"Received {received_audio_bytes} bytes of audio response.")

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
