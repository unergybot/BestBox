#!/bin/bash
# Start Decoupled OCR & Docling Services in Docker
# Target: GPU OCR (P100) + CPU Docling

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.ocr.yml"

echo "Orchestrating OCR and Docling services..."

# We don't need to manually export .env vars for docker-compose 
# if we specify the --env-file or let it find it.
# However, for the echo at the end we might need them.

# Load variables for the script output safely
if [ -f "$PROJECT_ROOT/.env" ]; then
    OCR_PORT=$(grep ^OCR_PORT= "$PROJECT_ROOT/.env" | cut -d'=' -f2-)
    DOC_PORT=$(grep ^DOC_PORT= "$PROJECT_ROOT/.env" | cut -d'=' -f2-)
fi

OCR_PORT=${OCR_PORT:-8084}
DOC_PORT=${DOC_PORT:-8085}

# Use docker-compose to build and start
# --env-file ensures it finds the root .env
docker compose -f "$COMPOSE_FILE" --env-file "$PROJECT_ROOT/.env" up -d --build

echo ""
echo "Services started:"
echo "  - OCR GPU Service: http://localhost:$OCR_PORT"
echo "  - Docling CPU Service: http://localhost:$DOC_PORT"
echo ""
echo "To view logs, run: docker compose -f $COMPOSE_FILE logs -f"
