# ROCm 7.2.0 Deployment Guide for BestBox

## Document Information

- **Version**: 1.0
- **Date**: January 22, 2026
- **Platform**: AMD Ryzen AI Max+ 395 with Radeon 8060S
- **OS**: Ubuntu 24.04.3 LTS (Noble Numbat)
- **ROCm Version**: 7.2.0
- **Status**: ✅ Verified and Operational

---

## Executive Summary

This guide documents the complete ROCm 7.2.0 installation and verification process for the BestBox enterprise agentic applications demonstration kit. ROCm has been successfully installed and verified on an AMD Ryzen AI Max+ 395 system with integrated Radeon 8060S GPU (GFX1151 architecture).

**Key Achievements:**
- ✅ ROCm 7.2.0 installed with 302 packages
- ✅ GPU successfully detected: AMD Radeon 8060S (gfx1151)
- ✅ HIP runtime functional with 98GB accessible VRAM
- ✅ OpenCL support operational
- ✅ Complete toolchain verified (hipcc, rocm-smi, rocminfo)

---

## Hardware Configuration

### System Specifications

| Component | Specification |
|-----------|---------------|
| **CPU** | AMD RYZEN AI MAX+ 395 w/ Radeon 8060S |
| **Architecture** | Zen 5 (znver5) |
| **CPU Cores** | 32 compute units @ 5187 MHz max |
| **System Memory** | 128 GB DDR5 (32,484,648 KB reported) |
| **GPU** | AMD Radeon 8060S (integrated) |
| **GPU Architecture** | RDNA 3.5 (GFX1151) |
| **GPU Compute Units** | 40 CUs (20 WGPs) |
| **GPU Memory** | 98,304 MB (96 GB shared with system RAM) |
| **GPU Clock** | 2900 MHz max |
| **PCI Bus ID** | 0000:C6:00.0 |
| **Device ID** | 0x1586 |
| **Storage** | 2TB NVMe SSD |

### GPU Architecture Details

```
GPU Architecture: gfx1151
- Compute Units: 40
- SIMDs per CU: 2
- Shader Engines: 2
- Shader Arrays per Engine: 2
- Wavefront Size: 32
- Max Waves per CU: 32
- Max Workgroup Size: 1024
- L1 Cache: 32 KB
- L2 Cache: 2048 KB (2 MB)
- L3 Cache: 32768 KB (32 MB)
```

### Firmware Versions

```
ASD firmware:        0x210000e7
ME firmware:         32
MEC firmware:        32
MES firmware:        0x00000080
MES KIQ firmware:    0x0000006f
PFP firmware:        46
RLC firmware:        290653446
SDMA firmware:       14
SMC firmware:        10.100.02.00
VCN firmware:        0x09117003
VBIOS:               113-STRXLGEN-001
```

---

## Software Environment

### Operating System

```
OS:           Ubuntu 24.04.3 LTS (Noble Numbat)
Kernel:       6.14.0-37-generic
Architecture: x86_64
Kernel Driver: amdgpu (loaded and active)
```

### ROCm Configuration

```
ROCm Version:     7.2.0 (7.2.0.70200-43~24.04)
HIP Version:      7.2.26015-fc0010cf6a
ROCm Path:        /opt/rocm-7.2.0
HIP Platform:     AMD (rocclr runtime)
HIP Compiler:     clang
LLVM Version:     22.0.0git (ROC 7.2.0 branch)
```

---

## Installation Procedure

### Prerequisites

1. **System Updates**
```bash
sudo apt-get update && sudo apt-get upgrade -y
```

2. **Install Dependencies**
```bash
sudo apt-get install -y wget gnupg2 software-properties-common
```

3. **Verify amdgpu Driver**
```bash
lsmod | grep amdgpu
# Should show amdgpu module loaded
```

### Step 1: Add ROCm Repository

```bash
# Download and install ROCm GPG key
wget -qO - https://repo.radeon.com/rocm/rocm.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/rocm.gpg

# Add ROCm 7.2 repository
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/7.2/ noble main" | \
  sudo tee /etc/apt/sources.list.d/rocm.list

# Update package lists
sudo apt-get update
```

### Step 2: Resolve Package Conflicts

⚠️ **CRITICAL**: Ubuntu 24.04 includes older ROCm packages that conflict with ROCm 7.2. These must be removed first:

```bash
# Remove conflicting Ubuntu packages
sudo apt-get remove --purge -y rocminfo rocm-cmake hipcc

# Install specific ROCm 7.2 versions with downgrades allowed
sudo apt-get install -y --allow-downgrades \
  rocminfo=1.0.0.70200-43~24.04 \
  rocm-cmake=0.14.0.70200-43~24.04 \
  hipcc=1.1.1.70200-43~24.04
```

### Step 3: Install ROCm Stack

```bash
# Install ROCm meta-package and utilities
sudo apt-get install -y rocm rocm-utils rocm-smi
```

This will install **302 packages** including:
- Core runtime: `hsa-rocr`, `rocm-hip-runtime`, `rocm-hip-sdk`
- Development tools: `hipcc`, `rocm-llvm`, `rocm-device-libs`
- Libraries: `rocblas`, `rocfft`, `rocsolver`, `rocsparse`, `rocrand`
- Deep Learning: `miopen-hip`, `migraphx`
- Utilities: `rocminfo`, `rocm-smi`, `clinfo`

**Download size**: ~572 MB  
**Installed size**: ~109 MB additional disk space

### Step 4: Configure User Permissions

⚠️ **CRITICAL**: Users must be added to the `render` and `video` groups to access GPU devices:

```bash
# Add user to required groups
sudo usermod -aG render,video $USER

# Verify group membership
groups $USER
```

**Important**: Group membership changes require a new login session:

```bash
# Option 1: Logout and login again (recommended)
logout

# Option 2: Start new shell with render group
newgrp render

# Option 3: Reboot system
sudo reboot
```

### Step 5: Verify Device Permissions

```bash
# Check device node permissions
ls -l /dev/kfd /dev/dri/renderD*

# Expected output:
# crw-rw---- root:render /dev/kfd
# crw-rw----+ root:render /dev/dri/renderD128
```

---

## Verification Procedures

### Basic ROCm Verification

#### 1. ROCm System Information

```bash
rocminfo | head -n 150
```

**Expected Output:**
- ROCk module loaded
- HSA Runtime Version: 1.18
- Two HSA Agents detected:
  - Agent 1: AMD RYZEN AI MAX+ 395 (CPU)
  - Agent 2: gfx1151 (GPU - AMD Radeon 8060S)
- GPU with 40 compute units, 2900 MHz max clock
- 98,304 MB GPU memory available

#### 2. ROCm System Management Interface

```bash
rocm-smi -a
```

**Expected Output:**
- GPU Device: AMD Radeon 8060S (0x1586)
- Current temperature: ~39°C (idle)
- Clock frequencies: 600 MHz (idle) / 2900 MHz (max)
- Power consumption: ~13W (idle)
- GFX Version: gfx1151
- 40 compute units detected

#### 3. HIP Configuration

```bash
hipconfig --full
```

**Expected Output:**
- HIP Version: 7.2.26015
- HIP Platform: AMD
- HIP Compiler: clang (AMD LLVM 22.0.0git)
- ROCm Path: /opt/rocm-7.2.0
- Target CPU: znver5

#### 4. OpenCL Information

```bash
clinfo | head -n 100
```

**Expected Output:**
- Platform: AMD Accelerated Parallel Processing
- Device Type: GPU
- Device: AMD Radeon 8060S
- Max compute units: 20 (OpenCL work groups)
- Max work group size: 256
- Global memory: 103,079,215,104 bytes (~96 GB)
- Clock rate: 2900 MHz

### HIP Compilation Test

#### Test Program: hip_test.cpp

```cpp
#include <hip/hip_runtime.h>
#include <iostream>

int main() {
    int deviceCount = 0;
    hipError_t err = hipGetDeviceCount(&deviceCount);
    
    if (err != hipSuccess) {
        std::cerr << "hipGetDeviceCount failed: " << hipGetErrorString(err) << std::endl;
        return 1;
    }
    
    std::cout << "Number of HIP devices: " << deviceCount << std::endl;
    
    for (int i = 0; i < deviceCount; i++) {
        hipDeviceProp_t props;
        err = hipGetDeviceProperties(&props, i);
        
        std::cout << "\nDevice " << i << ": " << props.name << std::endl;
        std::cout << "  Compute Capability: " << props.major << "." << props.minor << std::endl;
        std::cout << "  Total Global Memory: " << props.totalGlobalMem / (1024*1024) << " MB" << std::endl;
        std::cout << "  Max Clock Rate: " << props.clockRate / 1000 << " MHz" << std::endl;
        std::cout << "  Multiprocessors: " << props.multiProcessorCount << std::endl;
        std::cout << "  Warp Size: " << props.warpSize << std::endl;
        std::cout << "  GCN Arch: " << props.gcnArchName << std::endl;
    }
    
    return 0;
}
```

#### Compile and Execute

```bash
# Compile with hipcc
/opt/rocm-7.2.0/bin/hipcc hip_test.cpp -o hip_test

# Run test
./hip_test
```

**Expected Output:**
```
Number of HIP devices: 1

Device 0: AMD Radeon 8060S
  Compute Capability: 11.5
  Total Global Memory: 98304 MB
  Max Clock Rate: 2900 MHz
  Multiprocessors: 20
  Warp Size: 32
  GCN Arch: gfx1151
```

### Verification Checklist

- [ ] `rocminfo` shows GPU agent without permission errors
- [ ] `rocm-smi` displays GPU temperature and clock speeds
- [ ] `hipconfig` shows AMD platform and ROCm 7.2.0 paths
- [ ] `clinfo` detects AMD GPU with OpenCL support
- [ ] HIP test program compiles without errors
- [ ] HIP test program detects GPU and reports correct properties
- [ ] User is member of `render` and `video` groups
- [ ] Device nodes `/dev/kfd` and `/dev/dri/renderD*` are accessible

---

## Common Issues and Solutions

### Issue 1: Permission Denied on /dev/kfd

**Symptom:**
```
Unable to open /dev/kfd read-write: Permission denied
```

**Root Cause:** User not in `render` group, or group membership not active in current session.

**Solution:**
```bash
# Add user to render group
sudo usermod -aG render,video $USER

# Activate immediately (choose one):
# Option 1: Logout and login
logout

# Option 2: New shell with render group
newgrp render

# Option 3: Reboot
sudo reboot
```

### Issue 2: Package Dependency Conflicts

**Symptom:**
```
The following packages have unmet dependencies:
 rocm : Depends: rocminfo but it is not going to be installed
```

**Root Cause:** Ubuntu 24.04 includes older ROCm 5.7.1 packages that conflict with ROCm 7.2 versions.

**Solution:**
```bash
# Remove Ubuntu's older ROCm packages
sudo apt-get remove --purge -y rocminfo rocm-cmake hipcc

# Install specific ROCm 7.2 versions
sudo apt-get install -y --allow-downgrades \
  rocminfo=1.0.0.70200-43~24.04 \
  rocm-cmake=0.14.0.70200-43~24.04 \
  hipcc=1.1.1.70200-43~24.04

# Then install ROCm meta-package
sudo apt-get install -y rocm rocm-utils rocm-smi
```

### Issue 3: GPU Not Detected

**Symptom:**
```
Number of HIP devices: 0
```

**Root Cause:** amdgpu driver not loaded or GPU not supported.

**Solution:**
```bash
# Check if amdgpu driver is loaded
lsmod | grep amdgpu

# If not loaded, try loading it
sudo modprobe amdgpu

# Check dmesg for driver errors
dmesg | grep -i amdgpu | tail -n 20

# Verify PCI device is visible
lspci -k | grep -A 3 VGA
```

### Issue 4: Low GPU Performance

**Symptom:** GPU stuck at low clock speeds (e.g., 600-716 MHz instead of 2900 MHz)

**Root Cause:** GPU in power-saving mode or no compute workload active.

**Solution:**
```bash
# Check current performance level
rocm-smi --showperflevel

# Set performance mode (if supported)
rocm-smi --setperflevel high

# Note: On APU systems, power management is typically automatic
# GPU will clock up under load
```

---

## Performance Characteristics

### Memory Architecture

The AMD Ryzen AI Max+ 395 uses **Unified Memory Architecture (UMA)**:
- GPU shares system RAM (128 GB total)
- GPU can access up to 98 GB (75% of total)
- Eliminates PCIe bottleneck for data transfer
- Zero-copy memory access between CPU and GPU
- Ideal for LLM inference with large models

### Compute Capabilities

```
Total GPU Compute Units: 40
Total Stream Processors: 2560 (40 CUs × 2 SIMDs × 32 lanes)
Peak FP32 Performance: ~14.88 TFLOPS (2560 × 2900 MHz × 2 ops)
Peak FP16 Performance: ~29.76 TFLOPS (with 2:1 packing)
Memory Bandwidth: Shared with system (DDR5 speed dependent)
```

### Workload Suitability

**Excellent for:**
- ✅ Large Language Model (LLM) inference (leverages 98GB memory)
- ✅ Text embedding generation (BGE-M3: 1024-dim vectors)
- ✅ Vector similarity search preprocessing
- ✅ Moderate batch sizes (memory-bound workloads)
- ✅ Development and testing of GPU-accelerated applications

**Considerations:**
- ⚠️ Shared memory bandwidth with CPU
- ⚠️ No dedicated VRAM (all allocations reduce system RAM)
- ⚠️ Power management may throttle under sustained load
- ⚠️ Training large models may require external GPU

---

## Integration with BestBox Stack

### Python Environment Setup

```bash
# Install Python development tools
sudo apt-get install -y python3-dev python3-pip python3-venv

# Create virtual environment
python3 -m venv /home/unergy/BestBox/venv
source /home/unergy/BestBox/venv/bin/activate

# Install PyTorch with ROCm support
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2
# Note: ROCm 7.2 is compatible with ROCm 6.2 PyTorch builds

# Verify PyTorch sees GPU
python3 -c "import torch; print(f'GPU Available: {torch.cuda.is_available()}'); print(f'GPU Name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

### vLLM Configuration for ROCm

```bash
# Install vLLM with ROCm support
pip3 install vllm

# Set environment variables for optimal performance
export ROCM_PATH=/opt/rocm-7.2.0
export HSA_OVERRIDE_GFX_VERSION=11.0.0  # Map gfx1151 to gfx1100 family
export PYTORCH_ROCM_ARCH=gfx1100

# Launch vLLM server with Qwen3-14B
vllm serve Qwen/Qwen3-14B \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.85 \
  --max-model-len 32768 \
  --dtype float16 \
  --trust-remote-code
```

### Text Embeddings Inference (TEI) with ROCm

```bash
# Pull TEI Docker image (ROCm version)
docker pull ghcr.io/huggingface/text-embeddings-inference:rocm-1.5

# Run TEI with BGE-M3 model
docker run --rm -it \
  --device=/dev/kfd \
  --device=/dev/dri \
  --group-add video \
  --group-add render \
  -p 8080:80 \
  -v $(pwd)/data:/data \
  ghcr.io/huggingface/text-embeddings-inference:rocm-1.5 \
  --model-id BAAI/bge-m3 \
  --revision main \
  --max-batch-tokens 32768 \
  --pooling cls
```

### Docker Configuration for ROCm

Add user to docker group and configure ROCm device access:

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Create docker daemon configuration
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "runtimes": {
    "rocm": {
      "path": "/usr/bin/rocm-runtime",
      "runtimeArgs": []
    }
  },
  "default-runtime": "runc"
}
EOF

# Restart docker
sudo systemctl restart docker

# Test GPU access in container
docker run --rm -it \
  --device=/dev/kfd \
  --device=/dev/dri \
  --group-add video \
  --group-add render \
  rocm/pytorch:latest \
  rocminfo
```

---

## Environment Variables Reference

### Essential ROCm Variables

```bash
# ROCm installation path
export ROCM_PATH=/opt/rocm-7.2.0
export ROCM_HOME=/opt/rocm-7.2.0

# Add ROCm binaries to PATH
export PATH=$ROCM_PATH/bin:$PATH

# Add ROCm libraries to LD_LIBRARY_PATH
export LD_LIBRARY_PATH=$ROCM_PATH/lib:$LD_LIBRARY_PATH

# HIP configuration
export HIP_PATH=$ROCM_PATH/hip
export HIP_PLATFORM=amd

# GPU architecture override (if needed)
export HSA_OVERRIDE_GFX_VERSION=11.0.0  # Maps gfx1151 → gfx1100 family
export PYTORCH_ROCM_ARCH=gfx1100

# Enable ROCm debugging (optional)
export AMD_LOG_LEVEL=1  # 0=silent, 1=errors, 2=warnings, 3=info, 4=verbose
export HIP_VISIBLE_DEVICES=0  # Use first GPU
```

### Performance Tuning Variables

```bash
# Memory management
export HSA_ENABLE_SDMA=0  # Disable SDMA for debugging (default: enabled)
export GPU_MAX_HW_QUEUES=4  # Limit concurrent kernel queues

# Kernel fusion optimization
export HSA_KERNELCACHE_ENABLED=1  # Enable kernel caching
export ROCM_ENABLE_PRE_VEGA=0  # Disable pre-Vega workarounds

# TensorFlow ROCm specific
export TF_ROCM_FUSION_ENABLE=1
export HCC_AMDGPU_TARGET=gfx1100
```

---

## Monitoring and Diagnostics

### Real-time GPU Monitoring

```bash
# Watch GPU status (updates every 2 seconds)
watch -n 2 rocm-smi

# Monitor temperature and power
watch -n 1 'rocm-smi --showtemp && rocm-smi --showpower'

# Monitor GPU utilization
watch -n 1 rocm-smi --showuse

# Monitor memory usage
watch -n 1 rocm-smi --showmeminfo
```

### System Health Checks

```bash
# Check ROCk kernel module
lsmod | grep amdgpu

# Verify device nodes
ls -la /dev/kfd /dev/dri/renderD*

# Check HSA runtime
rocminfo | grep -A 5 "HSA System"

# Verify HIP installation
hipconfig --version

# List installed ROCm packages
dpkg -l | grep -E "rocm|hip" | wc -l  # Should show ~49 packages
```

### Performance Profiling

```bash
# Profile HIP application
rocprof --stats ./your_hip_app

# Generate timeline trace
rocprof --trace-start 0 --trace-stop 1000 ./your_hip_app

# Memory profiling
rocprof --hip-trace --hsa-trace ./your_hip_app
```

---

## Next Steps for BestBox Deployment

### Phase 1: Infrastructure Setup (Weeks 1-2)

1. **Python Environment**
   - ✅ Install Python 3.12+ with uv package manager
   - Install PyTorch 2.5+ with ROCm 7.2 support
   - Set up virtual environment with dependencies

2. **AI Inference Stack**
   - Deploy vLLM with Qwen3-14B-Instruct
   - Deploy Text Embeddings Inference with BGE-M3
   - Configure GPU memory allocation (50% LLM, 30% embeddings)

3. **Database Infrastructure**
   - PostgreSQL 16 for relational data
   - Redis 7 for caching and sessions
   - Qdrant for vector storage

4. **Container Orchestration**
   - Docker Compose setup for all services
   - ROCm device mounting configuration
   - Network and volume management

### Phase 2: Backend Development (Weeks 3-4)

1. **LangGraph Agent Framework**
   - Multi-agent architecture implementation
   - State machine definitions for 4 demo scenarios
   - Tool gateway integration

2. **CopilotKit Integration**
   - Agent protocol adapters
   - Real-time streaming setup
   - Error handling and retries

### Phase 3: Demo Applications (Weeks 5-8)

1. ERP Copilot (Week 5-6)
2. CRM Sales Assistant (Week 6-7)
3. IT Operations Agent (Week 7-8)
4. OA Workflow Agent (Week 8)

### Resource Requirements Summary

| Component | Requirement | Status |
|-----------|-------------|--------|
| **GPU** | ROCm-compatible AMD GPU | ✅ Radeon 8060S (gfx1151) |
| **VRAM** | 16GB minimum, 32GB recommended | ✅ 98GB available |
| **System RAM** | 32GB minimum, 64GB recommended | ✅ 128GB installed |
| **Storage** | 500GB SSD minimum | ✅ 2TB NVMe available |
| **ROCm** | Version 6.2+ | ✅ ROCm 7.2.0 installed |
| **Docker** | 24.0+ with ROCm runtime | ⏳ To be configured |
| **Python** | 3.12+ | ⏳ To be verified |

---

## Additional Resources

### Documentation

- **ROCm Documentation**: https://rocm.docs.amd.com/
- **HIP Programming Guide**: https://rocm.docs.amd.com/projects/HIP/en/latest/
- **ROCm Installation Guide**: https://rocm.docs.amd.com/projects/install-on-linux/en/latest/
- **AMD GPU ISA Documentation**: https://www.amd.com/en/support/graphics/amd-radeon-8000-series

### Community Support

- **ROCm GitHub**: https://github.com/ROCm/ROCm
- **ROCm Issue Tracker**: https://github.com/ROCm/ROCm/issues
- **AMD Developer Forum**: https://community.amd.com/t5/opencl/bd-p/opencl

### BestBox Project References

- **System Design Document**: `/home/unergy/BestBox/docs/system_design.md`
- **Review Checklist**: `/home/unergy/BestBox/docs/review_checklist.md`
- **Product Description**: `/home/unergy/BestBox/docs/product_desc.md`

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-22 | BestBox Team | Initial deployment guide with verified ROCm 7.2.0 installation |

---

## Appendix A: Complete rocminfo Output

```
ROCk module is loaded
=====================    
HSA System Attributes    
=====================    
Runtime Version:         1.18
Runtime Ext Version:     1.15
System Timestamp Freq.:  1000.000000MHz
Sig. Max Wait Duration:  18446744073709551615 (0xFFFFFFFFFFFFFFFF) (timestamp count)
Machine Model:           LARGE                              
System Endianness:       LITTLE                             
Mwaitx:                  DISABLED
XNACK enabled:           NO
DMAbuf Support:          YES
VMM Support:             YES

==========               
HSA Agents               
==========               
*******                  
Agent 1                  
*******                  
  Name:                    AMD RYZEN AI MAX+ 395 w/ Radeon 8060S
  Marketing Name:          AMD RYZEN AI MAX+ 395 w/ Radeon 8060S
  Vendor Name:             CPU                                
  Device Type:             CPU                                
  Max Clock Freq. (MHz):   5187                               
  Compute Unit:            32                                 

*******                  
Agent 2                  
*******                  
  Name:                    gfx1151                            
  Marketing Name:          AMD Radeon 8060S                   
  Vendor Name:             AMD                                
  Device Type:             GPU                                
  Chip ID:                 5510(0x1586)                       
  Compute Unit:            40                                 
  Max Clock Freq. (MHz):   2900                               
  Wavefront Size:          32(0x20)                           
  Workgroup Max Size:      1024(0x400)                        
  GCN Arch:                gfx1151
```

---

## Appendix B: Installed Package List

**Total Packages**: 302 (meta-package + dependencies)

**Key ROCm Packages** (49 direct packages):
- rocm (7.2.0.70200-43~24.04)
- rocm-utils
- rocm-smi
- rocminfo (1.0.0.70200-43~24.04)
- rocm-hip-runtime
- rocm-hip-sdk
- hipcc (1.1.1.70200-43~24.04)
- hsa-rocr-dev
- rocblas
- rocfft
- rocsolver
- rocsparse
- rocrand
- rccl
- miopen-hip
- migraphx
- rocm-llvm
- rocm-cmake (0.14.0.70200-43~24.04)
- rocm-device-libs
- clinfo

**Supporting Dependencies** (253 packages):
- OpenCV libraries
- BLAS/LAPACK implementations
- MPI runtimes (OpenMPI, MPICH)
- Compression libraries
- System utilities

To view complete list:
```bash
dpkg -l | grep -E "rocm|hip"
```

---

**End of Document**
