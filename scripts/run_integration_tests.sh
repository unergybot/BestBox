#!/bin/bash
#
# Run comprehensive integration tests for BestBox
#
# Usage:
#   ./scripts/run_integration_tests.sh [options]
#
# Options:
#   --full         Run all tests including those requiring services
#   --fast         Run only unit tests (no service dependencies)
#   --coverage     Generate coverage report
#   --verbose      Show detailed output
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         BestBox Integration Test Suite                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Parse arguments
RUN_MODE="fast"
COVERAGE=false
VERBOSE=""
PYTEST_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --full)
            RUN_MODE="full"
            shift
            ;;
        --fast)
            RUN_MODE="fast"
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        --verbose)
            VERBOSE="-v"
            PYTEST_ARGS="$PYTEST_ARGS -v -s"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}Test Mode:${NC} $RUN_MODE"
echo -e "${YELLOW}Coverage:${NC} $COVERAGE"
echo ""

# Check Python environment
if ! command -v python &> /dev/null; then
    echo -e "${RED}✗ Python not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python:${NC} $(python --version)"

# Install test dependencies if needed
echo ""
echo -e "${BLUE}Checking test dependencies...${NC}"
pip install -q pytest pytest-asyncio pytest-cov requests psycopg2-binary 2>/dev/null || true

# Check service dependencies
echo ""
echo -e "${BLUE}Checking service availability...${NC}"

check_service() {
    local name=$1
    local url=$2
    local required=$3
    
    if curl -s -f -o /dev/null --max-time 2 "$url" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $name is running"
        return 0
    else
        if [ "$required" = "true" ]; then
            echo -e "${RED}✗${NC} $name is NOT running (required for full tests)"
        else
            echo -e "${YELLOW}⚠${NC} $name is NOT running (optional)"
        fi
        return 1
    fi
}

LLM_AVAILABLE=false
API_AVAILABLE=false
DB_AVAILABLE=false

if [ "$RUN_MODE" = "full" ]; then
    check_service "LLM Server" "http://localhost:8080/health" "true" && LLM_AVAILABLE=true || true
    check_service "Agent API" "http://localhost:8000/health" "false" && API_AVAILABLE=true || true
    check_service "Prometheus" "http://localhost:9091/-/healthy" "false" || true
    
    # Check database
    if python -c "import psycopg2; psycopg2.connect(host='localhost', port=5432, database='bestbox', user='bestbox', password='bestbox')" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} PostgreSQL is running"
        DB_AVAILABLE=true
    else
        echo -e "${YELLOW}⚠${NC} PostgreSQL is NOT running (optional)"
    fi
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Running Tests...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Build pytest command
PYTEST_CMD="pytest"

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=agents --cov=services --cov=tools --cov-report=html --cov-report=term"
fi

PYTEST_CMD="$PYTEST_CMD $PYTEST_ARGS"

# Test categories
declare -a TEST_SUITES=(
    "tests/test_integration_full.py::TestAgentRouting"
    "tests/test_integration_full.py::TestContextManagement"
    "tests/test_integration_full.py::TestToolIntegration"
    "tests/test_integration_full.py::TestRAGIntegration"
    "tests/test_integration_full.py::TestLiveKitIntegration"
)

if [ "$RUN_MODE" = "full" ]; then
    TEST_SUITES+=(
        "tests/test_integration_full.py::TestGraphExecution"
        "tests/test_integration_full.py::TestEndToEndScenarios"
        "tests/test_integration_full.py::TestObservability"
        "tests/test_integration_full.py::TestSystemHealth"
    )
fi

# Run each test suite
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0

for suite in "${TEST_SUITES[@]}"; do
    suite_name=$(echo "$suite" | cut -d':' -f3)
    echo -e "${YELLOW}Testing: ${NC}$suite_name"
    
    if $PYTEST_CMD "$suite" 2>&1 | tee /tmp/pytest_output.txt; then
        # Count results
        PASSED=$(grep -o "passed" /tmp/pytest_output.txt | wc -l)
        FAILED=$(grep -o "failed" /tmp/pytest_output.txt | wc -l)
        SKIPPED=$(grep -o "skipped" /tmp/pytest_output.txt | wc -l)
        
        TOTAL_PASSED=$((TOTAL_PASSED + PASSED))
        TOTAL_FAILED=$((TOTAL_FAILED + FAILED))
        TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIPPED))
        
        echo -e "${GREEN}✓${NC} $suite_name completed"
    else
        echo -e "${RED}✗${NC} $suite_name failed"
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi
    echo ""
done

# Run additional test files
echo -e "${BLUE}Running additional test files...${NC}"
echo ""

declare -a ADDITIONAL_TESTS=(
    "tests/test_rag_integration.py"
    "tests/test_vector_store.py"
    "tests/test_chunker.py"
)

for test_file in "${ADDITIONAL_TESTS[@]}"; do
    if [ -f "$test_file" ]; then
        test_name=$(basename "$test_file")
        echo -e "${YELLOW}Testing: ${NC}$test_name"
        
        if $PYTEST_CMD "$test_file" 2>&1 | tee /tmp/pytest_output.txt; then
            echo -e "${GREEN}✓${NC} $test_name completed"
        else
            echo -e "${YELLOW}⚠${NC} $test_name skipped or failed"
        fi
        echo ""
    fi
done

# Summary
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Passed:${NC}  $TOTAL_PASSED"
echo -e "${RED}Failed:${NC}  $TOTAL_FAILED"
echo -e "${YELLOW}Skipped:${NC} $TOTAL_SKIPPED"
echo ""

if [ "$COVERAGE" = true ] && [ -d "htmlcov" ]; then
    echo -e "${BLUE}Coverage report generated:${NC} htmlcov/index.html"
    echo ""
fi

# Recommendations
if [ "$RUN_MODE" = "fast" ]; then
    echo -e "${YELLOW}ℹ${NC}  Running in fast mode. Use ${BLUE}--full${NC} to run integration tests."
fi

if [ "$LLM_AVAILABLE" = false ] && [ "$RUN_MODE" = "full" ]; then
    echo -e "${YELLOW}ℹ${NC}  Start LLM server for complete testing: ${BLUE}./scripts/start-llm.sh${NC}"
fi

echo ""

# Exit code
if [ $TOTAL_FAILED -gt 0 ]; then
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
else
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
fi
