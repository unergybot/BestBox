"""
Qwen3-ASR FastAPI Service
Provides automatic speech recognition using Qwen3-ASR-0.6B
"""

import os
import io
import torch
import logging
import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
ASR_MODEL = os.environ.get("ASR_MODEL", "Qwen/Qwen3-ASR-0.6B")
ASR_DEVICE = os.environ.get("ASR_DEVICE", "cuda")
ASR_PORT = int(os.environ.get("ASR_PORT", "8003"))

# Global model instance
asr_model = None

app = FastAPI(title="Qwen3-ASR Service")


class TranscriptionRequest(BaseModel):
    audio_url: Optional[str] = None
    language: Optional[str] = None


@app.on_event("startup")
async def load_model():
    """Load Qwen3-ASR model on startup"""
    global asr_model

    try:
        logger.info(f"Loading Qwen3-ASR model: {ASR_MODEL}")
        logger.info(f"Device: {ASR_DEVICE}")

        from qwen_asr import Qwen3ASRModel

        asr_model = Qwen3ASRModel.from_pretrained(
            ASR_MODEL,
            device_map=ASR_DEVICE,
            dtype=torch.bfloat16,
        )

        logger.info("✅ Qwen3-ASR model loaded successfully")

    except Exception as e:
        logger.error(f"❌ Failed to load ASR model: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok" if asr_model is not None else "loading",
        "model": ASR_MODEL,
        "device": ASR_DEVICE,
        "model_loaded": asr_model is not None,
    }


@app.post("/v1/audio/transcriptions")
async def transcribe_audio(
    file: UploadFile = File(...),
    model: Optional[str] = None,
    language: Optional[str] = None,
):
    """
    OpenAI-compatible audio transcription endpoint

    Args:
        file: Audio file to transcribe
        model: Model name (ignored, uses loaded model)
        language: Language hint (optional)

    Returns:
        JSON response with transcribed text
    """
    if asr_model is None:
        raise HTTPException(status_code=503, detail="ASR model not loaded")

    try:
        # Read audio file
        audio_bytes = await file.read()
        logger.info(f"Transcribing audio file: {file.filename} ({len(audio_bytes)} bytes)")

        # Convert to proper WAV format if needed
        import tempfile
        import wave
        import struct

        # Check if it's already a valid WAV file (starts with RIFF header)
        if audio_bytes[:4] != b'RIFF':
            # Assume raw PCM16, 16kHz, mono - wrap in WAV container
            logger.info("Converting raw PCM to WAV format")
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            with wave.open(temp_file.name, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)   # 16-bit
                wav_file.setframerate(16000)  # 16kHz
                wav_file.writeframes(audio_bytes)
            temp_path = temp_file.name
            temp_file.close()
        else:
            # Already WAV format, save as-is
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

        try:
            # Transcribe - returns List[ASRTranscription]
            results = asr_model.transcribe(
                audio=temp_path,
                language=language,
            )

            # Extract text from first result
            result_text = results[0].text if results else ""
            logger.info(f"✅ Transcription complete: {result_text[:100]}...")

            # OpenAI-compatible response format
            return {
                "text": result_text
            }

        finally:
            # Clean up temp file
            import os
            os.unlink(temp_path)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Transcription failed: {e}\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e) or "Transcription error")


@app.post("/v1/chat/completions")
async def chat_completion(request: dict):
    """
    OpenAI-compatible chat completion endpoint with audio support

    Handles messages with audio_url content type
    """
    if asr_model is None:
        raise HTTPException(status_code=503, detail="ASR model not loaded")

    try:
        messages = request.get("messages", [])

        # Extract audio URL from message
        audio_url = None
        for message in messages:
            if isinstance(message.get("content"), list):
                for content in message["content"]:
                    if content.get("type") == "audio_url":
                        audio_url = content.get("audio_url", {}).get("url")
                        break

        if not audio_url:
            raise HTTPException(status_code=400, detail="No audio_url found in messages")

        logger.info(f"Transcribing from URL: {audio_url}")

        # Download audio
        async with httpx.AsyncClient() as client:
            response = await client.get(audio_url)
            response.raise_for_status()
            audio_bytes = response.content

        # Save to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        try:
            # Transcribe
            results = asr_model.transcribe(audio=temp_path)

            # Extract text from first result
            result_text = results[0].text if results else ""
            logger.info(f"✅ Transcription complete: {result_text[:100]}...")

            # OpenAI-compatible response
            import time
            return {
                "id": "chatcmpl-qwen3asr",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": ASR_MODEL,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": result_text
                        },
                        "finish_reason": "stop"
                    }
                ]
            }

        finally:
            import os
            os.unlink(temp_path)

    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Qwen3-ASR service on port {ASR_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=ASR_PORT)
