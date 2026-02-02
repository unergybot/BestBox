#!/bin/bash
# Install/Build FunASR + MeloTTS Speech Service for P100
#
# This script builds the Docker container for P100-compatible speech services.
# Uses PyTorch 2.1.2 + CUDA 11.8 (compatible with P100 SM60).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "Building Speech Service for P100 (Docker)"
echo "========================================"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is required but not installed."
    exit 1
fi

# Check NVIDIA Docker
if ! docker info 2>/dev/null | grep -q "Runtimes.*nvidia"; then
    echo "WARNING: nvidia-docker runtime not detected."
    echo "GPU acceleration may not work."
fi

# Check GPU
echo "Checking GPUs..."
nvidia-smi --query-gpu=index,name,compute_cap,memory.total --format=csv,noheader
echo ""

# Build the image
echo "Building Docker image..."
echo "Base: pytorch/pytorch:2.1.2-cuda11.8-cudnn8-devel"
echo ""

docker build \
    -t bestbox-speech-p100:latest \
    -f ${PROJECT_ROOT}/docker/Dockerfile.speech-p100 \
    ${PROJECT_ROOT}

echo ""
echo "========================================"
echo "Build Complete!"
echo "========================================"
echo ""
echo "To start the service:"
echo "  ./scripts/start-speech-p100-docker.sh run"
echo ""
echo "Or with custom GPU ID (default: 0):"
echo "  SPEECH_GPU_ID=1 ./scripts/start-speech-p100-docker.sh run"
echo ""
echo "To view logs:"
echo "  ./scripts/start-speech-p100-docker.sh logs"
echo ""
