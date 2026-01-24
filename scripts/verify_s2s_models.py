import asyncio
import websockets
import json
import time

async def verify_s2s():
    uri = "ws://localhost:8765/ws/s2s"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # 1. Start Session
            print("\n[1] Starting session...")
            await websocket.send(json.dumps({
                "type": "session_start",
                "lang": "zh"
            }))
            
            # Wait for ready
            while True:
                resp = await websocket.recv()
                print(f"< {resp}")
                data = json.loads(resp)
                if data.get("type") == "session_ready":
                    print("Session ready!")
                    break
            
            # 2. Send Text Input (Simulating ASR)
            test_text = "Hello, what time is it?"
            print(f"\n[2] Sending text input: '{test_text}'")
            start_time = time.time()
            
            await websocket.send(json.dumps({
                "type": "text_input",
                "text": test_text
            }))
            
            # 3. Measure First Token and First Audio Latency
            first_token_time = None
            first_audio_time = None
            audio_chunks = 0
            tokens = []
            
            print("\n[3] Waiting for response...")
            while True:
                msg = await websocket.recv()
                
                # Check for binary (audio)
                if isinstance(msg, bytes):
                    audio_chunks += 1
                    if first_audio_time is None:
                        first_audio_time = time.time()
                        latency = (first_audio_time - start_time) * 1000
                        print(f"🔊 First AUDIO received after {latency:.1f}ms ({len(msg)} bytes)")
                    else:
                        # Print dot for subsequent chunks to reduce noise
                        print(".", end="", flush=True)
                else:
                    # JSON control message
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    
                    if msg_type == "llm_token":
                        token = data.get("token")
                        tokens.append(token)
                        if first_token_time is None:
                            first_token_time = time.time()
                            latency = (first_token_time - start_time) * 1000
                            print(f"📝 First TOKEN received after {latency:.1f}ms: '{token}'")
                        else:
                            print(token, end="", flush=True)
                            
                    elif msg_type == "response_end":
                        print("\n\n✅ Response complete!")
                        break
                    
                    elif msg_type == "error":
                        print(f"\n❌ Error: {data.get('message')}")
                        break
            
            print("\n" + "="*40)
            print("Summary:")
            print(f"Total Tokens: {len(tokens)}")
            print(f"Total Audio Chunks: {audio_chunks}")
            print(f"Full Response: {''.join(tokens)}")
            
            if audio_chunks > 0:
                print("✅ Audio synthesis working")
            else:
                print("❌ No audio received")
                
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_s2s())
