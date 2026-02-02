#!/bin/bash
#
# start-all-services.sh - Orchestrated startup for BestBox services
#
# Starts services in tiers with health checks to ensure proper dependency order:
# Tier 1: Docker infrastructure (Qdrant, PostgreSQL, Redis)
# Tier 2: LLM inference services (LLM server, Embeddings, Reranker, Agent API)
# Tier 3: Optional services (S2S Gateway)
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== BestBox Service Orchestrator ===${NC}"
echo ""

# Load environment variables from .env if present
if [ -f .env ]; then
    set -o allexport
    source .env
    set +o allexport
fi

# Helper function to check if a service is healthy
check_health() {
    local name=$1
    local url=$2
    local max_attempts=${3:-30}  # Default 30 attempts = 30 seconds
    local attempt=1

    echo -n "Waiting for $name to be ready"

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    echo -e " ${RED}✗ (timeout)${NC}"
    return 1
}

# Helper to check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Helper to detect NVIDIA GPU
has_nvidia_gpu() {
    command -v nvidia-smi > /dev/null 2>&1 && nvidia-smi -L > /dev/null 2>&1
}

echo -e "${YELLOW}=== Tier 1: Docker Infrastructure ===${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Start Docker services
echo "Starting Docker services..."
docker compose up -d

# Wait for Qdrant
if ! check_health "Qdrant" "http://localhost:6333/healthz" 30; then
    echo -e "${RED}Error: Qdrant failed to start${NC}"
    echo "Check logs: docker logs bestbox-qdrant"
    exit 1
fi

# Wait for PostgreSQL
if ! check_health "PostgreSQL" "http://localhost:5432" 30; then
    echo -e "${YELLOW}Warning: PostgreSQL health check failed (may still be working)${NC}"
fi

# Wait for Redis
if ! check_health "Redis" "http://localhost:6379" 30; then
    echo -e "${YELLOW}Warning: Redis health check failed (may still be working)${NC}"
fi

echo -e "${GREEN}✓ Tier 1 complete${NC}"
echo ""

# Wait for ERPNext (part of Tier 1 but takes longer)
echo -n "Waiting for ERPNext..."
if timeout 180 bash -c 'until curl -f http://localhost:8002/api/method/ping >/dev/null 2>&1; do sleep 2; done'; then
    echo -e "${GREEN}✓ Ready${NC}"
else
    echo -e "${YELLOW}Warning: ERPNext startup timed out (may still be initializing)${NC}"
fi


echo -e "${YELLOW}=== Tier 2: LLM Inference Services ===${NC}"

# Auto-detect the optional combined Embedding/Reranker service (typically on P100)
# if the user hasn't configured explicit URLs.
if [ -z "${EMBEDDINGS_URL:-}" ] || [ -z "${RERANKER_URL:-}" ]; then
    if curl -sf --max-time 1 "http://127.0.0.1:8004/health" > /dev/null 2>&1; then
        export EMBEDDINGS_URL="${EMBEDDINGS_URL:-http://127.0.0.1:8004}"
        export RERANKER_URL="${RERANKER_URL:-http://127.0.0.1:8004}"
    fi
fi

# Start LLM server
if curl -sf --max-time 1 "http://localhost:8001/health" > /dev/null 2>&1; then
    echo -e "${YELLOW}LLM server already reachable on port 8001${NC}"
elif is_running "llama-server"; then
    echo -e "${YELLOW}LLM server already running${NC}"
else
    # Prefer vLLM with CUDA when NVIDIA GPUs are present
    if has_nvidia_gpu; then
        if [ -f "./scripts/start-vllm-cuda.sh" ]; then
            echo "🚀 NVIDIA GPU detected! Starting vLLM CUDA server..."
            ./scripts/start-vllm-cuda.sh &
        else
            echo "🚀 NVIDIA GPU detected! vLLM script not found, falling back to llama-server..."
            ./scripts/start-llm-cuda.sh &
        fi
    # Detect Strix Halo hardware (AMD Radeon 8060S / gfx1103)
    elif lspci | grep -qi "Radeon 8060"; then
        echo "🚀 Strix Halo detected! Starting optimized LLM server..."
        ./scripts/start-llm-strix.sh &
    else
        echo "Starting standard LLM server..."
        ./scripts/start-llm.sh &
    fi
    sleep 2
fi


# Initialize ERPNext site if needed
# (This acts as a check to ensure the site is ready for seeding)
# We skip complex init script for now as the docker image should handle basic site creation
# but we can check if it's responsive first.

# ---------------------------------------------------------------------------
# ERPNext demo seeding (opt-in)
#
# Transactions seeding is NOT idempotent (creates new POs), so we do not run it
# automatically on every startup. To seed, run manually:
#   SEED_ERPNEXT=true ./scripts/start-all-services.sh
# Or run the individual scripts directly.
# ---------------------------------------------------------------------------
echo "Checking ERPNext data..."

SEED_STATE_DIR="${SEED_STATE_DIR:-./data/.seed_state}"
ERP_SEED_SENTINEL="${ERP_SEED_SENTINEL:-${SEED_STATE_DIR}/erpnext_seeded}"

mkdir -p "${SEED_STATE_DIR}" 2>/dev/null || true

if [ "${SEED_ERPNEXT:-false}" = "true" ]; then
    if [ -f "${ERP_SEED_SENTINEL}" ] && [ "${FORCE_SEED_ERPNEXT:-false}" != "true" ]; then
        echo -e "${YELLOW}Skipping ERPNext seeding (already seeded). Set FORCE_SEED_ERPNEXT=true to reseed.${NC}"
    else
        echo "Seeding ERPNext demo data (SEED_ERPNEXT=true)..."
        # Use venv python if available
        PYTHON_CMD="python"
        [ -f "./venv/bin/python" ] && PYTHON_CMD="./venv/bin/python"

        $PYTHON_CMD scripts/seed_erpnext_basic.py || echo "Warning: Basic seeding failed"
        $PYTHON_CMD scripts/seed_erpnext_fiscal_data.py || echo "Warning: Fiscal year seeding failed"
        $PYTHON_CMD scripts/seed_erpnext_transactions.py || echo "Warning: Transaction seeding failed"

        date -Iseconds > "${ERP_SEED_SENTINEL}" 2>/dev/null || true
    fi
else
    # Do a lightweight check just for operator visibility (no side effects)
    if docker compose ps -q erpnext >/dev/null 2>&1; then
        # -T avoids TTY allocation issues in non-interactive shells
        if docker compose exec -T erpnext bash -lc 'mysql -h mariadb -u root -padmin erpnext -e "SELECT COUNT(*) AS c FROM tabSupplier" 2>/dev/null | tail -n +2 | tr -d "[:space:]" | grep -Eq "^[0-9]+$"'; then
            SUPPLIER_COUNT=$(docker compose exec -T erpnext bash -lc 'mysql -h mariadb -u root -padmin erpnext -e "SELECT COUNT(*) AS c FROM tabSupplier" 2>/dev/null | tail -n +2 | tr -d "[:space:]"' 2>/dev/null || echo "")
            if [ -n "${SUPPLIER_COUNT}" ]; then
                echo "ERPNext Suppliers count: ${SUPPLIER_COUNT} (seeding disabled by default)"
            fi
        fi
    fi
fi

if ! check_health "LLM Server" "http://localhost:8001/health" 60; then
    echo -e "${RED}Error: LLM server failed to start${NC}"
    echo "Check logs in the terminal where start-llm.sh is running"
    exit 1
fi

# Start / verify Embeddings service
# If EMBEDDINGS_URL is set (e.g. http://127.0.0.1:8004), prefer that instead of
# launching the local (8081) python service.
EMBEDDINGS_URL_EFFECTIVE="${EMBEDDINGS_URL:-http://localhost:8081}"
EMBEDDINGS_URL_BASE="${EMBEDDINGS_URL_EFFECTIVE%/v1}"
EMBEDDINGS_HEALTH_URL="${EMBEDDINGS_URL_BASE%/}/health"

if [[ "${EMBEDDINGS_URL_EFFECTIVE}" != "http://localhost:8081" && "${EMBEDDINGS_URL_EFFECTIVE}" != "http://127.0.0.1:8081" ]]; then
    echo -e "${YELLOW}Using external Embeddings service: ${EMBEDDINGS_URL_EFFECTIVE}${NC}"
    if ! check_health "Embeddings" "${EMBEDDINGS_HEALTH_URL}" 60; then
        echo -e "${YELLOW}Warning: Embeddings service not responding at ${EMBEDDINGS_HEALTH_URL}${NC}"
    fi
else
    if is_running "services.embeddings.main"; then
        echo -e "${YELLOW}Embeddings server already running${NC}"
    else
        echo "Starting Embeddings server..."
        ./scripts/start-embeddings.sh &
        sleep 2
    fi

    if ! check_health "Embeddings" "http://localhost:8081/health" 60; then
        echo -e "${YELLOW}Warning: Embeddings server not responding (may still be loading)${NC}"
    fi
fi

# Start / verify Reranker service
RERANKER_URL_EFFECTIVE="${RERANKER_URL:-http://localhost:8082}"
RERANKER_URL_BASE="${RERANKER_URL_EFFECTIVE%/v1}"
RERANKER_HEALTH_URL="${RERANKER_URL_BASE%/}/health"

if [[ "${RERANKER_URL_EFFECTIVE}" != "http://localhost:8082" && "${RERANKER_URL_EFFECTIVE}" != "http://127.0.0.1:8082" ]]; then
    echo -e "${YELLOW}Using external Reranker service: ${RERANKER_URL_EFFECTIVE}${NC}"
    if ! check_health "Reranker" "${RERANKER_HEALTH_URL}" 60; then
        echo -e "${YELLOW}Warning: Reranker service not responding at ${RERANKER_HEALTH_URL}${NC}"
    fi
else
    if [ -f "./scripts/start-reranker.sh" ]; then
        if is_running "services.reranker.main"; then
            echo -e "${YELLOW}Reranker server already running${NC}"
        else
            echo "Starting Reranker server..."
            ./scripts/start-reranker.sh &
            sleep 2
        fi

        if ! check_health "Reranker" "http://localhost:8082/health" 60; then
            echo -e "${YELLOW}Warning: Reranker not responding (optional service)${NC}"
        fi
    else
        echo -e "${YELLOW}Reranker script not found (optional)${NC}"
    fi
fi

# Start Agent API
if is_running "services.agent_api"; then
    echo -e "${YELLOW}Agent API already running${NC}"
else
    echo "Starting Agent API..."
    ./scripts/start-agent-api.sh &
    sleep 2
fi

if ! check_health "Agent API" "http://localhost:8000/health" 30; then
    echo -e "${RED}Error: Agent API failed to start${NC}"
    echo "Check logs in the terminal where start-agent-api.sh is running"
    exit 1
fi

# Check for venv python
if [ -f "./venv/bin/python" ]; then
    PYTHON_EXEC="./venv/bin/python"
else
    PYTHON_EXEC="python"
fi

# Start Slack Gateway (if enabled)
if [ "${ENABLE_SLACK_GATEWAY:-false}" = "true" ]; then
    if is_running "services.slack_gateway"; then
        echo -e "${YELLOW}Slack Gateway already running${NC}"
    else
        echo "Starting Slack Gateway..."
        # We don't have a specific start script, so running python directly in background
        nohup $PYTHON_EXEC services/slack_gateway.py > slack_gateway.log 2>&1 &
        sleep 1
        echo -e "${GREEN}✓ Slack Gateway started${NC}"
    fi
fi

# Start Telegram Gateway (if enabled)
if [ "${ENABLE_TELEGRAM_GATEWAY:-false}" = "true" ]; then
    if is_running "services.telegram_gateway"; then
        echo -e "${YELLOW}Telegram Gateway already running${NC}"
    else
        echo "Starting Telegram Gateway..."
        nohup $PYTHON_EXEC services/telegram_gateway.py > telegram_gateway.log 2>&1 &
        sleep 1
        echo -e "${GREEN}✓ Telegram Gateway started${NC}"
    fi
fi

echo -e "${GREEN}✓ Tier 2 complete${NC}"
echo ""

echo -e "${YELLOW}=== Tier 3: Optional Services ===${NC}"

# Check if LiveKit stack (Tier 1) is healthy
if [ "${USE_LIVEKIT:-true}" = "true" ]; then
    echo "Checking LiveKit stack..."
    if check_health "LiveKit Server" "http://localhost:7880" 10; then
        echo -e "${GREEN}✅ LiveKit server is running on port 7880${NC}"
    else
        echo -e "${YELLOW}Warning: LiveKit server (bestbox-livekit) not responding on port 7880${NC}"
        echo "Attempting to start fallback LiveKit server..."
        docker rm -f livekit-server 2>/dev/null || true
        docker run -d --name livekit-server \
          -p 7880:7880 -p 7881:7881/tcp -p 50000-50020:50000-50020/udp \
          -v "$(pwd)/livekit.yaml:/etc/livekit.yaml" \
          livekit/livekit-server:latest --config /etc/livekit.yaml > /dev/null 2>&1
        sleep 3
    fi
    
    # Start LiveKit Agent automatically if not already running
    if is_running "livekit_agent.py"; then
        echo -e "${YELLOW}LiveKit Agent already running${NC}"
    else
        echo "Starting LiveKit Agent..."
        nohup ./scripts/start-livekit-agent.sh dev > livekit_agent.log 2>&1 &
        echo -e "${GREEN}✅ LiveKit Agent started in background${NC}"
    fi
fi

# Start S2S Gateway (legacy but still used for status and some features)
if [ "${SKIP_S2S:-false}" = "true" ]; then
    echo -e "${YELLOW}Skipping S2S Gateway (SKIP_S2S=true)${NC}"
else
    # Ensure S2S binds to the port the frontend expects by default.
    # Override with BESTBOX_S2S_PORT if you need a non-default port.
    export S2S_PORT="${BESTBOX_S2S_PORT:-8765}"
    export S2S_HOST="${S2S_HOST:-0.0.0.0}"

    if is_running "services.speech.s2s_server"; then
        # If it is running but not healthy on the expected port, restart it.
        if ! curl -sf --max-time 1 "http://localhost:${S2S_PORT}/health" > /dev/null 2>&1; then
            echo -e "${YELLOW}S2S Gateway running but not reachable on port ${S2S_PORT}; restarting...${NC}"
            pkill -f "services.speech.s2s_server" || true
            sleep 2
        else
            echo -e "${YELLOW}S2S Gateway already running${NC}"
        fi
    else
        echo "Starting S2S Gateway..."
        ./scripts/start-s2s.sh &
        sleep 2
    fi

    if ! check_health "S2S Gateway" "http://localhost:${S2S_PORT}/health" 30; then
        echo -e "${YELLOW}Warning: S2S Gateway not responding${NC}"
    fi
fi

echo -e "${GREEN}✓ Tier 3 complete${NC}"
echo ""

echo -e "${GREEN}=== All Services Started ===${NC}"
echo ""
echo "Service Status:"
echo "  LLM Server:     http://localhost:8001/health"
echo "  Embeddings:     ${EMBEDDINGS_HEALTH_URL}"
echo "  Reranker:       ${RERANKER_HEALTH_URL}"
echo "  Agent API:      http://localhost:8000/health"
if [ "${USE_LIVEKIT:-false}" = "true" ]; then
    echo "  LiveKit:        http://localhost:7880 (Voice - Recommended)"
    echo "                  To start agent: python services/livekit_agent.py dev"
else
    echo "  S2S Gateway:    http://localhost:8765/health (Legacy)"
fi
echo "  Qdrant:         http://localhost:6333/healthz"
echo "  Frontend:       http://localhost:3000 (start separately with 'cd frontend/copilot-demo && npm run dev')"
echo ""
echo "Environment Variables:"
echo "  USE_LIVEKIT=true    - Use LiveKit for voice (low latency, recommended)"
echo "  SKIP_S2S=true       - Skip both LiveKit and S2S"
echo ""
echo "To stop services:"
echo "  - Docker services: docker compose down"
if [ "${USE_LIVEKIT:-false}" = "true" ]; then
    echo "  - LiveKit server: docker stop livekit-server"
fi
echo "  - Python services: pkill -f 'llama-server|embeddings|agent_api|s2s_server'"
echo ""
echo -e "${YELLOW}Note: Services are running in background. Check individual terminals for logs.${NC}"
