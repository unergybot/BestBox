#!/bin/bash
# BestBox Environment Activation Script for CUDA
# Source this file to activate Python virtual environment with CUDA settings

# Activate virtual environment
source ~/BestBox/venv/bin/activate

# CUDA environment variables
export CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Optional: pin visible GPUs for CUDA services
if [ -n "${BESTBOX_CUDA_VISIBLE_DEVICES:-}" ]; then
  export CUDA_VISIBLE_DEVICES="$BESTBOX_CUDA_VISIBLE_DEVICES"
fi

# PyTorch CUDA settings
export PYTORCH_CUDA_ALLOC_CONF=${PYTORCH_CUDA_ALLOC_CONF:-max_split_size_mb:512}

# BestBox local services (CUDA docker defaults; override by exporting beforehand)
export LLM_BASE_URL=${LLM_BASE_URL:-http://127.0.0.1:8001/v1}
export LLM_MODEL=${LLM_MODEL:-Qwen/Qwen3-4B-Instruct-2507}
export EMBEDDINGS_URL=${EMBEDDINGS_URL:-http://127.0.0.1:8004}

# Unset ROCm variables if they exist (clean switch from AMD to NVIDIA)
unset HSA_OVERRIDE_GFX_VERSION
unset PYTORCH_ROCM_ARCH
unset ROCM_PATH
unset ROCM_HOME
unset HIP_PATH
unset HIP_PLATFORM

echo "✅ BestBox CUDA environment activated"
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
