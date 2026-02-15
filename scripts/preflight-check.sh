#!/bin/bash
# Pre-flight validation for BestBox customer pilot deployment

set -e

echo "=========================================="
echo "BestBox Customer Pilot - Pre-flight Check"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
WARN=0
FAIL=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARN++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

# 1. Check Python version
echo "[1/12] Checking Python version..."
PYTHON_VERSION=$(python --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
    check_pass "Python 3.8+ detected: $(python --version 2>&1)"
else
    check_fail "Python 3.8+ required, found: $(python --version 2>&1)"
fi

# 2. Check GPU availability
echo ""
echo "[2/12] Checking GPU availability..."
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        check_pass "NVIDIA GPU detected: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
        export GPU_BACKEND="cuda"
    else
        check_warn "nvidia-smi found but failed to execute"
    fi
elif command -v rocm-smi &> /dev/null || command -v rocminfo &> /dev/null; then
    check_pass "AMD ROCm GPU detected"
    export GPU_BACKEND="rocm"
else
    check_warn "No GPU detected - will run in CPU mode (slower)"
    export GPU_BACKEND="cpu"
fi

# 3. Check required ports
echo ""
echo "[3/12] Checking port availability..."
REQUIRED_PORTS=(6333 6334 5432 6379 8001 8081 8082 8000)
for port in "${REQUIRED_PORTS[@]}"; do
    if ! lsof -i:$port &> /dev/null; then
        check_pass "Port $port available"
    else
        check_warn "Port $port already in use (may need to stop existing service)"
    fi
done

# 4. Check Docker (for Qdrant, Postgres, Redis)
echo ""
echo "[4/12] Checking Docker..."
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        check_pass "Docker is running"
    else
        check_fail "Docker installed but not running (start with: sudo systemctl start docker)"
    fi
else
    check_fail "Docker not found (required for Qdrant, PostgreSQL, Redis)"
fi

# 5. Check BestBox directory structure
echo ""
echo "[5/12] Checking BestBox directory structure..."
REQUIRED_DIRS=(agents services tools scripts frontend data)
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        check_pass "Directory exists: $dir/"
    else
        check_fail "Missing directory: $dir/"
    fi
done

# 6. Check virtual environment
echo ""
echo "[6/12] Checking Python virtual environment..."
if [ -d "venv" ]; then
    check_pass "Virtual environment exists: venv/"
    if [ -f "venv/bin/python" ]; then
        check_pass "Python executable found in venv"
    else
        check_fail "venv/bin/python not found"
    fi
else
    check_warn "Virtual environment not found (will be created during setup)"
fi

# 7. Check critical Python packages
echo ""
echo "[7/12] Checking critical Python packages..."
if [ -f "venv/bin/python" ]; then
    source venv/bin/activate
    PACKAGES=(langchain langgraph qdrant-client fastapi uvicorn)
    for pkg in "${PACKAGES[@]}"; do
        if python -c "import ${pkg//-/_}" &> /dev/null; then
            check_pass "Package installed: $pkg"
        else
            check_warn "Package missing: $pkg (will be installed)"
        fi
    done
else
    check_warn "Skipping package check (venv not activated)"
fi

# 8. Check .env file
echo ""
echo "[8/12] Checking .env file..."
if [ -f ".env" ]; then
    check_pass ".env file exists"

    # Check for critical env vars
    if grep -q "NVIDIA_API_KEY=" .env || grep -q "LLM_BASE_URL=" .env; then
        check_pass "LLM configuration found in .env"
    else
        check_warn "LLM configuration may be missing from .env"
    fi
else
    check_warn ".env file not found (copy from .env.example)"
fi

# 9. Check disk space
echo ""
echo "[9/12] Checking disk space..."
AVAILABLE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE" -gt 20 ]; then
    check_pass "Sufficient disk space: ${AVAILABLE}GB available"
else
    check_warn "Low disk space: ${AVAILABLE}GB (recommend 20GB+)"
fi

# 10. Check network connectivity
echo ""
echo "[10/12] Checking network connectivity..."
if ping -c 1 8.8.8.8 &> /dev/null; then
    check_pass "Internet connectivity: OK"
else
    check_warn "No internet connection (may affect model downloads)"
fi

# 11. Check for existing services
echo ""
echo "[11/12] Checking for existing BestBox services..."
if pgrep -f "agent_api.py" &> /dev/null; then
    check_warn "agent_api.py already running (may need to stop)"
else
    check_pass "No conflicting agent_api process"
fi

# 12. Check systemd (optional, for production deployment)
echo ""
echo "[12/12] Checking systemd availability..."
if command -v systemctl &> /dev/null; then
    check_pass "systemd available for service management"
else
    check_warn "systemd not available (manual service management required)"
fi

# Summary
echo ""
echo "=========================================="
echo "Pre-flight Check Summary"
echo "=========================================="
echo -e "${GREEN}✓ Passed: $PASS${NC}"
echo -e "${YELLOW}⚠ Warnings: $WARN${NC}"
echo -e "${RED}✗ Failed: $FAIL${NC}"
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}❌ CRITICAL: $FAIL checks failed. Please fix before proceeding.${NC}"
    exit 1
elif [ $WARN -gt 3 ]; then
    echo -e "${YELLOW}⚠️  WARNING: $WARN checks have warnings. Review before proceeding.${NC}"
    exit 0
else
    echo -e "${GREEN}✅ PRE-FLIGHT PASSED: System ready for deployment${NC}"
    echo ""
    echo "Detected GPU backend: $GPU_BACKEND"
    echo "Next step: ./scripts/setup-customer.sh"
    exit 0
fi
