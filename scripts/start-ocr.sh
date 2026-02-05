#!/bin/bash
# Start GOT-OCR2.0 service on port 8084
# Target: P100 GPU (16GB VRAM, CUDA 11.8)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set environment variables
export OCR_PORT=${OCR_PORT:-8084}
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}

echo "Starting GOT-OCR2.0 service..."
echo "  Port: $OCR_PORT"
echo "  GPU: $CUDA_VISIBLE_DEVICES"

# Run the OCR service
python -m uvicorn services.ocr.got_ocr_service:app \
    --host 0.0.0.0 \
    --port "$OCR_PORT" \
    --log-level info
