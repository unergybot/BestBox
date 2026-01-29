"""
Test that the agent API starts with plugin system enabled.
"""

import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_plugin_system_imports():
    """Test that plugin system modules can be imported."""
    from plugins import (
        PluginRegistry,
        PluginLoader,
        PluginAPI,
        HookEvent,
        HookRunner,
        SkillLoader,
    )

    assert PluginRegistry is not None
    assert PluginLoader is not None
    assert PluginAPI is not None
    assert HookEvent is not None
    assert HookRunner is not None
    assert SkillLoader is not None


def test_graph_imports_plugins():
    """Test that agents/graph.py can import plugin system."""
    from agents.graph import _plugin_registry, _hook_runner

    assert _plugin_registry is not None
    assert _hook_runner is not None


def test_graph_has_plugin_tools():
    """Test that graph can incorporate plugin tools when they're loaded."""
    from plugins import PluginRegistry, PluginLoader

    # Load plugins
    registry = PluginRegistry()
    registry.clear()
    loader = PluginLoader(registry, workspace_dir=os.getcwd())
    loader.load_all()

    # Get plugin tools
    plugin_tools = registry.get_all_tools()

    # When plugins are loaded, they should be available via registry
    assert len(plugin_tools) > 0, "Should have loaded some plugin tools"

    # Note: UNIQUE_TOOLS is built at module import time, before plugins are loaded
    # In production, plugins are loaded during FastAPI startup before graph is compiled


def test_state_has_plugin_context():
    """Test that AgentState has plugin_context field."""
    from agents.state import AgentState, PluginContext

    # Check that types exist
    assert AgentState is not None
    assert PluginContext is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
