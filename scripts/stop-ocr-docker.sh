#!/bin/bash
# Stop OCR Services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🛑 Stopping BestBox OCR Services..."

cd "$PROJECT_ROOT/docker"

if [ -f "docker-compose.ocr.yml" ]; then
    docker compose -f docker-compose.ocr.yml down
    echo "✅ OCR services stopped"
else
    echo "⚠️  docker-compose.ocr.yml not found"
fi

echo ""
