# Multi-GPU Manual Testing Guide

## Quick checks

```bash
# 1) Auto-detect backend
source activate.sh
echo "$BESTBOX_GPU_BACKEND"

# 2) Override backend explicitly
BESTBOX_GPU_BACKEND=cuda source activate.sh
BESTBOX_GPU_BACKEND=rocm source activate.sh
BESTBOX_GPU_BACKEND=cpu source activate.sh

# 3) Start all services
./start-all-services.sh

# 4) Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8081/health
curl http://localhost:8082/health

# 5) Stop all services
./stop-all-services.sh
```

## Priority chain validation

```bash
# Env var wins
mkdir -p .bestbox
echo "gpu_backend=rocm" > .bestbox/config
BESTBOX_GPU_BACKEND=cuda source activate.sh
echo "$BESTBOX_GPU_BACKEND"  # expect cuda

# Config wins when env var is absent
unset BESTBOX_GPU_BACKEND
source activate.sh
echo "$BESTBOX_GPU_BACKEND"  # expect rocm

# Auto-detect used when both unset
rm -f .bestbox/config
source activate.sh
echo "$BESTBOX_GPU_BACKEND"  # expect cuda|rocm|cpu
```

## Automated validation

```bash
chmod +x tests/test_gpu_detection.sh tests/test_docker_compose.sh
./tests/test_gpu_detection.sh
./tests/test_docker_compose.sh
```
