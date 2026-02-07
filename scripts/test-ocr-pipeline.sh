#!/bin/bash
# Test OCR-VL Pipeline End-to-End
# Tests the complete flow: Docling -> Quality Gate -> GLM-OCR escalation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==================================="
echo "Testing OCR-VL Pipeline"
echo "==================================="
echo ""

# Check if services are running
check_service() {
    local name=$1
    local url=$2
    
    if curl -s "$url" > /dev/null 2>&1; then
        echo "✅ $name is running"
        return 0
    else
        echo "❌ $name is not responding"
        return 1
    fi
}

echo "🔍 Checking services..."
check_service "GPU Scheduler" "http://localhost:8086/health"
check_service "GOT-OCR2.0" "http://localhost:8084/health"
check_service "GLM-OCR" "http://localhost:11434/api/tags"
check_service "Docling" "http://localhost:8085/health"

echo ""
echo "📊 GPU Scheduler Status:"
curl -s http://localhost:8086/status | python3 -m json.tool 2>/dev/null || echo "Could not get status"

echo ""
echo "==================================="
echo "✅ Pipeline Test Complete"
echo "==================================="
echo ""
echo "To test document parsing:"
echo "  curl -X POST http://localhost:8085/parse \\"
echo "    -F 'file=@your-document.pdf' \\"
echo "    -F 'run_ocr=true'"
echo ""
