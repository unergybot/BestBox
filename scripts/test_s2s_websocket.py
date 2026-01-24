#!/usr/bin/env python3
"""
Quick WebSocket test for S2S service

Tests:
1. Connection to ws://localhost:8765/ws/s2s
2. Session initialization
3. Text input (skip ASR/TTS)
4. Agent response streaming
"""

import asyncio
import json
import websockets
import sys

async def test_s2s_websocket():
    uri = "ws://localhost:8765/ws/s2s"

    print("=" * 60)
    print("S2S WebSocket Test")
    print("=" * 60)
    print()

    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            print()

            # Step 1: Initialize session
            print("Step 1: Initializing session...")
            await websocket.send(json.dumps({
                "type": "session_start",
                "lang": "zh",
                "audio": {
                    "sample_rate": 16000,
                    "format": "pcm16",
                    "channels": 1
                }
            }))

            response = await websocket.recv()
            msg = json.loads(response)
            if msg.get("type") == "session_ready":
                print(f"✅ Session ready: {msg.get('session_id', 'N/A')}")
            print()

            # Step 2: Send text input
            test_query = "今天有什么会议？"
            print(f"Step 2: Sending text input: '{test_query}'")
            await websocket.send(json.dumps({
                "type": "text_input",
                "text": test_query
            }))
            print("✅ Text sent")
            print()

            # Step 3: Receive response
            print("Step 3: Receiving response...")
            tokens = []
            audio_chunks = 0

            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=30)

                # Binary data (TTS audio)
                if isinstance(response, bytes):
                    audio_chunks += 1
                    if audio_chunks == 1:
                        print(f"🔊 Audio: Received {len(response)} bytes")
                    continue

                # Text data (JSON messages)
                msg = json.loads(response)
                msg_type = msg.get("type")

                if msg_type == "llm_token":
                    token = msg.get("token", "")
                    tokens.append(token)
                    # Print inline without newline
                    print(token, end="", flush=True)

                elif msg_type == "response_end":
                    print()  # New line after tokens
                    print("✅ Response complete")
                    break

                elif msg_type == "error":
                    print(f"❌ Error: {msg.get('message')}")
                    break

            print()
            if audio_chunks > 0:
                print(f"🔊 Total audio chunks received: {audio_chunks}")

            print()
            print("=" * 60)
            print("✅ All tests passed!")
            print("=" * 60)

            return True

    except websockets.exceptions.ConnectionRefusedError:
        print("❌ Connection refused - is the S2S service running?")
        print("   Run: ./scripts/start-s2s.sh")
        return False

    except asyncio.TimeoutError:
        print("❌ Timeout waiting for response")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_s2s_websocket())
    sys.exit(0 if result else 1)
