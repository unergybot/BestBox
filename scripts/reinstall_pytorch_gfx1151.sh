#!/bin/bash
# Reinstall PyTorch with AMD's official gfx1151 wheels
# This provides proper GPU support for Radeon 8060S (Strix Halo)

set -e

echo "============================================================"
echo "PyTorch Reinstall for gfx1151 (AMD Radeon 8060S)"
echo "============================================================"
echo ""

# Activate environment
source ~/BestBox/activate.sh

echo "Step 1: Uninstalling current PyTorch..."
pip uninstall -y torch torchvision torchaudio || true

echo ""
echo "Step 2: Installing AMD official gfx1151 PyTorch wheels..."
echo "  Source: https://repo.amd.com/rocm/whl/gfx1151/"
echo ""

pip install --index-url https://repo.amd.com/rocm/whl/gfx1151/ torch torchvision torchaudio

echo ""
echo "Step 3: Verifying installation..."
python -c "
import torch
print('=' * 60)
print('PyTorch Installation Verification')
print('=' * 60)
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU count: {torch.cuda.device_count()}')
    print(f'GPU name: {torch.cuda.get_device_name(0)}')
    print(f'GPU capability: {torch.cuda.get_device_capability(0)}')

    # Test GPU memory allocation
    try:
        x = torch.randn(100, 100).cuda()
        print(f'GPU memory test: ✓ PASS')
        print(f'Allocated VRAM: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB')
    except Exception as e:
        print(f'GPU memory test: ✗ FAIL - {e}')
else:
    print('⚠ WARNING: CUDA not available!')
print('=' * 60)
"

echo ""
echo "============================================================"
echo "Installation Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Test Qwen3-ASR GPU usage:"
echo "     python scripts/diagnose_qwen3_gpu.py"
echo ""
echo "  2. If GPU works, run benchmark:"
echo "     python scripts/benchmark_asr_models.py --quick"
echo ""
