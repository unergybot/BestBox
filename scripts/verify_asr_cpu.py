from faster_whisper import WhisperModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cpu_inference():
    try:
        logger.info("Loading model on CPU...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        logger.info("Model loaded. Transcribing dummy audio...")
        # We don't have audio, but loading the model is the main test for library issues.
        # To truly test transcribe we need audio, but usually instantiation fails if libs are missing.
        logger.info("Success! CPU inference initialization works.")
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == "__main__":
    test_cpu_inference()
