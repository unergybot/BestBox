#!/bin/bash
# Install FunASR + MeloTTS for P100 GPU
# Optimized for SM60 (Pascal), CUDA 11.x

set -e

echo "========================================"
echo "Installing Speech Components for P100"
echo "========================================"
echo ""

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv,noheader
    echo ""
else
    echo "WARNING: nvidia-smi not found. GPU acceleration may not work."
    echo ""
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "Python version: $PYTHON_VERSION"
echo ""

# Install PyTorch with CUDA 11.8 (compatible with P100)
echo "Step 1: Installing PyTorch with CUDA 11.8..."
echo "----------------------------------------"
pip install torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118
echo ""

# Verify PyTorch CUDA
python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        print(f'  GPU {i}: {props.name} (SM {props.major}.{props.minor}, {props.total_memory // 1024**2} MB)')
"
echo ""

# Install FunASR
echo "Step 2: Installing FunASR..."
echo "----------------------------------------"
pip install funasr modelscope
echo ""

# Install MeloTTS
echo "Step 3: Installing MeloTTS..."
echo "----------------------------------------"
pip install melo-tts
echo ""

# Install additional dependencies
echo "Step 4: Installing audio processing dependencies..."
echo "----------------------------------------"
pip install scipy
echo ""

# Pre-download models
echo "Step 5: Pre-downloading models..."
echo "----------------------------------------"

echo "Downloading FunASR Paraformer-large (this may take a while)..."
python3 -c "
from funasr import AutoModel
print('Loading Paraformer-large with VAD and punctuation...')
model = AutoModel(
    model='iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch',
    device='cpu'  # Download on CPU first
)
print('FunASR model downloaded successfully!')
"
echo ""

echo "Downloading MeloTTS Chinese..."
python3 -c "
from melo.api import TTS
print('Loading MeloTTS Chinese...')
model = TTS(language='ZH', device='cpu')  # Download on CPU first
print('MeloTTS model downloaded successfully!')
print(f'Available speakers: {list(model.hps.data.spk2id.keys())}')
"
echo ""

# Test on GPU
echo "Step 6: Testing GPU inference..."
echo "----------------------------------------"

python3 -c "
import torch

if torch.cuda.is_available() and torch.cuda.device_count() > 1:
    device = 'cuda:1'  # P100
    print(f'Testing on {device}...')

    # Test FunASR
    print('Testing FunASR on GPU...')
    from funasr import AutoModel
    import numpy as np

    model = AutoModel(
        model='iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch',
        device=device
    )

    # Test with silence
    silence = np.zeros(16000, dtype=np.float32)
    result = model.generate(input=silence)
    print(f'  FunASR test passed: {result}')

    # Test MeloTTS
    print('Testing MeloTTS on GPU...')
    from melo.api import TTS

    tts = TTS(language='ZH', device=device)
    # Just verify it loads, don't synthesize
    print(f'  MeloTTS loaded on {device}')

    print('GPU tests passed!')
else:
    print('GPU test skipped (cuda:1 not available)')
    print('Models will fall back to CPU or cuda:0')
"

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Usage:"
echo "  # Set environment variables"
echo "  export ASR_ENGINE=funasr"
echo "  export TTS_ENGINE=melo"
echo "  export ASR_DEVICE=cuda:1"
echo "  export TTS_DEVICE=cuda:1"
echo ""
echo "  # Start S2S service"
echo "  ./scripts/start-s2s.sh"
echo ""
