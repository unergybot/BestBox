#!/bin/bash
# BestBox Environment Activation Script for CUDA
# Source this file to activate Python virtual environment with CUDA settings

# Activate virtual environment
source ~/BestBox/venv/bin/activate

# CUDA environment variables
export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# GPU configuration for CUDA system
# Tesla P100 (GPU 0) - 16GB - NOT compatible with PyTorch 2.10+ (sm_60 < sm_70)
# RTX 3080 (GPU 1) - 10GB - supports PyTorch (sm_86)
# Only use GPU 1 (RTX 3080) for native PyTorch-based services (vLLM)
export CUDA_VISIBLE_DEVICES=1

# PyTorch CUDA settings
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

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

# GPU info
python - <<'PY'
import torch

print(f"   CUDA available: {torch.cuda.is_available()}")
print(f"   CUDA version: {torch.version.cuda}")
print(f"   GPU count: {torch.cuda.device_count()}")
for i in range(torch.cuda.device_count()):
    try:
        name = torch.cuda.get_device_name(i)
        mem_gb = torch.cuda.get_device_properties(i).total_memory / 1024**3
        print(f"   GPU {i}: {name} ({mem_gb:.1f} GB)")
    except Exception as e:
        print(f"   GPU {i}: <error: {e}>")
PY
