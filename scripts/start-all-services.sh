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

# Start LLM server
if is_running "llama-server"; then
    echo -e "${YELLOW}LLM server already running${NC}"
else
    # Prefer CUDA when NVIDIA GPUs are present
    if has_nvidia_gpu; then
        echo "🚀 NVIDIA GPU detected! Starting CUDA LLM server..."
        ./scripts/start-llm-cuda.sh &
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

# Check if demo data seeded
echo "Checking ERPNext data..."
# We use a simple python check or curl if possible, but docker exec is reliable for DB check
if docker compose ps -q erpnext >/dev/null; then
    # Only run if container is running
    if ! docker compose exec erpnext bash -c 'mysql -h mariadb -u root -padmin erpnext -e "SELECT COUNT(*) FROM tabSupplier" 2>/dev/null | grep -v COUNT | grep -q [1-9]'; then
        echo "Seeding ERPNext demo data..."
        # Use venv python if available
        PYTHON_CMD="python"
        [ -f "./venv/bin/python" ] && PYTHON_CMD="./venv/bin/python"
        
        $PYTHON_CMD scripts/seed_erpnext_basic.py || echo "Warning: Basic seeding failed"
        $PYTHON_CMD scripts/seed_erpnext_fiscal_data.py || echo "Warning: Fiscal year seeding failed"
        $PYTHON_CMD scripts/seed_erpnext_transactions.py || echo "Warning: Transaction seeding failed"
    fi
fi

if ! check_health "LLM Server" "http://localhost:8080/health" 60; then
    echo -e "${RED}Error: LLM server failed to start${NC}"
    echo "Check logs in the terminal where start-llm.sh is running"
    exit 1
fi

# Start Embeddings server
if is_running "services.embeddings.main"; then
    echo -e "${YELLOW}Embeddings server already running${NC}"
else
    echo "Starting Embeddings server..."
    ./scripts/start-embeddings.sh &
    sleep 2
fi

if ! check_health "Embeddings" "http://localhost:8081/health" 30; then
    echo -e "${YELLOW}Warning: Embeddings server not responding (may still be loading)${NC}"
fi

# Start Reranker server (if script exists)
if [ -f "./scripts/start-reranker.sh" ]; then
    if is_running "services.reranker.main"; then
        echo -e "${YELLOW}Reranker server already running${NC}"
    else
        echo "Starting Reranker server..."
        ./scripts/start-reranker.sh &
        sleep 2
    fi

    if ! check_health "Reranker" "http://localhost:8082/health" 30; then
        echo -e "${YELLOW}Warning: Reranker not responding (optional service)${NC}"
    fi
else
    echo -e "${YELLOW}Reranker script not found (optional)${NC}"
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
    if is_running "services.speech.s2s_server"; then
        echo -e "${YELLOW}S2S Gateway already running${NC}"
    else
        echo "Starting S2S Gateway..."
        ./scripts/start-s2s.sh &
        sleep 2
    fi

    if ! check_health "S2S Gateway" "http://localhost:8765/health" 30; then
        echo -e "${YELLOW}Warning: S2S Gateway not responding${NC}"
    fi
fi

echo -e "${GREEN}✓ Tier 3 complete${NC}"
echo ""

echo -e "${GREEN}=== All Services Started ===${NC}"
echo ""
echo "Service Status:"
echo "  LLM Server:     http://localhost:8080/health"
echo "  Embeddings:     http://localhost:8081/health"
echo "  Reranker:       http://localhost:8082/health"
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
