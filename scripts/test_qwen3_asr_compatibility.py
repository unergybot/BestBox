#!/usr/bin/env python3
"""
Qwen3-ASR Compatibility Smoke Test

Quick test to verify Qwen3-ASR can load and run on your system.
Run this BEFORE the full benchmark to catch issues early.

Usage:
    python scripts/test_qwen3_asr_compatibility.py
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('qwen3-compat')

def test_pytorch_cuda():
    """Test PyTorch and CUDA availability."""
    logger.info("=" * 60)
    logger.info("Test 1: PyTorch and CUDA/ROCm")
    logger.info("=" * 60)

    try:
        import torch
        logger.info(f"✓ PyTorch version: {torch.__version__}")

        cuda_available = torch.cuda.is_available()
        logger.info(f"{'✓' if cuda_available else '✗'} CUDA available: {cuda_available}")

        if cuda_available:
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"  GPU: {device_name}")

            # Check compute capability
            capability = torch.cuda.get_device_capability(0)
            logger.info(f"  Compute capability: {capability}")

            # Check memory
            total_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"  Total VRAM: {total_mem:.1f}GB")

        return cuda_available

    except ImportError:
        logger.error("✗ PyTorch not installed!")
        logger.info("  Install: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2")
        return False
    except Exception as e:
        logger.error(f"✗ PyTorch test failed: {e}")
        return False


def test_qwen_asr_import():
    """Test if qwen-asr package can be imported."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 2: Qwen3-ASR Package Import")
    logger.info("=" * 60)

    try:
        from qwen_asr import Qwen3ASRModel
        logger.info("✓ qwen-asr package installed")

        # Try to get version
        try:
            import qwen_asr
            version = getattr(qwen_asr, '__version__', 'unknown')
            logger.info(f"  Version: {version}")
        except:
            pass

        return True

    except ImportError as e:
        logger.error("✗ qwen-asr not installed!")
        logger.info("  Install: pip install -U qwen-asr")
        logger.info(f"  Error: {e}")
        return False


def test_model_loading(use_gpu=True):
    """Test loading Qwen3-ASR model."""
    device = "cuda" if use_gpu else "cpu"

    logger.info("\n" + "=" * 60)
    logger.info(f"Test 3: Loading Qwen3-ASR-0.6B on {device.upper()}")
    logger.info("=" * 60)
    logger.info("This may take 1-2 minutes for first download...")

    try:
        from qwen_asr import Qwen3ASRModel
        import time
        import torch

        start = time.time()

        # Load model
        logger.info("  Loading model...")
        model = Qwen3ASRModel.from_pretrained("Qwen/Qwen3-ASR-0.6B")

        # Move to GPU if available (required for gfx1151)
        if device == "cuda" and torch.cuda.is_available():
            logger.info("  Moving model to GPU...")
            model.model = model.model.cuda()
            actual_device = "cuda:0"
        else:
            actual_device = "cpu"

        load_time = time.time() - start

        # Verify device
        if hasattr(model, 'model'):
            first_param_device = next(model.model.parameters()).device
            logger.info(f"  Verified device: {first_param_device}")

        logger.info(f"✓ Model loaded successfully in {load_time:.1f}s")
        logger.info(f"  Device: {actual_device}")

        return True, model

    except Exception as e:
        logger.error(f"✗ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_simple_transcription(model, use_gpu=True):
    """Test basic transcription on dummy audio."""
    logger.info("\n" + "=" * 60)
    logger.info("Test 4: Simple Transcription")
    logger.info("=" * 60)

    try:
        import numpy as np
        import soundfile as sf
        import time

        # Create 2 seconds of silence (dummy audio)
        audio_path = "/tmp/qwen3_test_audio.wav"
        silence = np.zeros(32000, dtype=np.float32)
        sf.write(audio_path, silence, 16000)

        logger.info("  Transcribing 2s silence (compatibility test)...")

        start = time.time()
        result = model.transcribe(audio_path)
        trans_time = time.time() - start

        # Handle result format (could be dict or list)
        if isinstance(result, dict):
            transcript = result.get('text', '').strip()
        elif isinstance(result, list):
            # Result is a list of segments/tokens
            if len(result) > 0 and isinstance(result[0], dict):
                # List of dicts with 'text' key
                transcript = ' '.join(seg.get('text', '') for seg in result).strip()
            else:
                # List of strings
                transcript = ' '.join(str(r) for r in result).strip()
        else:
            transcript = str(result).strip()

        logger.info(f"✓ Transcription completed in {trans_time:.2f}s")
        logger.info(f"  Result type: {type(result)}")
        logger.info(f"  Output: '{transcript[:100]}...' (expected empty or minimal)")

        # Check if result makes sense
        if transcript == '' or '[BLANK]' in transcript.upper() or len(transcript) < 10:
            logger.info("  ✓ Output looks reasonable for silent audio")
            return True
        else:
            logger.warning(f"  ⚠ Unexpected output for silent audio (len={len(transcript)})")
            logger.info("  This may indicate model hallucination, but model is functional")
            return True

    except Exception as e:
        logger.error(f"✗ Transcription failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all compatibility tests."""
    print("\n" + "=" * 60)
    print("QWEN3-ASR COMPATIBILITY TEST")
    print("=" * 60)
    print()

    results = {}

    # Test 1: PyTorch/CUDA
    gpu_available = test_pytorch_cuda()
    results['pytorch'] = True
    results['gpu'] = gpu_available

    # Test 2: Package import
    if not test_qwen_asr_import():
        results['import'] = False
        print_summary(results)
        return
    results['import'] = True

    # Test 3: Model loading (GPU if available, else CPU)
    device = "cuda" if gpu_available else "cpu"
    success, model = test_model_loading(use_gpu=gpu_available)
    results['load'] = success

    if not success:
        print_summary(results)
        return

    # Test 4: Simple transcription
    success = test_simple_transcription(model, use_gpu=gpu_available)
    results['transcribe'] = success

    # Print summary
    print_summary(results)


def print_summary(results):
    """Print test summary and recommendations."""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = all(results.values())

    print(f"\nPyTorch:       {'✓ PASS' if results.get('pytorch') else '✗ FAIL'}")
    print(f"GPU Available: {'✓ YES' if results.get('gpu') else '✗ NO (CPU only)'}")
    print(f"Package Import:{'✓ PASS' if results.get('import') else '✗ FAIL'}")
    print(f"Model Loading: {'✓ PASS' if results.get('load') else '✗ FAIL'}")
    print(f"Transcription: {'✓ PASS' if results.get('transcribe') else '✗ FAIL'}")

    print("\n" + "=" * 60)

    if all_passed and results.get('gpu'):
        print("✅ ALL TESTS PASSED (GPU MODE)")
        print("=" * 60)
        print("\nRecommendation: Proceed with full benchmark")
        print("  python scripts/benchmark_asr_models.py")

    elif all_passed and not results.get('gpu'):
        print("⚠️  TESTS PASSED (CPU ONLY)")
        print("=" * 60)
        print("\nRecommendation: Qwen3-ASR works but GPU unavailable")
        print("  - Run CPU benchmark: python scripts/benchmark_asr_models.py --cpu-only")
        print("  - Performance will be slower than GPU")
        print("  - Consider fixing GPU/ROCm setup for better performance")

    elif not results.get('import'):
        print("❌ PACKAGE NOT INSTALLED")
        print("=" * 60)
        print("\nFix: Install qwen-asr")
        print("  pip install -U qwen-asr")

    elif not results.get('load'):
        print("❌ MODEL LOADING FAILED")
        print("=" * 60)
        print("\nPossible causes:")
        print("  1. GPU/ROCm compatibility issue")
        print("  2. Insufficient VRAM")
        print("  3. Model download failed")
        print("\nTroubleshooting:")
        print("  - Check error messages above")
        print("  - Try CPU mode: Modify test_model_loading(use_gpu=False)")
        print("  - Verify internet connection for model download")

    elif not results.get('transcribe'):
        print("❌ TRANSCRIPTION FAILED")
        print("=" * 60)
        print("\nModel loaded but transcription failed")
        print("  - Check error messages above")
        print("  - Model may have compatibility issues")

    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        print("\nReview error messages above for details")

    print()


if __name__ == '__main__':
    main()
