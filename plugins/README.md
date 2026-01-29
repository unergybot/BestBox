# BestBox Plugin System

The BestBox plugin system provides an extensible framework for adding tools, lifecycle hooks, communication channels, and HTTP routes to the multi-agent system.

## Quick Start

### Verify Plugin System

```bash
python scripts/verify_plugin_system.py
```

### Run Tests

```bash
pytest tests/test_plugins.py tests/test_plugin_integration.py -v
```

## Architecture

```
plugins/
├── __init__.py          # Package exports
├── manifest.py          # Data structures (PluginManifest, ToolDefinition, etc.)
├── api.py               # PluginAPI for plugin authors
├── loader.py            # Plugin discovery and loading
├── hooks.py             # Lifecycle hook execution
├── skill_loader.py      # SKILL.md parser
├── registry.py          # Central registry singleton
└── utils.py             # Requirement checking utilities
```

## Plugin Types

### 1. Skills (SKILL.md)

Lightweight plugins defined with YAML frontmatter:

**Location**: `skills/<skill-name>/SKILL.md`

**Format**:
```yaml
---
name: my-skill
description: My custom skill
version: 1.0.0
requires:
  bins: [git]
  python_packages: [requests]
  env_vars: [API_KEY]
tools:
  - name: my_tool
    description: Tool description
    parameters:
      type: object
      properties:
        query: {type: string}
hooks:
  - event: BEFORE_ROUTING
    handler: skills.my_skill.hooks.handler
    priority: 100
---

# Skill Documentation

This skill does X, Y, and Z...
```

**Optional Python Module** (`skills/my-skill/__init__.py`):
```python
def my_tool(query: str) -> str:
    return f"Result: {query}"

def register(api):
    api.register_tool(
        name="my_tool",
        description="Tool description",
        func=my_tool,
    )
```

### 2. Full Plugins (bestbox.plugin.json)

Complete Python modules with manifest:

**Location**: `plugins_contrib/<plugin-name>/`

**Manifest** (`bestbox.plugin.json`):
```json
{
  "name": "my-plugin",
  "description": "My custom plugin",
  "version": "1.0.0",
  "requires": {
    "bins": ["docker"],
    "python_packages": ["fastapi"],
    "env_vars": ["API_KEY"]
  },
  "tools": [
    {
      "name": "my_tool",
      "description": "Tool description",
      "parameters": {"type": "object"}
    }
  ],
  "hooks": [
    {
      "event": "BEFORE_ROUTING",
      "handler": "plugins_contrib.my_plugin.hooks.handler",
      "priority": 100
    }
  ]
}
```

**Module** (`__init__.py`):
```python
def my_tool(query: str) -> str:
    return f"Result: {query}"

def register(api):
    """Called by PluginLoader."""
    api.register_tool(
        name="my_tool",
        description="Tool description",
        func=my_tool,
    )
```

## Lifecycle Hooks

Hooks allow plugins to intercept agent execution at specific points:

### Available Events

- `BEFORE_AGENT_START` - Before agent system starts
- `MESSAGE_RECEIVED` - When user message is received
- `BEFORE_ROUTING` - Before router classifies intent
- `AFTER_ROUTING` - After router determines target agent
- `BEFORE_TOOL_CALL` - Before tools are executed
- `AFTER_TOOL_CALL` - After tools complete
- `BEFORE_RESPONSE` - Before sending response to user
- `AFTER_RESPONSE` - After response is sent
- `ON_ERROR` - When an error occurs
- `ON_SHUTDOWN` - During system shutdown

### Hook Handler

```python
def my_hook(context):
    """
    Hook handler.

    Args:
        context: HookContext with event, state, plugin_name, metadata

    Returns:
        Modified state dict or None to keep unchanged
    """
    # Access current state
    messages = context.state.get("messages", [])

    # Optionally modify state
    modified_state = context.state.copy()
    modified_state["custom_field"] = "value"

    return modified_state  # or None
```

### Priority

Hooks execute in priority order (lower = earlier):
- 50: High priority (runs first)
- 100: Normal priority (default)
- 200: Low priority (runs last)

## PluginAPI Reference

### `register_tool(name, description, func, parameters=None)`

Register a tool for LangGraph.

```python
api.register_tool(
    name="my_tool",
    description="Tool description",
    func=my_tool_function,
)
```

### `register_hook(event, handler, priority=100)`

Register a lifecycle hook.

```python
from plugins import HookEvent

api.register_hook(
    event=HookEvent.BEFORE_ROUTING,
    handler=my_hook_function,
    priority=100,
)
```

### `register_channel(channel_type, config)`

Register a communication channel.

```python
api.register_channel(
    channel_type="slack",
    config={"token": "xoxb-...", "channel": "#general"},
)
```

### `register_http_route(route, handler, methods=["GET"])`

Register a FastAPI HTTP route.

```python
async def my_endpoint(request: Request):
    return {"status": "ok"}

api.register_http_route(
    route="/api/custom",
    handler=my_endpoint,
    methods=["GET", "POST"],
)
```

## Discovery

Plugins are discovered from multiple sources with priority (later overrides earlier):

1. **Bundled** - `skills/`, `plugins_contrib/` in project root
2. **Global** - `~/.bestbox/plugins/`
3. **Workspace** - `.bestbox/plugins/` in current directory
4. **Config-specified** - Additional paths from configuration

## Requirements

Plugins can specify requirements that are checked before loading:

```yaml
requires:
  bins: [git, docker]           # Binary executables in PATH
  python_packages: [requests]   # Importable Python packages
  env_vars: [API_KEY]            # Environment variables
```

Plugins with unmet requirements are skipped with a warning.

## Integration

### With LangGraph

Plugin tools are automatically merged with agent tools:

```python
from agents.graph import UNIQUE_TOOLS  # Includes plugin tools
```

### With Agent State

Plugins can use `plugin_context` in AgentState:

```python
state["plugin_context"] = {
    "active_plugins": ["my-plugin"],
    "tool_results": {"my_tool": {...}},
    "hook_data": {"custom_key": "value"},
}
```

### With FastAPI

Plugin HTTP routes are registered on startup:

```python
# Plugins loaded before graph import
from plugins import PluginRegistry, PluginLoader
loader = PluginLoader(PluginRegistry())
loader.load_all()

# Graph now has plugin tools
from agents.graph import app as agent_app
```

## Examples

See:
- `plugins_contrib/example/` - Full plugin example
- `skills/example/` - Skill example
- `tests/test_plugins.py` - Unit tests
- `tests/test_plugin_integration.py` - Integration tests

## Documentation

- **User Guide**: `../docs/PLUGIN_SYSTEM.md`
- **Implementation**: `../PLUGIN_SYSTEM_IMPLEMENTATION.md`
- **API Reference**: See docstrings in source files

## Module Overview

### `manifest.py`

Data structures for plugin definitions:
- `PluginType` - Enum for SKILL vs PLUGIN
- `Requirement` - Binary/package/env requirements
- `ToolDefinition` - Tool metadata
- `HookDefinition` - Hook metadata
- `PluginManifest` - Complete plugin definition

### `registry.py`

Singleton registry managing all plugins:
- `register_plugin()` - Add plugin manifest
- `register_tool()` - Add LangChain tool
- `register_hook()` - Add lifecycle hook
- `get_all_tools()` - Get tools for LangGraph
- `get_hook_handlers()` - Get hooks for event

### `loader.py`

Plugin discovery and loading:
- `discover_all()` - Find all plugins
- `load_plugin()` - Load single plugin
- `load_all()` - Discover and load all

### `hooks.py`

Hook execution engine:
- `run()` - Execute hooks asynchronously
- `run_sync()` - Execute hooks synchronously

### `skill_loader.py`

SKILL.md parser:
- `discover_skills()` - Find SKILL.md files
- `parse_skill()` - Parse YAML frontmatter
- `load_skill_module()` - Import Python module

### `api.py`

Plugin author API:
- `HookEvent` - Enum of lifecycle events
- `HookContext` - Context passed to hooks
- `PluginAPI` - Registration interface

### `utils.py`

Utility functions:
- `check_binary_available()` - Check for binary in PATH
- `check_env_var()` - Check environment variable
- `check_python_package()` - Check importable package
- `check_all_requirements()` - Validate all requirements
