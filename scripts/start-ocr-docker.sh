#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==================================="
echo "Starting BestBox OCR Services"
echo "==================================="
echo ""

echo "🔍 Checking GPU setup..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  Warning: nvidia-smi not found. GPU services may not work properly."
else
    echo "✅ NVIDIA drivers detected"
    nvidia-smi --query-gpu=name,index,memory.total --format=csv,noheader
fi

echo ""
echo "📋 Service Overview:"
echo "  • ocr-service      :8084  GOT-OCR2.0 on P100 (GPU 0)"
echo "  • glm-ocr-service  :11434 GLM-OCR on RTX 3080 (GPU 1)"
echo "  • docling-service  :8085  Docling with quality gate (CPU)"
echo "  • gpu-scheduler    :8086  Mutual exclusion scheduler"
echo ""

cd "$PROJECT_ROOT/docker"

if [ ! -f "docker-compose.ocr.yml" ]; then
    echo "❌ docker-compose.ocr.yml not found!"
    exit 1
fi

if ! docker network ls | grep -q "bestbox-network"; then
    echo "🌐 Creating bestbox-network..."
    docker network create bestbox-network 2>/dev/null || true
fi

echo "🐳 Building and starting OCR services..."
docker compose -f docker-compose.ocr.yml up --build -d

echo ""
echo "⏳ Waiting for services to be healthy..."
echo ""

wait_for_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker compose -f docker-compose.ocr.yml ps | grep -q "$service.*healthy"; then
            echo "  ✅ $service is healthy"
            return 0
        fi
        echo "  ⏳ Waiting for $service... ($attempt/$max_attempts)"
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo "  ❌ $service failed to become healthy"
    return 1
}

wait_for_service "bestbox-gpu-scheduler" "8086"
wait_for_service "bestbox-ocr" "8084"
wait_for_service "bestbox-glm-ocr" "11434"
wait_for_service "bestbox-docling" "8085"

echo ""
echo "==================================="
echo "✅ OCR Services Started"
echo "==================================="
echo ""
echo "Service Endpoints:"
echo "  Docling Parser:  http://localhost:8085/parse"
echo "  GOT-OCR2.0:      http://localhost:8084/ocr"
echo "  GLM-OCR:         http://localhost:11434/api/generate"
echo "  GPU Scheduler:   http://localhost:8086/lock"
echo ""
echo "Management Commands:"
echo "  View logs:       docker compose -f docker/docker-compose.ocr.yml logs -f"
echo "  Stop services:   docker compose -f docker/docker-compose.ocr.yml down"
echo "  Restart:         ./scripts/start-ocr-docker.sh"
echo ""
echo "🚀 Ready to process documents!"
echo ""
