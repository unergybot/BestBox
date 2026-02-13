#!/bin/bash
# BestBox Environment Activation Script
# Source this file to activate Python virtual environment with ROCm settings

# Activate virtual environment
source ~/BestBox/venv/bin/activate

# ROCm environment variables
export ROCM_PATH=/opt/rocm-7.2.0
export ROCM_HOME=/opt/rocm-7.2.0
export PATH=$ROCM_PATH/bin:$PATH
export LD_LIBRARY_PATH=$ROCM_PATH/lib:$LD_LIBRARY_PATH

# HIP configuration
export HIP_PATH=$ROCM_PATH/hip
export HIP_PLATFORM=amd

# GPU architecture mapping (gfx1151 → gfx1100 family)
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100

# LLM Backend (vLLM)
export LLM_BASE_URL="http://localhost:8001/v1"

# Model paths (use ModelScope cache)
export HF_HOME="$HOME/.cache/modelscope/hub/models"
export TRANSFORMERS_CACHE="$HOME/.cache/modelscope/hub/models"
export SENTENCE_TRANSFORMERS_HOME="$HOME/.cache/modelscope/hub/models"

# Embeddings & Reranker models
export EMBEDDINGS_MODEL_NAME="BAAI/bge-m3"
export RERANKER_MODEL_NAME="BAAI/bge-reranker-v2-m3"

# Optional: Enable ROCm debugging
# export AMD_LOG_LEVEL=3
# export HIP_VISIBLE_DEVICES=0

echo "✅ BestBox environment activated"
echo "   Python: $(python --version)"
echo "   PyTorch: $(python -c 'import torch; print(torch.__version__)')"

# GPU info (robust: avoid shell escaping issues)
python - <<'PY'
import torch

available = torch.cuda.is_available()
print(f"   Torch CUDA available: {available}")
if available:
	try:
		print(f"   GPU: {torch.cuda.get_device_name(0)}")
	except Exception:
		print("   GPU: <unknown>")

	try:
		mem_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
		print(f"   GPU Memory: {mem_gb:.1f} GB")
	except Exception:
		print("   GPU Memory: <unknown>")
PY
