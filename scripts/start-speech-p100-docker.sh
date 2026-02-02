#!/bin/bash
# Start Speech Service (FunASR + MeloTTS) on P100 via Docker
#
# This script builds and runs the speech service container on the P100 GPU.
# The container uses PyTorch 2.1.2 + CUDA 11.8 which is compatible with P100 (SM60).
#
# Usage:
#   ./scripts/start-speech-p100-docker.sh [build|run|stop|logs]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

IMAGE_NAME="bestbox-speech-p100"
CONTAINER_NAME="bestbox-speech-p100"
PORT="${SPEECH_PORT:-8765}"

# P100 is typically GPU 0 (adjust if different in your setup)
GPU_ID="${SPEECH_GPU_ID:-0}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

build() {
    echo -e "${GREEN}Building speech service image...${NC}"
    docker build \
        -t ${IMAGE_NAME}:latest \
        -f ${PROJECT_ROOT}/docker/Dockerfile.speech-p100 \
        ${PROJECT_ROOT}
    echo -e "${GREEN}Build complete!${NC}"
}

run() {
    # Check if container already running
    if docker ps -q -f name=${CONTAINER_NAME} | grep -q .; then
        echo -e "${YELLOW}Container ${CONTAINER_NAME} already running${NC}"
        echo "Use '$0 stop' to stop it first, or '$0 logs' to view logs"
        return
    fi

    # Remove stopped container if exists
    docker rm -f ${CONTAINER_NAME} 2>/dev/null || true

    echo -e "${GREEN}Starting speech service on GPU ${GPU_ID} (P100)...${NC}"

    docker run -d \
        --name ${CONTAINER_NAME} \
        --gpus "device=${GPU_ID}" \
        --restart unless-stopped \
        -p ${PORT}:8765 \
        -v ${PROJECT_ROOT}/models:/app/models:rw \
        -v bestbox-speech-cache:/root/.cache \
        -e ASR_ENGINE=funasr \
        -e TTS_ENGINE=melo \
        -e S2S_ENABLE_TTS=true \
        ${IMAGE_NAME}:latest

    echo -e "${GREEN}Speech service started!${NC}"
    echo ""
    echo "  Container: ${CONTAINER_NAME}"
    echo "  Port:      ${PORT}"
    echo "  GPU:       ${GPU_ID} (P100)"
    echo ""
    echo "Health check: curl http://localhost:${PORT}/health"
    echo "View logs:    docker logs -f ${CONTAINER_NAME}"
}

stop() {
    echo -e "${YELLOW}Stopping speech service...${NC}"
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    docker rm ${CONTAINER_NAME} 2>/dev/null || true
    echo -e "${GREEN}Stopped${NC}"
}

logs() {
    docker logs -f ${CONTAINER_NAME}
}

status() {
    if docker ps -q -f name=${CONTAINER_NAME} | grep -q .; then
        echo -e "${GREEN}Speech service is running${NC}"
        docker ps -f name=${CONTAINER_NAME} --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        curl -s http://localhost:${PORT}/health 2>/dev/null | python3 -m json.tool || echo "Health check failed"
    else
        echo -e "${YELLOW}Speech service is not running${NC}"
    fi
}

case "${1:-run}" in
    build)
        build
        ;;
    run)
        run
        ;;
    start)
        run
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        run
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    build-run)
        build
        run
        ;;
    *)
        echo "Usage: $0 {build|run|stop|restart|logs|status|build-run}"
        echo ""
        echo "Commands:"
        echo "  build     Build the Docker image"
        echo "  run       Start the container (default)"
        echo "  stop      Stop the container"
        echo "  restart   Stop and start the container"
        echo "  logs      View container logs"
        echo "  status    Check if service is running"
        echo "  build-run Build image and start container"
        exit 1
        ;;
esac
