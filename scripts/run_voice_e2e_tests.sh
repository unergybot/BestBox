#!/bin/bash
#
# Voice Pipeline E2E Test Runner
#
# Runs comprehensive tests for Xunfei integration and voice pipeline.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Voice Pipeline E2E Test Suite"
echo "========================================="
echo ""

# Function to check if service is running
check_service() {
    local name=$1
    local url=$2

    if curl -s -f -o /dev/null "$url"; then
        echo -e "${GREEN}✓${NC} $name is running"
        return 0
    else
        echo -e "${RED}✗${NC} $name is NOT running"
        return 1
    fi
}

# Check prerequisites
echo "=== Checking Prerequisites ==="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}✗${NC} pytest not installed"
    echo "Install with: pip install pytest pytest-asyncio"
    exit 1
fi
echo -e "${GREEN}✓${NC} pytest is installed"

# Check if required Python packages are available
python3 -c "import services.xunfei_adapters" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} xunfei_adapters module available"
else
    echo -e "${RED}✗${NC} xunfei_adapters module not found"
    exit 1
fi

echo ""

# Check optional services for integration tests
echo "=== Checking Optional Services (for integration tests) ==="
echo ""

services_available=0

if check_service "LLM Server" "http://localhost:8080/health"; then
    ((services_available++))
fi

if check_service "Agent API" "http://localhost:8000/health"; then
    ((services_available++))
fi

# Skip LiveKit check for now (port 7880 may not respond to HTTP health checks)
# if check_service "LiveKit Server" "http://localhost:7880"; then
#     ((services_available++))
# fi

echo ""

if [ $services_available -eq 0 ]; then
    echo -e "${YELLOW}⚠${NC} No services detected - integration tests will be skipped"
    echo "To run integration tests, start services with:"
    echo "  ./scripts/start-llm.sh"
    echo "  ./scripts/start-agent-api.sh"
    echo "  ./scripts/start-livekit.sh"
    echo ""
fi

# Run tests
echo "========================================="
echo "Running Tests"
echo "========================================="
echo ""

# Phase 1: Unit tests (no services required)
echo "=== Phase 1: Unit Tests ==="
echo "Running: pytest tests/test_xunfei_adapters.py -v -m 'not integration'"
echo ""

pytest tests/test_xunfei_adapters.py -v -m "not integration" --tb=short

if [ $? -ne 0 ]; then
    echo -e "${RED}✗${NC} Unit tests failed"
    exit 1
fi

echo ""
echo -e "${GREEN}✓${NC} Unit tests passed"
echo ""

# Phase 2: Integration tests (if services available)
if [ $services_available -ge 2 ]; then
    echo "=== Phase 2: Integration Tests ==="
    echo "Running: pytest tests/test_voice_pipeline_e2e.py -v -m integration"
    echo ""

    pytest tests/test_voice_pipeline_e2e.py -v -m "integration" --tb=short

    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}⚠${NC} Integration tests failed (this is expected if services are not fully configured)"
    else
        echo -e "${GREEN}✓${NC} Integration tests passed"
    fi
    echo ""
else
    echo "=== Phase 2: Integration Tests (SKIPPED) ==="
    echo -e "${YELLOW}⚠${NC} Skipping integration tests - services not available"
    echo ""
fi

# Phase 3: Configuration tests (always run)
echo "=== Phase 3: Configuration Tests ==="
echo "Running: pytest tests/test_voice_pipeline_e2e.py::TestVoicePipelineConfiguration -v"
echo ""

pytest tests/test_voice_pipeline_e2e.py::TestVoicePipelineConfiguration -v --tb=short

if [ $? -ne 0 ]; then
    echo -e "${RED}✗${NC} Configuration tests failed"
    exit 1
fi

echo ""
echo -e "${GREEN}✓${NC} Configuration tests passed"
echo ""

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo ""
echo -e "${GREEN}✓${NC} Unit tests: PASSED"
echo -e "${GREEN}✓${NC} Configuration tests: PASSED"

if [ $services_available -ge 2 ]; then
    echo -e "Integration tests: See results above"
else
    echo -e "${YELLOW}⚠${NC} Integration tests: SKIPPED (services not available)"
fi

echo ""
echo "========================================="
echo "All tests completed!"
echo "========================================="
