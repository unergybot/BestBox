#!/usr/bin/env python3
"""
Test script for Qwen2-VL model setup

This script verifies that:
1. Required packages are installed
2. Model can be loaded (or downloaded)
3. Basic inference works
4. Service can be started

Usage:
    python scripts/test_vl_model.py [--download-only] [--quick-test]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import torch
from PIL import Image
import io


def check_prerequisites():
    """Check if all prerequisites are met"""
    print("=" * 70)
    print("CHECKING PREREQUISITES")
    print("=" * 70)
    print()

    checks_passed = True

    # Check CUDA
    print("1. GPU Availability:")
    if torch.cuda.is_available():
        print(f"   ✅ CUDA available")
        print(f"   ✅ Device: {torch.cuda.get_device_name(0)}")
        print(f"   ✅ Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    else:
        print("   ⚠️  CUDA not available - will use CPU (very slow)")

    print()

    # Check packages
    print("2. Required Packages:")
    required = ['transformers', 'accelerate', 'sentencepiece', 'qwen_vl_utils']
    for package in required:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - MISSING")
            checks_passed = False

    print()

    # Check disk space
    print("3. Disk Space:")
    import shutil
    cache_path = Path.home() / ".cache" / "huggingface"
    cache_path.mkdir(parents=True, exist_ok=True)

    stat = shutil.disk_usage(cache_path)
    free_gb = stat.free / 1024**3
    print(f"   Available: {free_gb:.1f}GB")
    if free_gb < 20:
        print(f"   ⚠️  Low disk space (need ~14GB for model)")
        checks_passed = False
    else:
        print(f"   ✅ Sufficient space for model download")

    print()
    return checks_passed


def download_model():
    """Download Qwen3-VL model"""
    print("=" * 70)
    print("DOWNLOADING QWEN3-VL MODEL")
    print("=" * 70)
    print()

    print("📥 Downloading Qwen3-VL-8B-Instruct...")
    print("   Size: ~16GB")
    print("   This may take 10-30 minutes depending on your internet speed")
    print()

    try:
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

        print("Loading model (downloading if needed)...")
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            "Qwen/Qwen3-VL-8B-Instruct",
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
            trust_remote_code=True
        )

        processor = AutoProcessor.from_pretrained(
            "Qwen/Qwen3-VL-8B-Instruct",
            trust_remote_code=True
        )

        print()
        print("✅ Model downloaded and loaded successfully!")
        print(f"   Model memory: ~{torch.cuda.memory_allocated() / 1024**3:.2f}GB")

        return model, processor

    except Exception as e:
        print(f"❌ Failed to download model: {e}")
        return None, None


def quick_test(model, processor):
    """Run a quick inference test"""
    print()
    print("=" * 70)
    print("QUICK INFERENCE TEST")
    print("=" * 70)
    print()

    try:
        # Create a simple test image (solid color)
        print("Creating test image...")
        test_image = Image.new('RGB', (640, 480), color=(73, 109, 137))

        # Simple test prompt
        prompt = "Describe this image briefly."

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": test_image},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        print("Preparing inputs...")
        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor(
            text=[text],
            images=[test_image],
            return_tensors="pt"
        ).to("cuda" if torch.cuda.is_available() else "cpu")

        print("Generating response...")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                temperature=0.7
            )

        response = processor.batch_decode(outputs, skip_special_tokens=True)[0]

        print()
        print("✅ Inference successful!")
        print(f"   Response length: {len(response)} chars")
        print(f"   Sample: {response[:200]}...")

        return True

    except Exception as e:
        print(f"❌ Inference test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_service_endpoints():
    """Test if the service can be imported and basic endpoints work"""
    print()
    print("=" * 70)
    print("TESTING SERVICE IMPORT")
    print("=" * 70)
    print()

    try:
        print("Importing VL service...")
        from services.vision import qwen2_vl_server

        print("✅ Service module imported successfully")

        # Check if FastAPI app exists
        if hasattr(qwen2_vl_server, 'app'):
            print("✅ FastAPI app found")
            print(f"   Title: {qwen2_vl_server.app.title}")
            print(f"   Version: {qwen2_vl_server.app.version}")
        else:
            print("⚠️  FastAPI app not found")

        return True

    except Exception as e:
        print(f"❌ Service import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Qwen2-VL setup")
    parser.add_argument(
        '--download-only',
        action='store_true',
        help='Only download the model, skip tests'
    )
    parser.add_argument(
        '--quick-test',
        action='store_true',
        help='Run quick inference test'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip model download (assumes already downloaded)'
    )

    args = parser.parse_args()

    # Step 1: Check prerequisites
    if not check_prerequisites():
        print()
        print("❌ Prerequisites check failed!")
        print("   Please fix the issues above and try again")
        return 1

    # Step 2: Download model
    model, processor = None, None
    if not args.skip_download:
        model, processor = download_model()
        if model is None:
            return 1
    else:
        print("⏭️  Skipping model download")

    if args.download_only:
        print()
        print("✅ Model download complete (--download-only mode)")
        return 0

    # Step 3: Quick inference test
    if args.quick_test and model is not None:
        if not quick_test(model, processor):
            return 1

    # Step 4: Test service import
    if not test_service_endpoints():
        return 1

    # Summary
    print()
    print("=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Start VL service: ./scripts/start-vl.sh")
    print("  2. Test health: curl http://localhost:8083/health")
    print("  3. Test analysis: curl -X POST http://localhost:8083/analyze-image \\")
    print("                         -F 'file=@path/to/image.jpg'")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
