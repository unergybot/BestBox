"""
S2S Gateway - WebSocket service for Speech-to-Speech
Bridges ASR (Qwen3-ASR) and TTS (Qwen3-TTS) services via WebSocket
"""

import os
import asyncio
import logging
import time
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
S2S_PORT = int(os.environ.get("S2S_PORT", "8765"))
ASR_URL = os.environ.get("ASR_URL", "http://localhost:8003")
TTS_URL = os.environ.get("TTS_URL", "http://localhost:8004")
AGENT_API_URL = os.environ.get("AGENT_API_URL", "http://localhost:8000")

app = FastAPI(title="S2S Gateway")

# CORS for WebSocket
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""

    # Check if ASR and TTS services are reachable
    asr_healthy = False
    tts_healthy = False

    try:
        async with httpx.AsyncClient() as client:
            asr_resp = await client.get(f"{ASR_URL}/health", timeout=2.0)
            asr_healthy = asr_resp.status_code == 200
    except:
        pass

    try:
        async with httpx.AsyncClient() as client:
            tts_resp = await client.get(f"{TTS_URL}/health", timeout=2.0)
            tts_healthy = tts_resp.status_code == 200
    except:
        pass

    return {
        "status": "ok" if (asr_healthy and tts_healthy) else "degraded",
        "service": "s2s-gateway",
        "asr_service": ASR_URL,
        "tts_service": TTS_URL,
        "asr_healthy": asr_healthy,
        "tts_healthy": tts_healthy,
    }


async def process_audio_buffer(websocket: WebSocket, audio_buffer: bytearray, asr_url: str):
    """Process accumulated audio buffer and send transcription"""
    if len(audio_buffer) == 0:
        return

    logger.info(f"Processing complete audio: {len(audio_buffer)} bytes")
    try:
        # Send complete audio to ASR service
        async with httpx.AsyncClient() as client:
            files = {"file": ("audio.wav", bytes(audio_buffer), "audio/wav")}
            response = await client.post(
                f"{asr_url}/v1/audio/transcriptions",
                files=files,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            transcript = result.get("text", "")
            logger.info(f"Transcription: {transcript}")

            # Send transcript back to client
            if transcript.strip():
                await websocket.send_json({
                    "type": "asr_final",
                    "text": transcript
                })

                # TODO: Send to agent API for response
                # For now, just echo back
                await websocket.send_json({
                    "type": "response",
                    "text": f"Received: {transcript}"
                })

    except Exception as e:
        logger.error(f"ASR processing failed: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


@app.websocket("/ws/s2s")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Speech-to-Speech interaction

    Protocol:
    - Client sends: Binary audio data (PCM16) or JSON control messages
    - Server sends: JSON transcripts and responses, or Binary audio data
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    # Audio buffer for accumulating chunks
    audio_buffer = bytearray()
    silent_chunks = 0
    last_audio_time = time.time()

    # VAD parameters
    SILENCE_THRESHOLD = 500  # RMS threshold for silence
    SILENCE_DURATION = 1.5   # Seconds of silence before processing
    MIN_AUDIO_LENGTH = 16000 # Minimum 0.5 seconds of audio (16kHz * 2 bytes * 0.5s)

    try:
        while True:
            # Receive message from client
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("Client disconnected")
                break

            # Handle binary audio data
            if "bytes" in message:
                audio_data = message["bytes"]

                # Calculate RMS energy for VAD
                import struct
                samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
                rms = sum(abs(s) for s in samples) / len(samples) if samples else 0

                is_silent = rms < SILENCE_THRESHOLD

                if is_silent:
                    silent_chunks += 1
                    # Check if we've had enough silence and have accumulated audio
                    silence_duration = silent_chunks * (len(audio_data) / 2 / 16000)  # seconds

                    if silence_duration >= SILENCE_DURATION and len(audio_buffer) >= MIN_AUDIO_LENGTH:
                        logger.info(f"Silence detected ({silence_duration:.1f}s), processing audio")
                        await process_audio_buffer(websocket, audio_buffer, ASR_URL)
                        audio_buffer.clear()
                        silent_chunks = 0
                else:
                    # Speech detected, reset silence counter and accumulate
                    silent_chunks = 0
                    audio_buffer.extend(audio_data)
                    last_audio_time = time.time()

            # Handle JSON control messages
            elif "text" in message:
                try:
                    import json
                    data = json.loads(message["text"])
                    logger.info(f"Received control message: {data}")

                    # Handle different message types
                    msg_type = data.get("type")

                    if msg_type == "session_start":
                        # Session initialization
                        session_id = f"session_{int(time.time() * 1000)}"
                        logger.info(f"Session started: {session_id}")
                        await websocket.send_json({
                            "type": "session_ready",
                            "session_id": session_id
                        })

                    elif msg_type == "audio_end":
                        # Process any remaining audio in buffer (manual stop)
                        logger.info("Received audio_end signal (manual stop)")
                        await process_audio_buffer(websocket, audio_buffer, ASR_URL)
                        audio_buffer.clear()
                        silent_chunks = 0

                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

                    elif msg_type == "text_input":
                        # Direct text input (no ASR needed)
                        text = data.get("text", "")
                        await websocket.send_json({
                            "type": "response",
                            "text": f"Text received: {text}"
                        })

                    else:
                        logger.warning(f"Unknown message type: {msg_type}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown message type: {msg_type}"
                        })

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        logger.info("WebSocket connection closed")


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting S2S Gateway on port {S2S_PORT}")
    logger.info(f"ASR Service: {ASR_URL}")
    logger.info(f"TTS Service: {TTS_URL}")
    logger.info(f"Agent API: {AGENT_API_URL}")

    uvicorn.run(app, host="0.0.0.0", port=S2S_PORT)
