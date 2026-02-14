"""
Qwen3-TTS FastAPI Service
Provides text-to-speech synthesis using Qwen3-TTS-12Hz-0.6B-Base
"""

import os
import io
import torch
import logging
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TTS_MODEL = os.environ.get("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
TTS_DEVICE = os.environ.get("TTS_DEVICE", "cuda")
TTS_PORT = int(os.environ.get("TTS_PORT", "8004"))

# Global model instance
tts_model = None

app = FastAPI(title="Qwen3-TTS Service")


class TTSRequest(BaseModel):
    text: str
    language: str = "Chinese"
    ref_audio: Optional[str] = None
    ref_text: Optional[str] = None


@app.on_event("startup")
async def load_model():
    """Load Qwen3-TTS model on startup"""
    global tts_model

    try:
        logger.info(f"Loading Qwen3-TTS model: {TTS_MODEL}")
        logger.info(f"Device: {TTS_DEVICE}")

        from qwen_tts import Qwen3TTSModel

        tts_model = Qwen3TTSModel.from_pretrained(
            TTS_MODEL,
            device_map=TTS_DEVICE,
            dtype=torch.bfloat16,
            attn_implementation="sdpa",  # Use scaled_dot_product_attention (ROCm compatible)
        )

        logger.info("✅ Qwen3-TTS model loaded successfully")

    except Exception as e:
        logger.error(f"❌ Failed to load TTS model: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok" if tts_model is not None else "loading",
        "model": TTS_MODEL,
        "device": TTS_DEVICE,
        "model_loaded": tts_model is not None,
    }


@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    """
    Synthesize speech from text using voice cloning

    Args:
        text: Text to synthesize
        language: Target language (e.g., "Chinese", "English")
        ref_audio: Reference audio URL for voice cloning (optional)
        ref_text: Reference audio transcript (optional)

    Returns:
        Audio file (WAV format)
    """
    if tts_model is None:
        raise HTTPException(status_code=503, detail="TTS model not loaded")

    try:
        logger.info(f"Synthesizing: {request.text[:50]}...")

        # Generate speech
        if request.ref_audio and request.ref_text:
            # Voice cloning mode
            wavs, sr = tts_model.generate_voice_clone(
                text=request.text,
                language=request.language,
                ref_audio=request.ref_audio,
                ref_text=request.ref_text,
            )
        else:
            # Standard synthesis (may need default voice)
            wavs, sr = tts_model.generate(
                text=request.text,
                language=request.language,
            )

        # Convert to WAV bytes
        audio_bytes = io.BytesIO()
        sf.write(audio_bytes, wavs[0], sr, format="WAV")
        audio_bytes.seek(0)

        logger.info(f"✅ Synthesis complete ({len(wavs[0])} samples at {sr}Hz)")

        return Response(
            content=audio_bytes.read(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=output.wav"
            }
        )

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Qwen3-TTS service on port {TTS_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=TTS_PORT)
