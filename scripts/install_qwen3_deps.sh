#!/bin/bash
# Install dependencies for Qwen3-ASR testing

set -e

echo "=================================="
echo "Installing Qwen3-ASR Dependencies"
echo "=================================="

# Activate environment
source ~/BestBox/activate.sh

echo ""
echo "Installing benchmark utilities..."
pip install -q jiwer soundfile datasets

echo ""
echo "Installing PyTorch with ROCm support..."
pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2

echo ""
echo "Installing Qwen3-ASR..."
pip install -q -U qwen-asr

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "Verify installation:"
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')

try:
    from qwen_asr import Qwen3ASRModel
    print('Qwen3-ASR: Installed ✓')
except ImportError:
    print('Qwen3-ASR: Not installed ✗')

try:
    from faster_whisper import WhisperModel
    print('faster-whisper: Installed ✓')
except ImportError:
    print('faster-whisper: Not installed ✗')
"

echo ""
echo "Next step: Run smoke test"
echo "  python scripts/test_qwen3_asr_compatibility.py"
