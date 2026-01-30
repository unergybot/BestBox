#!/usr/bin/env python3
"""
Diagnose why Qwen3-ASR isn't using GPU despite CUDA being available.
"""

import torch
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('gpu-diagnose')

print("=" * 60)
print("QWEN3-ASR GPU DIAGNOSTIC")
print("=" * 60)

# Step 1: Check PyTorch CUDA
print("\n1. PyTorch CUDA Status:")
print(f"   PyTorch version: {torch.__version__}")
print(f"   CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   CUDA version: {torch.version.cuda}")
    print(f"   GPU count: {torch.cuda.device_count()}")
    print(f"   Current device: {torch.cuda.current_device()}")
    print(f"   Device name: {torch.cuda.get_device_name(0)}")
    print(f"   Device capability: {torch.cuda.get_device_capability(0)}")

# Step 2: Load Qwen3-ASR model
print("\n2. Loading Qwen3-ASR model...")
try:
    from qwen_asr import Qwen3ASRModel

    model = Qwen3ASRModel.from_pretrained("Qwen/Qwen3-ASR-0.6B")
    print("   ✓ Model loaded")

    # Step 3: Inspect model structure
    print("\n3. Inspecting model structure:")
    print(f"   Model type: {type(model)}")
    print(f"   Has 'model' attr: {hasattr(model, 'model')}")
    print(f"   Has 'device' attr: {hasattr(model, 'device')}")

    if hasattr(model, 'model'):
        print(f"   Inner model type: {type(model.model)}")

        # Check device of internal model parameters
        try:
            first_param = next(model.model.parameters())
            print(f"   First parameter device: {first_param.device}")
            print(f"   First parameter dtype: {first_param.dtype}")
        except StopIteration:
            print("   No parameters found in model")

    # Step 4: Try to move model to GPU manually
    print("\n4. Attempting to move model to GPU:")

    if hasattr(model, 'model') and torch.cuda.is_available():
        try:
            print("   Trying model.model.cuda()...")
            model.model = model.model.cuda()

            # Verify
            first_param = next(model.model.parameters())
            print(f"   ✓ Model moved! Device: {first_param.device}")

            # Step 5: Test transcription on GPU
            print("\n5. Testing transcription on GPU:")
            import numpy as np
            import soundfile as sf

            # Create test audio
            audio_path = "/tmp/gpu_test.wav"
            silence = np.zeros(16000, dtype=np.float32)  # 1 second
            sf.write(audio_path, silence, 16000)

            import time
            start = time.time()
            result = model.transcribe(audio_path)
            elapsed = time.time() - start

            print(f"   ✓ Transcription completed in {elapsed:.2f}s")
            print(f"   Result type: {type(result)}")
            if isinstance(result, list) and len(result) > 0:
                print(f"   Result: {result[0]}")

            print("\n" + "=" * 60)
            print("✅ SUCCESS - Model can use GPU!")
            print("=" * 60)
            print("\nSolution: Need to manually move model.model.cuda()")

        except Exception as e:
            print(f"   ✗ Failed to move to GPU: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⚠ Cannot move model (no CUDA or no internal model)")

    # Step 6: Check for device parameter in from_pretrained
    print("\n6. Checking Qwen3ASRModel API:")
    import inspect
    sig = inspect.signature(Qwen3ASRModel.from_pretrained)
    print(f"   from_pretrained params: {sig}")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
