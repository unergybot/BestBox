# BestBox Technology Stack

## Core Architecture

### AI & ML Stack
- **LLM**: Qwen2.5-14B-Instruct (locally deployed)
- **Embeddings**: BGE-M3 (1024-dimensional vectors)
- **Inference Engine**: vLLM with ROCm support
- **Agent Framework**: LangGraph for multi-agent coordination
- **Vector Database**: Qdrant for semantic search and RAG

### Backend Technologies
- **Language**: Python 3.12+
- **Web Framework**: FastAPI with async support
- **Agent Orchestration**: LangGraph state machines
- **Database**: PostgreSQL 16 (primary), MariaDB (ERPNext)
- **Cache**: Redis 7
- **Message Queue**: Redis-based queuing

### Frontend Technologies
- **Framework**: React with Next.js
- **AI Integration**: CopilotKit for chat interfaces
- **Voice**: LiveKit for WebRTC voice communication
- **UI Components**: Generative UI with streaming responses

### Infrastructure
- **GPU Runtime**: ROCm 7.2.0 with HIP support
- **Containerization**: Docker Compose orchestration
- **Observability**: OpenTelemetry, Prometheus, Grafana, Jaeger
- **Hardware**: AMD Ryzen AI Max+ 395 with Radeon 8060S

## Build System & Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-s2s.txt  # For speech-to-speech features

# Install Node.js dependencies
cd frontend/copilot-demo
npm install
```

### Service Management
```bash
# Start all backend services
./scripts/start-all-services.sh

# Start individual services
./scripts/start-llm.sh          # Local LLM server
./scripts/start-embeddings.sh   # Embedding service
./scripts/start-reranker.sh     # Reranker service
./scripts/start-livekit.sh      # LiveKit voice server

# Start frontend
./scripts/start-frontend.sh

# Start LiveKit agent
python services/livekit_agent.py dev
```

### Docker Services
```bash
# Start infrastructure services
docker compose up -d

# View service logs
docker compose logs -f qdrant
docker compose logs -f postgres

# Stop all services
docker compose down
```

### Testing
```bash
# Fast tests (no service dependencies)
./scripts/run_integration_tests.sh --fast

# Full integration tests (requires running services)
./scripts/run_integration_tests.sh --full

# With coverage report
./scripts/run_integration_tests.sh --fast --coverage

# End-to-end LiveKit tests
./scripts/test_e2e_livekit.sh
```

### Development Utilities
```bash
# Seed knowledge base with demo data
python scripts/seed_knowledge_base.py

# Seed demo data for agents
python scripts/seed_demo_data.py

# Monitor GPU usage
watch -n 2 rocm-smi

# Check service health
curl http://localhost:8000/health  # Agent API
curl http://localhost:8080/health  # LLM server
curl http://localhost:6333/health  # Qdrant
```

## Key Libraries & Frameworks

### Python Dependencies
- **langgraph**: Multi-agent orchestration and state management
- **langchain-core**: Core LangChain abstractions
- **fastapi**: Modern async web framework
- **pydantic**: Data validation and serialization
- **qdrant-client**: Vector database client
- **faster-whisper**: Speech recognition
- **TTS**: Text-to-speech synthesis

### Node.js Dependencies
- **@copilotkit/react-core**: AI chat integration
- **@livekit/components-react**: Voice communication components
- **next**: React framework with SSR support

## Environment Variables

### Required Configuration
```bash
# ROCm GPU Configuration
export ROCM_PATH=/opt/rocm-7.2.0
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100

# Service URLs
export LLM_BASE_URL=http://localhost:8080
export QDRANT_URL=http://localhost:6333
export POSTGRES_URL=postgresql://bestbox:bestbox@localhost:5432/bestbox

# LiveKit Configuration
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret
```

## Performance Targets

- **LLM Latency (P50)**: <500ms first token for 2K context
- **LLM Latency (P99)**: <2s first token for 8K context
- **Throughput**: 30-50 tokens/second (single user, 14B model)
- **Embedding**: <100ms for 512 tokens to 1024-dim vector
- **Vector Search**: <50ms for top-10 results from 100K documents
- **E2E Response**: <3s for simple query with 1 tool call
- **Concurrent Users**: 5-8 users sharing 14B model instance