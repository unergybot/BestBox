#!/bin/bash
# Start GOT-OCR2.0 Service in Docker
# Target: P100 GPU (16GB VRAM, CUDA 11.8)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_FILE="$PROJECT_ROOT/docker/Dockerfile.ocr-p100"
IMAGE_NAME="bestbox-ocr-p100"
CONTAINER_NAME="bestbox-ocr"

# Source environment variables if available
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

OCR_PORT=${OCR_PORT:-8084}

echo "Building OCR Docker image..."
docker build -t "$IMAGE_NAME" -f "$DOCKER_FILE" "$PROJECT_ROOT"

echo "Starting OCR container..."
# Stop existing container if running
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    docker stop "$CONTAINER_NAME"
    docker rm "$CONTAINER_NAME"
fi
# Remove stopped container if exists
if [ "$(docker ps -aq -f status=exited -f name=$CONTAINER_NAME)" ]; then
    docker rm "$CONTAINER_NAME"
fi

docker run -d \
    --name "$CONTAINER_NAME" \
    --gpus 'device=0' \
    -p "$OCR_PORT":8084 \
    --restart unless-stopped \
    -e OCR_PORT=8084 \
    -e CUDA_VISIBLE_DEVICES=0 \
    "$IMAGE_NAME"

echo "OCR Service started in Docker container: $CONTAINER_NAME on port $OCR_PORT"
echo "Logs:"
docker logs -f "$CONTAINER_NAME"
