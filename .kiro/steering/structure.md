# BestBox Project Structure

## Root Directory Layout

```
BestBox/
├── agents/                    # Multi-agent system core
├── services/                  # Backend services and APIs
├── tools/                     # Enterprise integration tools
├── frontend/                  # React/Next.js user interfaces
├── scripts/                   # Deployment and utility scripts
├── tests/                     # Comprehensive test suite
├── docs/                      # Documentation and guides
├── config/                    # Configuration files
├── data/                      # Demo data and knowledge base
├── migrations/                # Database schema migrations
└── third_party/               # External dependencies
```

## Core Directories

### `/agents/` - Multi-Agent System
- **`router.py`**: Query classification and agent routing
- **`erp_agent.py`**: ERP/Finance operations agent
- **`crm_agent.py`**: CRM/Sales operations agent
- **`it_ops_agent.py`**: IT Operations and monitoring agent
- **`oa_agent.py`**: Office Automation workflow agent
- **`general_agent.py`**: General queries and help agent
- **`graph.py`**: LangGraph state machine definition
- **`state.py`**: Shared agent state management
- **`context_manager.py`**: Context window management
- **`utils.py`**: Common agent utilities

### `/services/` - Backend Services
- **`agent_api.py`**: FastAPI endpoint for agent interactions
- **`livekit_agent.py`**: LiveKit voice agent service
- **`observability.py`**: Metrics and tracing service
- **`embeddings/`**: Text embedding service
- **`rag_pipeline/`**: Retrieval-Augmented Generation pipeline
- **`speech/`**: Speech-to-speech processing services

### `/tools/` - Enterprise Integrations
- **`erp_tools.py`**: Vendor, inventory, procurement tools
- **`crm_tools.py`**: Customer, sales pipeline tools
- **`it_ops_tools.py`**: Server monitoring, log analysis tools
- **`oa_tools.py`**: Leave requests, approval workflow tools
- **`rag_tools.py`**: Knowledge base search and retrieval tools

### `/frontend/` - User Interfaces
- **`copilot-demo/`**: Main CopilotKit chat interface
  - React components for AI chat
  - LiveKit voice integration
  - Generative UI components
  - Mobile-responsive design

### `/scripts/` - Automation & Deployment
- **`start-all-services.sh`**: Orchestrated service startup
- **`start-*.sh`**: Individual service startup scripts
- **`test-*.sh`**: Testing and validation scripts
- **`seed_*.py`**: Data seeding utilities
- **`verify-*.sh`**: Health check and verification scripts

### `/tests/` - Test Suite
- **`test_integration_full.py`**: End-to-end integration tests
- **`test_rag_integration.py`**: RAG pipeline tests
- **`test_*.py`**: Component-specific test files
- **`fixtures/`**: Test data and mock objects

## Configuration Structure

### `/config/` - Service Configuration
- **`grafana/`**: Dashboard and provisioning configs
- **`prometheus/`**: Metrics collection and alerting rules
- **`otel-collector-config.yaml`**: OpenTelemetry configuration

### Environment Files
- **`.env`**: Main environment variables
- **`.env.observability`**: Observability-specific settings
- **`docker-compose.yml`**: Infrastructure service definitions

## Data Organization

### `/data/` - Application Data
- **`demo/`**: Demo scenario data
- **`demo_docs/`**: Knowledge base documents by domain
  - `crm/`: Customer and sales documents
  - `erp/`: Financial and procurement documents
  - `itops/`: IT operations documentation
  - `oa/`: Office automation procedures
- **`audio/`**: Audio processing test files

## Documentation Structure

### `/docs/` - Project Documentation
- **`system_design.md`**: Complete architecture specification (800+ lines)
- **`rocm_deployment_guide.md`**: ROCm installation and setup
- **`TESTING_GUIDE.md`**: Comprehensive testing documentation
- **`LIVEKIT_DEPLOYMENT.md`**: Voice integration setup
- **`E2E_LIVEKIT_INTEGRATION.md`**: End-to-end integration guide
- **`plans/`**: Development and deployment plans

## Naming Conventions

### File Naming
- **Python modules**: `snake_case.py`
- **Configuration files**: `kebab-case.yaml` or `snake_case.json`
- **Scripts**: `kebab-case.sh` or `snake_case.py`
- **Documentation**: `UPPER_CASE.md` for guides, `snake_case.md` for specs

### Code Organization
- **Classes**: `PascalCase`
- **Functions/variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Agent nodes**: `{domain}_agent` (e.g., `erp_agent`, `crm_agent`)

### Service Naming
- **Container names**: `bestbox-{service}` (e.g., `bestbox-qdrant`)
- **Service ports**: Consistent port allocation
  - 8000-8099: Application services
  - 6000-6999: Databases and storage
  - 3000-3999: Frontend and UI services
  - 9000-9999: Monitoring and observability

## Import Patterns

### Agent Imports
```python
from agents.state import AgentState
from agents.utils import get_llm
from agents.context_manager import apply_sliding_window
```

### Service Imports
```python
from services.rag_pipeline import RAGPipeline
from tools.{domain}_tools import {ToolClass}
```

### Configuration Imports
```python
import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
```

## Development Workflow

1. **Feature Development**: Start in `/agents/` or `/tools/`
2. **Service Integration**: Add endpoints in `/services/`
3. **Frontend Integration**: Update React components in `/frontend/`
4. **Testing**: Add tests in `/tests/` with appropriate fixtures
5. **Documentation**: Update relevant files in `/docs/`
6. **Deployment**: Use scripts in `/scripts/` for service management