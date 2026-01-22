# Python & PyTorch Setup Report

**Date:** January 22, 2026  
**Status:** ✅ COMPLETE

---

## Environment Details

### Python Configuration
- **Python Version:** 3.12.3
- **Virtual Environment:** `/home/unergy/BestBox/venv`
- **Package Manager:** pip 25.3
- **Activation:** `source ~/BestBox/activate.sh`

### PyTorch Installation
- **PyTorch Version:** 2.10.0+rocm7.1
- **ROCm Compatibility:** ROCm 7.1 wheels (compatible with ROCm 7.2)
- **Download Size:** 5.4 GB (torch) + 302 MB (triton-rocm) + dependencies
- **Installation Method:** pip with ROCm 7.1 index

### Packages Installed
```
torch==2.10.0+rocm7.1
torchvision==0.25.0+rocm7.1
torchaudio==2.10.0+rocm7.1
triton-rocm==3.6.0
numpy==2.3.5
pillow==12.0.0
sympy==1.14.0
networkx==3.6.1
fsspec==2025.12.0
jinja2==3.1.6
```

---

## GPU Verification

### Detection Test Results
```python
import torch

PyTorch version: 2.10.0+rocm7.1
GPU available: True
GPU count: 1
GPU name: AMD Radeon 8060S
GPU memory: 96.00 GB
```

### Device Properties
| Property | Value |
|----------|-------|
| **Device Name** | AMD Radeon 8060S |
| **Architecture** | gfx1151 (RDNA 3.5) |
| **Total Memory** | 96 GB |
| **Compute Capability** | 11.5 |
| **ROCm Version** | 7.2.0 (using 7.1 wheels) |
| **Detection Status** | ✅ Successful |

---

## Environment Variables

### ROCm Configuration
```bash
export ROCM_PATH=/opt/rocm-7.2.0
export ROCM_HOME=/opt/rocm-7.2.0
export PATH=$ROCM_PATH/bin:$PATH
export LD_LIBRARY_PATH=$ROCM_PATH/lib:$LD_LIBRARY_PATH
```

### HIP Configuration
```bash
export HIP_PATH=$ROCM_PATH/hip
export HIP_PLATFORM=amd
```

### GPU Architecture Mapping
```bash
# Map gfx1151 (RDNA 3.5) to gfx1100 family for framework compatibility
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100
```

**Note:** The environment variables are automatically set when using `source ~/BestBox/activate.sh`

---

## Known Issues & Solutions

### Issue 1: libdrm Warning (Benign)
**Warning Message:**
```
/opt/amdgpu/share/libdrm/amdgpu.ids: No such file or directory
```

**Impact:** None - GPU detection and functionality work correctly

**Root Cause:** Missing amdgpu device ID database file (cosmetic only)

**Solution:** Can be ignored, or install `amdgpu-core` package if desired

---

## Quick Start Guide

### Daily Usage
```bash
# Activate environment (includes all ROCm settings)
source ~/BestBox/activate.sh

# Verify GPU
python -c "import torch; print(torch.cuda.is_available())"

# Run your code
python your_script.py
```

### Test GPU with Simple Computation
```python
import torch

# Create tensors
x = torch.rand(1000, 1000).cuda()
y = torch.rand(1000, 1000).cuda()

# Matrix multiplication on GPU
z = torch.matmul(x, y)

print(f"✅ GPU computation successful!")
print(f"Result shape: {z.shape}")
print(f"Device: {z.device}")
```

---

## Next Steps (Phase 1 Continuation)

### Priority 1: Install vLLM ⏳
**Goal:** Deploy Qwen3-14B model for inference

**Tasks:**
```bash
# Activate environment
source ~/BestBox/activate.sh

# Install vLLM
pip install vllm

# Test basic import
python -c "import vllm; print(vllm.__version__)"
```

**Expected Time:** 30-60 minutes (includes download)

### Priority 2: Deploy Embeddings Service ⏳
**Goal:** Setup BGE-M3 for text vectorization

**Tasks:**
```bash
# Pull TEI Docker image with ROCm support
docker pull ghcr.io/huggingface/text-embeddings-inference:rocm-1.5

# Run TEI container
docker run --rm -d \
  --device=/dev/kfd \
  --device=/dev/dri \
  --group-add video \
  --group-add render \
  -p 8080:80 \
  --name tei \
  ghcr.io/huggingface/text-embeddings-inference:rocm-1.5 \
  --model-id BAAI/bge-m3 \
  --pooling cls
```

**Expected Time:** 1-2 hours

### Priority 3: Database Infrastructure ⏳
**Goal:** Setup PostgreSQL, Redis, Qdrant

**Tasks:**
- Deploy PostgreSQL 16 in Docker
- Deploy Redis 7 in Docker
- Deploy Qdrant vector database
- Create docker-compose.yml for orchestration

**Expected Time:** 1 day

---

## Performance Benchmarks (To be tested)

### Expected Performance Targets
| Metric | Target | Status |
|--------|--------|--------|
| **LLM Latency (P50)** | <500ms | ⏳ To test |
| **LLM Throughput** | 30-50 tok/s | ⏳ To test |
| **Embedding Latency** | <100ms | ⏳ To test |
| **GPU Utilization** | 70-80% | ⏳ To test |
| **Memory Usage** | <60GB | ⏳ To test |

---

## Resource Allocation Plan

### GPU Memory Budget (96 GB available)
| Component | Estimated Memory | Priority |
|-----------|------------------|----------|
| **Qwen3-14B (FP16)** | ~28 GB | High |
| **BGE-M3 Embeddings** | ~2 GB | High |
| **Vector Cache** | ~8 GB | Medium |
| **System Overhead** | ~8 GB | Required |
| **Reserved for Peaks** | ~50 GB | Buffer |

**Total Planned:** ~46 GB  
**Available Buffer:** ~50 GB (for additional models or larger batches)

---

## Troubleshooting

### GPU Not Detected
```bash
# Check ROCm installation
rocm-smi

# Check device permissions
ls -l /dev/kfd /dev/dri/renderD*

# Verify group membership
groups

# If needed, activate render group
newgrp render
```

### PyTorch Import Errors
```bash
# Reinstall PyTorch
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm7.1

# Verify installation
python -c "import torch; print(torch.__version__)"
```

### Performance Issues
```bash
# Monitor GPU in real-time
watch -n 2 rocm-smi

# Check PyTorch CUDA backend
python -c "import torch; print(torch.version.hip)"

# Verify environment variables
env | grep -E "ROCM|HIP|HSA"
```

---

## References

### Documentation
- **PyTorch ROCm:** https://pytorch.org/get-started/locally/
- **ROCm Documentation:** https://rocm.docs.amd.com/
- **System Design:** `/home/unergy/BestBox/docs/system_design.md`
- **ROCm Deployment Guide:** `/home/unergy/BestBox/docs/rocm_deployment_guide.md`

### Useful Commands
```bash
# Check Python packages
pip list | grep torch

# GPU monitoring
rocm-smi
watch -n 1 rocm-smi --showuse

# Environment check
python -c "import torch; print(torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_properties(0))"
```

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-22 | 1.0 | Initial setup: Python 3.12.3, PyTorch 2.10.0+rocm7.1, GPU verified |

---

**Setup Status:** ✅ Phase 1 Python Environment COMPLETE  
**Next Phase:** vLLM Deployment  
**Timeline:** On Track
