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

echo -e "${YELLOW}=== Tier 2: LLM Inference Services ===${NC}"

# Start LLM server
if is_running "llama-server"; then
    echo -e "${YELLOW}LLM server already running${NC}"
else
    echo "Starting LLM server..."
    ./scripts/start-llm.sh &
    sleep 2
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

echo -e "${GREEN}✓ Tier 2 complete${NC}"
echo ""

echo -e "${YELLOW}=== Tier 3: Optional Services ===${NC}"

# Start S2S Gateway (optional)
if [ "${SKIP_S2S:-false}" = "true" ]; then
    echo -e "${YELLOW}Skipping S2S (SKIP_S2S=true)${NC}"
else
    if is_running "services.speech.s2s_server"; then
        echo -e "${YELLOW}S2S Gateway already running${NC}"
    else
        echo "Starting S2S Gateway (TTS disabled by default)..."
        export S2S_ENABLE_TTS=false  # Disable TTS to prevent hang
        ./scripts/start-s2s.sh &
        sleep 2
    fi

    if ! check_health "S2S Gateway" "http://localhost:8765/health" 30; then
        echo -e "${YELLOW}Warning: S2S Gateway not responding (optional service)${NC}"
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
echo "  S2S Gateway:    http://localhost:8765/health"
echo "  Qdrant:         http://localhost:6333/healthz"
echo "  Frontend:       http://localhost:3000 (start separately with 'cd frontend/copilot-demo && npm run dev')"
echo ""
echo "To stop services:"
echo "  - Docker services: docker compose down"
echo "  - Python services: pkill -f 'llama-server|embeddings|agent_api|s2s_server'"
echo ""
echo -e "${YELLOW}Note: Services are running in background. Check individual terminals for logs.${NC}"
