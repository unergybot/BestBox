#!/usr/bin/env python3
import os
import sys
import logging
from faster_whisper import download_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("model_downloader")

def download_asr_model(model_name, output_dir=None):
    """Download faster-whisper model."""
    logger.info(f"Downloading model: {model_name}")
    try:
        # download_model returns the path to the model
        model_path = download_model(model_name, output_dir=output_dir)
        logger.info(f"Successfully downloaded to: {model_path}")
        return model_path
    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        # Try a smaller fallback model if the large one fails
        if "large" in model_name:
            logger.warning("Large model failed. Trying 'medium' as fallback...")
            try:
                return download_model("medium", output_dir=output_dir)
            except Exception as e2:
                logger.error(f"Fallback failed: {e2}")
        sys.exit(1)

if __name__ == "__main__":
    # Default matching the one in start-s2s.sh usually
    model_name = os.environ.get("ASR_MODEL", "Systran/faster-distil-whisper-large-v3")
    
    logger.info("Starting model download check...")
    download_asr_model(model_name)
    logger.info("Ready for S2S service.")
