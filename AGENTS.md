# AGENTS.md - BestBox Development Guide

This file provides guidelines for AI agents working with the BestBox enterprise agentic applications demo kit.

## Build, Lint, and Test Commands

### Environment Setup
```bash
source ~/BestBox/activate.sh  # Activate venv and set ROCm environment variables
```

### Backend Testing
```bash
# Run all agent tests
python scripts/test_agents.py

# Run integration tests (fast mode - unit tests only)
./scripts/run_integration_tests.sh --fast

# Run integration tests (full mode - requires services)
./scripts/run_integration_tests.sh --full

# Run single test file
python scripts/test_agent_setup.py

# Run with coverage
./scripts/run_integration_tests.sh --coverage

# Run with verbose output
./scripts/run_integration_tests.sh --verbose
```

### Frontend Development
```bash
cd frontend/copilot-demo
npm run dev        # Start development server
npm run build      # Build for production
npm run start      # Start production server
npm run lint       # Run ESLint
```

### Service Management
```bash
# Infrastructure (run first)
docker compose up -d

# Individual services
./scripts/start-llm.sh        # LLM server on :8080
./scripts/start-embeddings.sh # Embeddings on :8081
./scripts/start-agent-api.sh   # Agent API on :8000
./scripts/start-s2s.sh         # S2S Gateway on :8765
```

## Code Style Guidelines

### Python Backend Code

#### Imports and Organization
- **Standard library imports first**: `import os`, `import sys`
- **Third-party imports second**: `from langchain_core...`, `import fastapi`
- **Local imports third**: `from agents.state import...`, `from tools.erp_tools...`
- Use absolute imports: `from agents.state import AgentState`
- Group related imports and sort alphabetically within groups

#### Type Annotations
- **Mandatory for all functions**: Use proper type hints
- **Preferred patterns**:
  ```python
  from typing import TypedDict, Annotated, List, Optional, Dict, Any
  
  def agent_node(state: AgentState) -> Dict[str, Any]:
      """Process agent request with proper typing."""
      pass
  
  @tool
  def get_data(
      param1: str, 
      param2: Optional[int] = None
  ) -> List[Dict[str, Any]]:
      """Tool with comprehensive type hints."""
      pass
  ```

#### Naming Conventions
- **Functions and variables**: `snake_case` (e.g., `get_purchase_orders`, `current_agent`)
- **Classes**: `PascalCase` (e.g., `AgentState`, `RouteDecision`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `ROUTER_SYSTEM_PROMPT`)
- **Private members**: Leading underscore (`_internal_helper`)

#### Error Handling
- **Use specific exceptions**: `ValueError`, `KeyError`, custom exceptions
- **Graceful degradation**: Check dependencies, provide fallbacks
- **Logging**: Use structured logging with context
- **Pattern**:
  ```python
  try:
      result = risky_operation()
      return result
  except SpecificError as e:
      logger.error(f"Operation failed: {e}", exc_info=True)
      return fallback_value()
  ```

#### Documentation
- **Docstrings for all functions**: Use triple quotes with Args/Returns
- **Type hints in docstrings**: Follow Google or NumPy style
- **Inline comments**: Explain business logic, not obvious code

### Frontend TypeScript/React Code

#### Imports and Organization
- **React imports first**: `import { useState, useEffect } from 'react'`
- **Third-party libraries second**: `import { CopilotKit } from "@copilotkit/react-core"`
- **Local imports third**: `import { VoiceButton } from "@/components/VoiceButton"`
- **Type imports**: Use `import type` for type-only imports

#### Component Patterns
- **Function components with TypeScript**:
  ```typescript
  interface VoiceButtonProps {
    serverUrl?: string;
    onTranscript?: (text: string) => void;
    disabled?: boolean;
  }
  
  export default function VoiceButton({
    serverUrl,
    onTranscript,
    disabled = false
  }: VoiceButtonProps) {
    // Component implementation
  }
  ```

#### Naming Conventions
- **Components**: `PascalCase` (e.g., `VoiceButton`, `ServiceStatusCard`)
- **Hooks**: `camelCase` starting with `use` (e.g., `useS2S`, `useServiceHealth`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `API_BASE_URL`)
- **Functions/variables**: `camelCase` (e.g., `handleClick`, `isConnected`)

#### TypeScript Patterns
- **Interfaces for props**: Always type component props
- **Enum-like types**: Use union types for constants
- **Generic types**: Prefer `Array<T>` over `T[]` for complex types
- **Optional properties**: Use `?` modifier

#### State Management
- **Local state**: `useState` for component state
- **Side effects**: `useEffect` with proper dependency arrays
- **Callbacks**: `useCallback` for event handlers
- **Custom hooks**: Extract complex logic into reusable hooks

### File Organization

#### Python Structure
```
agents/
├── __init__.py
├── state.py          # TypedDict state definitions
├── router.py         # Intent classification
├── erp_agent.py      # Domain-specific agent
└── graph.py          # LangGraph orchestration

tools/
├── erp_tools.py      # Domain tools with @tool decorator
├── rag_tools.py      # RAG integration
└── __init__.py

services/
├── agent_api.py      # FastAPI backend
└── embeddings/main.py # BGE-M3 embeddings service
```

#### Frontend Structure
```
frontend/copilot-demo/
├── app/[locale]/           # Next.js pages
├── components/            # React components
├── hooks/                 # Custom React hooks
├── lib/                   # Utilities and clients
└── api/                   # API routes
```

## Testing Guidelines

### Unit Testing
- **Test files**: Name `test_*.py` or `*_test.py`
- **Use pytest**: With async support for FastAPI
- **Mock external services**: Use `unittest.mock`
- **Coverage goal**: >80% for critical paths

### Integration Testing
- **Service dependencies**: Check service availability before testing
- **Environment isolation**: Use test configurations
- **Data cleanup**: Reset state between tests
- **End-to-end**: Test complete user flows

## Key Development Practices

### Agent Development
- **State management**: Use `AgentState` TypedDict consistently
- **Tool definitions**: Use `@tool` decorator with proper docstrings
- **Error recovery**: Handle tool failures gracefully
- **Context management**: Use sliding window for long conversations

### Frontend Development
- **Component composition**: Build reusable, composable components
- **Type safety**: Strict TypeScript configuration
- **Performance**: Use React.memo, useMemo, useCallback appropriately
- **Accessibility**: Include ARIA labels and keyboard navigation

### Service Integration
- **Health checks**: Implement `/health` endpoints
- **Graceful degradation**: Handle service unavailability
- **Configuration**: Use environment variables for all settings
- **Logging**: Structured logs with correlation IDs

## Common Patterns

### Async/Await Usage
```python
async def process_request(state: AgentState):
    llm = get_llm()
    result = await llm.ainvoke(state["messages"])
    return {"messages": [result]}
```

### Tool Implementation
```python
@tool
def get_data(param: str) -> Dict[str, Any]:
    """Get data with proper error handling."""
    try:
        data = fetch_data(param)
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### React Hook Pattern
```typescript
export function useCustomHook(options: Options) {
  const [state, setState] = useState<State>(initialState);
  
  const handleAction = useCallback(async () => {
    // Async operation
  }, [dependency]);
  
  return { state, handleAction };
}
```

## Environment Variables

### Backend Services
- `HSA_OVERRIDE_GFX_VERSION=11.0.0` # AMD GPU support
- `PYTORCH_ROCM_ARCH=gfx1100`
- `LLM_HOST=localhost:8080`
- `EMBEDDINGS_HOST=localhost:8081`

### Frontend
- `NEXT_PUBLIC_USE_LIVEKIT=true/false`
- `NEXT_PUBLIC_S2S_SERVER_URL=ws://localhost:8765`

## Git Workflow

### Branching
- **main**: Stable deployment branch
- **develop**: Integration branch
- **feature/***: Feature-specific branches

### Commit Messages
- **Format**: `type(scope): description`
- **Types**: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- **Examples**:
  - `feat(agents): add CRM agent integration`
  - `fix(frontend): resolve voice button state issue`
  - `docs(README): update deployment instructions`