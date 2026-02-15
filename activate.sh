#!/bin/bash
# BestBox Unified Activation Script
# Source this file to activate Python environment with automatic GPU backend selection

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
	source "$SCRIPT_DIR/venv/bin/activate"
else
	echo "⚠️  Virtual environment not found: $SCRIPT_DIR/venv"
	return 1 2>/dev/null || exit 1
fi

source "$SCRIPT_DIR/scripts/detect-gpu.sh"
GPU_BACKEND="$(detect_gpu)" || return 1 2>/dev/null || exit 1
export BESTBOX_GPU_BACKEND="$GPU_BACKEND"

case "$GPU_BACKEND" in
	cuda)
		export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"
		export PATH="$CUDA_HOME/bin:$PATH"
		export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
		export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-max_split_size_mb:512}"

		unset HSA_OVERRIDE_GFX_VERSION PYTORCH_ROCM_ARCH
		unset ROCM_PATH ROCM_HOME HIP_PATH HIP_PLATFORM FLASH_ATTENTION_TRITON_AMD_ENABLE
		;;
	rocm)
		export ROCM_PATH="/opt/rocm-7.2.0"
		export ROCM_HOME="/opt/rocm-7.2.0"
		export PATH="$ROCM_PATH/bin:$PATH"
		export LD_LIBRARY_PATH="$ROCM_PATH/lib:${LD_LIBRARY_PATH:-}"
		export HIP_PATH="$ROCM_PATH/hip"
		export HIP_PLATFORM="amd"
		export HSA_OVERRIDE_GFX_VERSION="11.0.0"
		export PYTORCH_ROCM_ARCH="gfx1100"
		export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"

		unset CUDA_HOME CUDA_VISIBLE_DEVICES PYTORCH_CUDA_ALLOC_CONF
		;;
	cpu)
		unset CUDA_HOME CUDA_VISIBLE_DEVICES PYTORCH_CUDA_ALLOC_CONF
		unset ROCM_PATH ROCM_HOME HIP_PATH HIP_PLATFORM
		unset HSA_OVERRIDE_GFX_VERSION PYTORCH_ROCM_ARCH FLASH_ATTENTION_TRITON_AMD_ENABLE
		;;
esac

export LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:8001/v1}"
export HF_HOME="${HF_HOME:-$HOME/.cache/modelscope/hub/models}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HOME/.cache/modelscope/hub/models}"
export SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-$HOME/.cache/modelscope/hub/models}"
export EMBEDDINGS_MODEL_NAME="${EMBEDDINGS_MODEL_NAME:-BAAI/bge-m3}"
export RERANKER_MODEL_NAME="${RERANKER_MODEL_NAME:-BAAI/bge-reranker-v2-m3}"

export BESTBOX_COMPOSE_FILES="-f docker-compose.yml -f docker-compose.${GPU_BACKEND}.yml"

echo "✅ BestBox environment activated (${GPU_BACKEND} mode)"
echo "   Python: $(python --version 2>/dev/null || echo unknown)"

if [ "$GPU_BACKEND" = "cpu" ]; then
	echo "   GPU: CPU fallback"
else
	python - <<'PY'
try:
	import torch
except Exception:
	print("   Torch: not installed")
	raise SystemExit(0)

available = torch.cuda.is_available()
print(f"   Torch CUDA available: {available}")
if available:
	try:
		print(f"   GPU: {torch.cuda.get_device_name(0)}")
	except Exception:
		print("   GPU: <unknown>")
PY
fi
