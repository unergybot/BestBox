## Installation for ROCm Ryzen APU

## Prerequisites

refer to https://hakedev.substack.com/p/strix-halo-rocm-71-ubuntu-2404

```bash
# Verify distro codename and running kernel (Ubuntu 24.04 = 'noble')
lsb_release -a

# No LSB modules are available.
# Distributor ID:	Ubuntu
# Description:	Ubuntu 24.04.1 LTS
# Release:	24.04
# Codename:	noble


lsb_release -cs   # should print 'noble' for Ubuntu 24.04
# noble

uname -r
# 6.17.0-14-generic

# (Optional) Check for OEM kernel packages if AMD/ROCm recommends one
sudo apt update
apt search linux-oem-24.04
apt policy linux-oem-24.04c   # check this package if AMD/ROCm docs recommend it
# Install the recommended OEM kernel only if needed
sudo apt install linux-oem-24.04c
# sudo reboot now

# After kernel change (or if staying on current kernel), install matching headers/modules
sudo apt install -y "linux-headers-$(uname -r)" "linux-modules-extra-$(uname -r)"

# Download and install AMD installer
wget https://repo.radeon.com/amdgpu-install/7.2/ubuntu/noble/amdgpu-install_7.2.70100-1_all.deb
# Installing a local .deb may show: "Download is performed unsandboxed as root..." — it's harmless.
# To avoid the warning, move it to /tmp first: sudo mv amdgpu-install_*.deb /tmp && sudo apt install /tmp/amdgpu-install_*.deb
sudo apt install ./amdgpu-install_7.2.70100-1_all.deb

# Install ROCm userspace + kernel support and add user to video/render groups.
# If you frequently change kernels, prefer DKMS mode to avoid breakage after upgrades.
# Option A (recommended for frequent kernel updates):
sudo amdgpu-install -y --usecase=rocm,dkms

# Option B (userspace-only, no DKMS):
sudo amdgpu-install -y --usecase=rocm --no-dkms
sudo usermod -a -G render,video $LOGNAME

# Reboot and verify devices/drivers
sudo reboot now


# After reboot, check nodes and driver logs
ls -l /dev/kfd /dev/dri || true
dmesg | grep -i amdgpu || true
# If modules fail to load, check Secure Boot status (it can block unsigned kernel modules)
sudo mokutil --sb-state
```

### Memory
```bash
sudo apt install pipx
pipx ensurepath
pipx install amd-debug-tools


```

### Post-kernel-update recovery checklist (6.14+/OEM)

Run these checks first when ROCm/vLLM worked previously but fails after a kernel update:

```bash
# 1) Confirm current kernel and headers match
uname -r
dpkg -l | grep "linux-headers-$(uname -r)" || sudo apt install -y "linux-headers-$(uname -r)"

# 2) Verify device nodes and group access
ls -l /dev/kfd /dev/dri
groups

# 3) If using DKMS, rebuild modules for current kernel
sudo dkms status || true
sudo amdgpu-install -y --usecase=rocm,dkms
sudo reboot now

# 4) If Secure Boot is enabled and DKMS modules fail, disable Secure Boot
sudo mokutil --sb-state
```

Quick ROCm sanity check (host):

```bash
/opt/rocm/bin/rocminfo | head -n 40
python3 -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

* docker
* pytorch 2.9
* rocm 7.2 (7.1.1 has engine init failures on gfx1151, see ROCm/ROCm#5865)
* Triton 3.5.1

Options:
- PyTorch via PIP installation
- Docker installation

## Docker Installation

```bash
# Docker
sudo apt install docker.io

sudo docker pull rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1

docker build -t rocm-vllm:latest .

sudo docker run -it \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --device=/dev/kfd \
  --device=/dev/dri \
  --group-add video \
  --group-add render \
  --ipc=host \
  --shm-size 8G \
  rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1

# Verify pytorch installation

python3 -c 'import torch' 2> /dev/null && echo 'Success' || echo 'Failure'
#Success

python3 -c 'import torch; print(torch.cuda.is_available())'
# True

python3 -c "import torch; print(f'device name [0]:', torch.cuda.get_device_name(0))"
# device name [0]: <Supported AMD GPU>

python3 -m torch.utils.collect_env
# list the versions of pytorch, rocm, os, cuda, gpu model, hip, MIOpen runtime version etc.

```

## VLLM

```bash
# Enable FlashAttention Triton AMD support (required when building FlashAttention/Triton on ROCm)
export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"

# Flash-Attention (ROCm build)
git clone https://github.com/ROCm/flash-attention.git
cd flash-attention && git checkout v2.7.3-cktile && python setup.py install

# vllm (ROCm-compatible branch/tag)
git clone https://github.com/vllm-project/vllm.git
cd vllm
pip install --upgrade packaging --ignore-installed
pip install -r requirements/rocm.txt
export PYTORCH_ROCM_ARCH="gfx1151"
python3 setup.py install
pip install amdsmi==7.0.2

# Serve example (if model is available under Hugging Face cache or mounted /models)
# (adjust path or model id as needed)
vllm serve /models/Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --served-model-name qwen3-30b --dtype auto --max-model-len 32768 \
  --gpu-memory-utilization 0.8 --port 8000 --async-scheduling \
  --dtype float16 --max-model-len 2048 --max-num-seqs 16 --max-num-batched-tokens 8192 \
  --enforce-eager
```

### Dockerfile (vllm-ready image)

Below is a minimal Dockerfile that builds on the ROCm PyTorch image and installs Flash-Attention, Triton (if desired), and vllm. This produces a self-contained image you can run and mount your local Hugging Face cache so models are used from `~/.cache/huggingface` on the host.

```dockerfile
FROM rocm/pytorch:rocm7.2_ubuntu24.04_py3.12_pytorch_release_2.9.1

# Install basics
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential cmake python3-dev python3-pip python3-venv curl && \
    rm -rf /var/lib/apt/lists/*

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTORCH_ROCM_ARCH=gfx1151
ENV FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
ENV HSA_OVERRIDE_GFX_VERSION=11.5.1

# Install Python deps
RUN pip install --upgrade pip setuptools wheel

# Build and install Flash-Attention (ROCm)
RUN git clone https://github.com/ROCm/flash-attention.git /opt/flash-attention && \
    cd /opt/flash-attention && git checkout v2.7.3-cktile && python setup.py install

# Install Triton (optional - may take a long time)
# (Uncomment / add triton build steps here if you want to compile Triton inside the image.)

# Install vllm
RUN git clone https://github.com/vllm-project/vllm.git /opt/vllm && \
    cd /opt/vllm && pip install -r requirements/rocm.txt && python3 setup.py install

# ROCm device detection for vLLM
RUN pip install amdsmi==7.0.2

# Useful tools
RUN pip install huggingface-hub amdsmi==7.0.2

WORKDIR /workspace
CMD ["/bin/bash"]
```

### Build & Run (mount Hugging Face cache)

- Build image (long):

```bash
docker build -t rocm-vllm:latest .
```

- Run container using your host Hugging Face cache (~/.cache/huggingface):

```bash
docker run -it --rm \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --device=/dev/kfd --device=/dev/dri --group-add video --group-add render \
  --ipc=host --shm-size=8G \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface:rw \
  -v /path/to/your/models:/models:rw \
  -e HF_HOME=/root/.cache/huggingface \
  -e TRANSFORMERS_CACHE=/root/.cache/huggingface/hub \
  -e FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE \
  -e PYTORCH_ROCM_ARCH=gfx1151 \
  -p 8000:8000 \
  rocm-vllm:latest
```

- Serve the downloaded modelscope qwen3-30b model:

```bash
docker run -it --rm \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --device=/dev/kfd --device=/dev/dri --group-add video --group-add render \
  --ipc=host --shm-size=8G \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface:rw \
  -v /path/to/your/models:/models:rw \
  -e HF_HOME=/root/.cache/huggingface \
  -e TRANSFORMERS_CACHE=/root/.cache/huggingface/hub \
  -e FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE \
  -e PYTORCH_ROCM_ARCH=gfx1151 \
  -p 8000:8000 \
  rocm-vllm:latest \
  vllm serve /models/Qwen/Qwen3-30B-A3B-Instruct-2507 \
    --served-model-name qwen3-30b --dtype auto --max-model-len 32768 \
    --gpu-memory-utilization 0.8 --port 8000 --async-scheduling \
    --dtype float16 --max-model-len 2048 --max-num-seqs 16 --max-num-batched-tokens 8192 \
    --enforce-eager
```

### Serving Qwen3 from ModelScope cache (your current path)

If your model is already on the host at:

`~/.cache/modelscope/hub/models/Qwen/Qwen3-30B-A3B-Instruct-2507`

Mount the ModelScope models directory and serve from `/models`:

```bash
docker run -it --rm \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --device=/dev/kfd --device=/dev/dri --group-add video --group-add render \
  --ipc=host --shm-size=16G \
  -v $HOME/.cache/modelscope/hub/models:/models:rw \
  -e FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE \
  -e PYTORCH_ROCM_ARCH=gfx1151 \
  -p 8000:8000 \
  rocm-vllm:latest \
  vllm serve /models/Qwen/Qwen3-30B-A3B-Instruct-2507 \
    --served-model-name qwen3-30b \
    --dtype float16 \
    --port 8000 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 2048 \
    --max-num-seqs 8 \
    --max-num-batched-tokens 4096 \
    --enforce-eager
```

Tuning quick notes:
- **`--enforce-eager` is required on gfx1151** — HIP Graphs are unstable on Strix Halo (vllm#32180). This adds some CPU overhead but prevents driver timeouts and engine crashes.
- If you see GPU hangs/timeouts on an APU driving the desktop, drop `--max-num-seqs` (e.g. 2) and `--max-num-batched-tokens` (e.g. 1024).
- If throughput is low but stable, increase `--max-num-seqs` and `--max-num-batched-tokens` gradually until you hit memory pressure or latency spikes.
- Keep `--served-model-name qwen3-30b` aligned with your benchmark/client `model` field.

Notes:
- Mounting `$HOME/.cache/huggingface` into `/root/.cache/huggingface` inside the container makes all Hugging Face downloads (models/tokenizers) available to the container without duplicating files.
- If you prefer the models directory mapped to `/models`, add `-v /path/to/your/models:/models` to the `docker run` command and call `vllm serve /models/<model-dir> ...`.
- To pre-download models on the host (so the container can immediately use them), use `huggingface-cli` or a small Python snippet:

```bash
python - <<'PY'
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id="Qwen/Qwen3-30B-A3B-Instruct-2507", filename="pytorch_model.bin")
PY
```

---

## modelscope
```bash
pip install modelscope
modelscope download --model Qwen/Qwen3-30B-A3B-Instruct-2507


# add user to docker group
sudo usermod -aG docker $USER

# apply group membership immediately in current shell (or log out/in)
newgrp docker

# verify
docker images
docker run --rm hello-world

```


## Others
* VS Code
* Chrome browser
* git
* gh cli



```bash
sudo add-apt-repository ppa:git-core/ppa
sudo apt update
sudo apt install git

sudo apt install python-is-python3
sudo apt install python3-pip
sudo apt install python3-venv


python3 -m pip install --upgrade pip
pip install huggingface-hub


### Troubleshooting — modelscope: ModuleNotFoundError: No module named 'pkg_resources' (Python 3.12) ⚠️

If you see an error like `ModuleNotFoundError: No module named 'pkg_resources'` when running `modelscope` inside a Python 3.12 virtualenv, a quick workaround is to expose a working `pkg_resources` implementation from pip's vendored copy. Run (inside your project root):

```bash
mkdir -p .venv/lib/python3.12/site-packages/pkg_resources
cat > .venv/lib/python3.12/site-packages/pkg_resources/__init__.py <<'PY'
# pkg_resources shim (uses pip's vendored implementation when available)
try:
    from pip._vendor.pkg_resources import *
except Exception:
    try:
        from setuptools._vendor.pkg_resources import *
    except Exception as e:
        raise ImportError("No usable pkg_resources found (pip._vendor.pkg_resources and setuptools._vendor.pkg_resources failed)") from e
PY

# Verify it worked
.venv/bin/python -c "import pkg_resources; print(pkg_resources.__file__)"
```

Note: Newer `setuptools` releases may not expose a top-level `pkg_resources`, and older `pkg_resources` implementations (from old `setuptools`) can rely on internals removed in Python 3.12. The shim above is a safe, small workaround to get `modelscope` working; removing it is safe later once upstream fixes are available or when using Python 3.11.

```
---
```bash
pipx install amd-debug-tools
amd-ttm
amd-bios
amd-pstate
amd-s2idle
```

On an APU, that “VRAM” is typically a UMA carveout from system RAM, so 128 GB installed − 96 GB carved out ≈ 32 GB left for Linux, exactly what you see in meminfo and amd-ttm.

Fix (BIOS/UEFI)

Reboot into BIOS/UEFI setup.
Find the integrated graphics memory setting (common names):
“UMA Frame Buffer Size”
“iGPU Memory” / “Integrated Graphics Share Memory”
“DVMT Pre-Allocated” (some OEMs still use this wording)
Set it to minimum / Auto / 512MB (0.5GB).
This matches AMD’s own guidance in the doc you linked: “set the minimum dedicated VRAM in the BIOS (0.5GB)”.
Save and reboot.

Validate after reboot
Run:

free -h → should show around 125–126 GiB
amd-smi → VRAM total should drop a lot (not 96 GB)
amd-ttm → “Total system memory” should become ~128 GB, and the default TTM limit will increase (it uses ~half of system RAM by default)
Then set the ROCm shared-memory limit you actually want
Example (100 GB shared pool):

amd-ttm --set 100
reboot
If you tell me your motherboard/OEM model (or paste sudo dmidecode -t 0 | head -n 30), I can point you to the exact BIOS menu path for that vendor.