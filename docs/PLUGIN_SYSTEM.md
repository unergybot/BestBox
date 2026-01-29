# BestBox Plugin System

The BestBox plugin system provides an extensible framework for adding tools, lifecycle hooks, communication channels, and HTTP routes to the agent system.

## Overview

The plugin system supports two types of plugins:

1. **Skills** - Lightweight plugins defined via `SKILL.md` files with YAML frontmatter
2. **Full Plugins** - Complete Python modules with `bestbox.plugin.json` manifests

## Architecture

```
plugins/                    # Core plugin system
├── __init__.py
├── manifest.py             # Data structures for plugin manifests
├── api.py                  # PluginAPI for registration
├── loader.py               # Plugin discovery and loading
├── hooks.py                # Lifecycle hook execution
├── skill_loader.py         # SKILL.md parser
├── registry.py             # Central registry
└── utils.py                # Requirement checking

skills/                     # Skill.md files
plugins_contrib/            # Full plugin modules
```

## Discovery Priority

Plugins are discovered from multiple sources, with later sources overriding earlier ones:

1. **Bundled** - `skills/`, `plugins_contrib/` in project root
2. **Global** - `~/.bestbox/plugins/`
3. **Workspace** - `.bestbox/plugins/` in current directory
4. **Config-specified** - Additional paths from configuration

## Creating a Skill

Skills are defined using a `SKILL.md` file with YAML frontmatter:

```markdown
---
name: my-skill
description: My custom skill
version: 1.0.0
author: Your Name
requires:
  bins: [git, jq]
  python_packages: [requests]
  env_vars: [GITHUB_TOKEN]
tools:
  - name: my_tool
    description: Tool description
    parameters:
      type: object
      properties:
        query:
          type: string
          description: Search query
      required:
        - query
hooks:
  - event: BEFORE_ROUTING
    handler: skills.my_skill.hooks.before_routing
    priority: 100
---

# My Skill

Skill content and documentation goes here.
```

### Skill Directory Structure

```
skills/my-skill/
├── SKILL.md              # Required: Skill definition
├── __init__.py           # Optional: Python module with register()
└── hooks.py              # Optional: Hook handler functions
```

### Skill Python Module

Optionally provide a Python module with a `register()` function:

```python
# skills/my_skill/__init__.py

def my_tool(query: str) -> str:
    """Tool implementation."""
    return f"Results for: {query}"

def register(api):
    """Called by PluginLoader."""
    api.register_tool(
        name="my_tool",
        description="Tool description",
        func=my_tool,
    )
```

## Creating a Full Plugin

Full plugins use `bestbox.plugin.json` manifests:

```json
{
  "name": "my-plugin",
  "description": "My custom plugin",
  "version": "1.0.0",
  "author": "Your Name",
  "requires": {
    "bins": ["docker"],
    "python_packages": ["fastapi"],
    "env_vars": ["API_KEY"]
  },
  "tools": [
    {
      "name": "my_tool",
      "description": "Tool description",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {"type": "string"}
        }
      }
    }
  ],
  "hooks": [
    {
      "event": "BEFORE_ROUTING",
      "handler": "plugins_contrib.my_plugin.hooks.before_routing",
      "priority": 100
    }
  ]
}
```

### Plugin Directory Structure

```
plugins_contrib/my-plugin/
├── bestbox.plugin.json   # Required: Plugin manifest
├── __init__.py           # Required: Module with register()
└── hooks.py              # Optional: Hook handlers
```

### Plugin Module

```python
# plugins_contrib/my_plugin/__init__.py

def my_tool(query: str) -> str:
    """Tool implementation."""
    return f"Results for: {query}"

def register(api):
    """
    Called by PluginLoader with PluginAPI instance.

    Args:
        api: PluginAPI for registration
    """
    # Register tool
    api.register_tool(
        name="my_tool",
        description="Tool description",
        func=my_tool,
    )

    # Register HTTP route (optional)
    from fastapi import Request

    async def custom_endpoint(request: Request):
        return {"status": "ok"}

    api.register_http_route(
        route="/api/my-plugin/status",
        handler=custom_endpoint,
        methods=["GET"],
    )

    api.log_info("My plugin initialized")
```

## Lifecycle Hooks

Hooks allow plugins to intercept and modify agent behavior at specific points:

### Available Hook Events

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
# plugins_contrib/my_plugin/hooks.py

def before_routing(context):
    """
    Hook handler for BEFORE_ROUTING event.

    Args:
        context: HookContext with:
            - event: HookEvent enum value
            - state: Current AgentState dict
            - plugin_name: Name of this plugin
            - metadata: Event-specific metadata

    Returns:
        Modified state dict or None to keep unchanged
    """
    # Access state
    messages = context.state.get("messages", [])

    # Optionally modify state
    modified_state = context.state.copy()
    modified_state["custom_field"] = "value"

    return modified_state  # or None
```

### Hook Priority

Hooks are executed in priority order (lower number = earlier execution):

```yaml
hooks:
  - event: BEFORE_ROUTING
    handler: my_plugin.hooks.handler
    priority: 50  # Runs before priority 100
```

## PluginAPI Reference

The `PluginAPI` class provides methods for plugin registration:

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
    config={
        "token": "xoxb-...",
        "channel": "#general",
    },
)
```

### `register_http_route(route, handler, methods=["GET"])`

Register a FastAPI HTTP route.

```python
async def my_endpoint(request: Request):
    return {"data": "value"}

api.register_http_route(
    route="/api/custom",
    handler=my_endpoint,
    methods=["GET", "POST"],
)
```

## Requirements

Plugins can specify requirements that are checked before loading:

```yaml
requires:
  bins: [git, docker]           # Binary executables
  python_packages: [requests]   # Python packages
  env_vars: [API_KEY]            # Environment variables
```

If requirements are not met, the plugin is skipped with a warning.

## Testing

Run plugin system tests:

```bash
pytest tests/test_plugins.py -v
```

## Integration with LangGraph

Plugins integrate seamlessly with the agent system:

1. **Tools** - Plugin tools are merged with agent tools and available to all agents
2. **Hooks** - Execute at defined lifecycle points in `agents/graph.py`
3. **State** - Hooks can modify `AgentState` including `plugin_context`

### Plugin Context in State

```python
from agents.state import AgentState

state: AgentState = {
    "messages": [...],
    "current_agent": "erp_agent",
    "plugin_context": {
        "active_plugins": ["my-plugin"],
        "tool_results": {"my_tool": {...}},
        "hook_data": {"custom_key": "value"},
    },
}
```

## Example: GitHub Integration Plugin

```python
# plugins_contrib/github/bestbox.plugin.json
{
  "name": "github",
  "description": "GitHub API integration",
  "version": "1.0.0",
  "requires": {
    "bins": ["git"],
    "env_vars": ["GITHUB_TOKEN"]
  },
  "tools": [
    {
      "name": "search_github_repos",
      "description": "Search GitHub repositories",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {"type": "string"}
        }
      }
    }
  ]
}

# plugins_contrib/github/__init__.py
import requests
import os

def search_github_repos(query: str) -> str:
    """Search GitHub repositories."""
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"token {token}"}

    response = requests.get(
        f"https://api.github.com/search/repositories?q={query}",
        headers=headers,
    )

    data = response.json()
    repos = data.get("items", [])[:5]

    return "\n".join([f"- {r['full_name']}: {r['description']}" for r in repos])

def register(api):
    api.register_tool(
        name="search_github_repos",
        description="Search GitHub repositories",
        func=search_github_repos,
    )
```

## Best Practices

1. **Naming** - Use descriptive, unique names for plugins and tools
2. **Requirements** - Always specify requirements to prevent runtime errors
3. **Error Handling** - Handle errors gracefully in tools and hooks
4. **Logging** - Use `api.log_info()`, `api.log_warning()`, `api.log_error()`
5. **State Modification** - Only modify state in hooks when necessary
6. **Priority** - Use appropriate hook priorities (50 for early, 100 default, 200 for late)
7. **Testing** - Write unit tests for plugin functionality

## Troubleshooting

### Plugin Not Loading

Check logs for:
- Unmet requirements (missing binaries, packages, env vars)
- Syntax errors in manifest files
- Import errors in Python modules

### Tool Not Available

Verify:
- Tool is registered in `register()` function
- No name collision with existing tools
- Plugin loaded successfully (check startup logs)

### Hook Not Firing

Ensure:
- Event name matches `HookEvent` enum value
- Handler path is correct (importable)
- Hook registered with correct priority
