#!/bin/bash
set -e

# Activate environment
source activate.sh

echo "🚀 Starting Qwen2.5-VL Vision-Language Service"
echo "============================================="
echo ""

# Check GPU availability
echo "📊 Checking GPU availability..."
python3 -c "import torch; print(f'   CUDA available: {torch.cuda.is_available()}'); \
            print(f'   Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}'); \
            print(f'   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB' if torch.cuda.is_available() else '   GPU Memory: N/A')"

echo ""

# Check if transformers is installed
if ! python3 -c "import transformers" 2>/dev/null; then
    echo "⚠️  transformers not found, installing..."
    pip install transformers accelerate sentencepiece
fi

# Check if model exists in cache
MODEL_PATH="$HOME/.cache/huggingface/hub/models--Qwen--Qwen2.5-VL-3B-Instruct"
if [ ! -d "$MODEL_PATH" ]; then
    echo "📥 Qwen2.5-VL-3B-Instruct not found in cache"
    echo "   Model will be downloaded on first run (~7GB, may take 5-10 minutes)"
    echo ""
    read -p "   Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Create logs directory
mkdir -p logs

echo ""
echo "🌐 Starting VL service on http://localhost:8083"
echo "   Logs: logs/vl.log"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

# Start service
uvicorn services.vision.qwen2_vl_server:app \
  --host 0.0.0.0 \
  --port 8083 \
  --workers 1 \
  --log-level info \
  2>&1 | tee logs/vl.log
