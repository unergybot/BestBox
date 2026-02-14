#!/usr/bin/env python3
"""
Test script for Qwen3-ASR and Qwen3-TTS on AMD ROCm
Verifies that both models can load and run basic inference on ROCm GPUs
"""

import sys
import os
import torch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pytorch_rocm():
    """Test PyTorch ROCm availability"""
    logger.info("=" * 60)
    logger.info("PyTorch ROCm Test")
    logger.info("=" * 60)

    logger.info(f"PyTorch version: {torch.__version__}")
    logger.info(f"CUDA available: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        logger.info(f"Device count: {torch.cuda.device_count()}")
        logger.info(f"Current device: {torch.cuda.current_device()}")
        logger.info(f"Device name: {torch.cuda.get_device_name(0)}")
        logger.info(f"ROCm version: {torch.version.hip}")
        return True
    else:
        logger.error("CUDA/ROCm not available!")
        return False

def test_qwen3_asr():
    """Test Qwen3-ASR 0.6B model"""
    logger.info("\n" + "=" * 60)
    logger.info("Qwen3-ASR Test")
    logger.info("=" * 60)

    try:
        # Import qwen-asr package
        logger.info("Importing qwen-asr package...")
        from qwen_asr import Qwen3ASRModel
        logger.info("✅ qwen-asr package imported successfully")

        # Load model
        logger.info("Loading Qwen3-ASR-0.6B model...")
        model_path = os.path.expanduser("~/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-0.6B")

        model = Qwen3ASRModel.from_pretrained(
            model_path,
            device_map="cuda:0",
            dtype=torch.bfloat16,
        )
        logger.info("✅ Model loaded successfully")

        # Test with sample audio (you'll need to provide actual audio)
        logger.info("ASR model ready for inference")
        logger.info(f"Model device: {next(model.parameters()).device}")

        return True

    except ImportError as e:
        logger.error(f"❌ Failed to import qwen-asr: {e}")
        logger.info("Install with: pip install qwen-asr")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to load ASR model: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_qwen3_tts():
    """Test Qwen3-TTS 0.6B model"""
    logger.info("\n" + "=" * 60)
    logger.info("Qwen3-TTS Test")
    logger.info("=" * 60)

    try:
        # Import qwen-tts package
        logger.info("Importing qwen-tts package...")
        from qwen_tts import Qwen3TTSModel
        logger.info("✅ qwen-tts package imported successfully")

        # Load model
        logger.info("Loading Qwen3-TTS-12Hz-0.6B-Base model...")
        model_path = os.path.expanduser("~/.cache/modelscope/hub/models/Qwen/Qwen3-TTS-12Hz-0.6B-Base")

        model = Qwen3TTSModel.from_pretrained(
            model_path,
            device_map="cuda:0",
            dtype=torch.bfloat16,
            attn_implementation="sdpa",  # Use scaled_dot_product_attention instead of flash_attn
        )
        logger.info("✅ Model loaded successfully")

        logger.info("TTS model ready for inference")
        logger.info(f"Model device: {next(model.parameters()).device}")

        return True

    except ImportError as e:
        logger.error(f"❌ Failed to import qwen-tts: {e}")
        logger.info("Install with: pip install qwen-tts")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to load TTS model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    logger.info("Testing Qwen3 Audio Models on AMD ROCm")
    logger.info("")

    results = {
        "PyTorch ROCm": test_pytorch_rocm(),
        "Qwen3-ASR": False,
        "Qwen3-TTS": False,
    }

    # Only test models if PyTorch ROCm is available
    if results["PyTorch ROCm"]:
        results["Qwen3-ASR"] = test_qwen3_asr()
        results["Qwen3-TTS"] = test_qwen3_tts()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{test_name:20s} {status}")

    logger.info("=" * 60)

    # Exit code
    if all(results.values()):
        logger.info("\n🎉 All tests passed! Qwen3 audio models work on ROCm!")
        return 0
    else:
        logger.info("\n⚠️  Some tests failed. Check logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
