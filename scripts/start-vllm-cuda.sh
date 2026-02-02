#!/usr/bin/env bash
# BestBox vLLM Server Startup Script (NVIDIA CUDA)
# Starts vLLM on port 8001 using official CUDA Docker image
# Requirements: Docker, NVIDIA GPU with CUDA support

set -e

# Configuration (override via environment variables)
MODEL="${LLM_MODEL:-Qwen/Qwen3-4B-Instruct-2507}"
MODEL_PATH="${LLM_MODEL_PATH:-}"
PORT="${LLM_PORT:-8001}"
CUDA_DEVICE="${LLM_CUDA_DEVICE:-1}"
CONTAINER_NAME="vllm-server-cuda"
IMAGE="vllm/vllm-openai:v0.11.0"
LOG_FILE="vllm-cuda.log"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting vLLM with NVIDIA CUDA Backend${NC}"
echo "=============================================="
echo -e "Model: ${GREEN}${MODEL}${NC}"
echo -e "Image: ${GREEN}${IMAGE}${NC}"
echo -e "Port: ${GREEN}${PORT}${NC}"
echo -e "CUDA Device: ${GREEN}${CUDA_DEVICE}${NC}"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
    exit 1
fi

# Check if NVIDIA Docker support is available
if ! docker ps --format 'table {{.Names}}' > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker daemon is not running${NC}"
    exit 1
fi

# Check if container already running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}⚠️  Container '${CONTAINER_NAME}' already running${NC}"
    echo "Stop it with: docker stop ${CONTAINER_NAME}"
    exit 1
fi

# Remove old container if exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}🧹 Removing old container...${NC}"
    docker rm -f ${CONTAINER_NAME} > /dev/null
fi

echo -e "${BLUE}📦 Starting vLLM container...${NC}"
echo ""

# Check if Docker image exists locally
echo -e "${BLUE}📦 Checking Docker image locally...${NC}"
if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE}$"; then
    echo -e "${GREEN}✅ Image found locally${NC}"
else
    echo -e "${YELLOW}⚠️  Image not found locally, pulling from registry...${NC}"
    echo -e "${BLUE}This may take several minutes (several GB)...${NC}"
    echo ""
    
    # Pull with visible progress
    if ! docker pull "${IMAGE}"; then
        echo -e "${RED}❌ Failed to pull image ${IMAGE}${NC}"
        echo -e "${BLUE}Troubleshooting:${NC}"
        echo "   1. Check internet connection"
        echo "   2. Check Docker is running: docker ps"
        echo "   3. Try manually: docker pull ${IMAGE}"
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}✅ Image pulled successfully${NC}"
fi

echo ""
echo -e "${BLUE}📦 Starting vLLM container...${NC}"
echo ""

# Build the docker run command
DOCKER_CMD="docker run -d \
  --name ${CONTAINER_NAME} \
  --runtime nvidia \
  --gpus \"device=${CUDA_DEVICE}\" \
  -p ${PORT}:8000 \
  -e VLLM_USE_V1=1 \
  -v \$HOME/.cache/huggingface:/root/.cache/huggingface \
  -e HF_HUB_OFFLINE=1 \
  ${IMAGE}"

# Add model path if provided, otherwise use model name
if [ -n "${MODEL_PATH}" ]; then
    DOCKER_CMD="${DOCKER_CMD} \
  --model ${MODEL_PATH}"
else
    DOCKER_CMD="${DOCKER_CMD} \
  --model ${MODEL}"
fi

# Add vLLM optimizations for CUDA
DOCKER_CMD="${DOCKER_CMD} \
  --dtype float16 \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --max-num-batched-tokens 8192 \
  --trust-remote-code \
  --disable-log-requests \
  --enable-auto-tool-choice \
  --tool-call-parser hermes"

# Execute docker command with error output visible
if eval "${DOCKER_CMD}"; then
    echo -e "${GREEN}✅ Container started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start container${NC}"
    echo -e "${BLUE}Troubleshooting:${NC}"
    echo "   1. Check NVIDIA runtime: docker run --rm --runtime nvidia --gpus all nvidia-smi"
    echo "   2. Check Docker logs: docker logs ${CONTAINER_NAME}"
    echo "   3. Verify GPU: nvidia-smi"
    exit 1
fi

echo ""
echo -e "${BLUE}📊 Monitoring startup (this may take a while if model needs to download)...${NC}"
sleep 2
echo ""

# Wait for server to be ready (max 180 seconds for large model downloads)
MAX_ATTEMPTS=180
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ vLLM server is ready!${NC}"
        echo ""
        echo -e "${BLUE}📋 Service Information:${NC}"
        echo -e "   API Endpoint: ${GREEN}http://localhost:${PORT}/v1/chat/completions${NC}"
        echo -e "   Health Check: ${GREEN}http://localhost:${PORT}/health${NC}"
        echo -e "   Container:    ${GREEN}${CONTAINER_NAME}${NC}"
        echo ""
        echo -e "${BLUE}📝 Quick Commands:${NC}"
        echo "   View logs:      docker logs -f ${CONTAINER_NAME}"
        echo "   Stop server:    docker stop ${CONTAINER_NAME}"
        echo "   Remove image:   docker rm ${CONTAINER_NAME}"
        echo ""
        exit 0
    fi
    ATTEMPT=$((ATTEMPT + 1))
    
    # Show progress every 15 attempts (every 15 seconds)
    if [ $((ATTEMPT % 15)) -eq 0 ]; then
        ELAPSED=$((ATTEMPT))
        echo "⏳ Waiting for model to load... ($ELAPSED/180 seconds)"
        
        # Show container status for debugging
        CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' ${CONTAINER_NAME} 2>/dev/null || echo "unknown")
        if [ "$CONTAINER_STATUS" != "running" ]; then
            echo -e "${YELLOW}⚠️  Container status: ${CONTAINER_STATUS}${NC}"
            echo "   Check logs: docker logs ${CONTAINER_NAME}"
        fi
    fi
    
    sleep 1
done

echo -e "${RED}❌ Server failed to start within timeout (180s)${NC}"
echo ""
echo -e "${BLUE}📋 Troubleshooting:${NC}"
echo "   1. Check container is still running: docker ps | grep ${CONTAINER_NAME}"
echo "   2. Check container logs: docker logs ${CONTAINER_NAME}"
echo "   3. Check NVIDIA runtime: docker run --rm --runtime nvidia --gpus all nvidia-smi"
echo "   4. Check model download: docker exec ${CONTAINER_NAME} ls -lh /root/.cache/huggingface"
echo ""
echo -e "${BLUE}Last 30 log lines:${NC}"
docker logs --tail=30 ${CONTAINER_NAME} 2>/dev/null || echo "   (No logs available)"
exit 1
