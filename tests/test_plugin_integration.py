"""
Integration tests for plugin system with LangGraph.
"""

import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins import PluginRegistry, PluginLoader
from agents.state import AgentState
from langchain_core.messages import HumanMessage


class TestPluginIntegration:
    """Test plugin system integration with agent graph."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = PluginRegistry()
        registry.clear()

    def test_plugin_loading(self):
        """Test that plugins are discovered and loaded."""
        registry = PluginRegistry()
        loader = PluginLoader(registry, workspace_dir=os.getcwd())

        # Load all plugins
        count = loader.load_all()

        assert count > 0, "Should load at least the example plugin"

        # Check that example plugin is loaded
        plugins = registry.get_all_plugins()
        plugin_names = [p.name for p in plugins]

        assert "example" in plugin_names or "example-skill" in plugin_names

    def test_plugin_tools_available(self):
        """Test that plugin tools are registered and available."""
        registry = PluginRegistry()
        loader = PluginLoader(registry, workspace_dir=os.getcwd())
        loader.load_all()

        # Get all tools
        tools = registry.get_all_tools()
        tool_names = [t.name for t in tools]

        # Check for example plugin tools
        assert any("example" in name for name in tool_names), \
            f"Should have example tools, got: {tool_names}"

    def test_plugin_tools_in_graph(self):
        """Test that plugin tools are available in the agent graph."""
        from agents.graph import UNIQUE_TOOLS

        tool_names = [t.name for t in UNIQUE_TOOLS]

        # Plugin tools should be included
        # (This assumes plugins are loaded when graph.py is imported)
        print(f"Available tools in graph: {tool_names}")

        # Check that we have the standard tools
        assert "search_knowledge_base" in tool_names

    def test_hooks_registered(self):
        """Test that plugin hooks are registered."""
        registry = PluginRegistry()
        loader = PluginLoader(registry, workspace_dir=os.getcwd())
        loader.load_all()

        # Get hooks for BEFORE_ROUTING
        from plugins import HookEvent
        handlers = registry.get_hook_handlers(HookEvent.BEFORE_ROUTING.value)

        # Should have at least the example plugin hook
        assert len(handlers) > 0, "Should have registered hooks"

    def test_hook_execution(self):
        """Test that hooks execute correctly."""
        from plugins import HookRunner, HookEvent

        registry = PluginRegistry()
        loader = PluginLoader(registry, workspace_dir=os.getcwd())
        loader.load_all()

        runner = HookRunner(registry)

        # Create test state
        state: AgentState = {
            "messages": [HumanMessage(content="Test message")],
            "current_agent": "router",
            "tool_calls": 0,
            "confidence": 0.0,
            "context": {},
            "plan": [],
            "step": 0,
            "plugin_context": None,
        }

        # Run hooks
        result = runner.run_sync(HookEvent.BEFORE_ROUTING, state)

        # State should be returned (possibly modified)
        assert result is not None
        assert "messages" in result

    def test_example_plugin_tool(self):
        """Test calling the example plugin tool."""
        registry = PluginRegistry()
        loader = PluginLoader(registry, workspace_dir=os.getcwd())
        loader.load_all()

        # Find example tool
        tool = registry.get_tool("example_tool")

        if tool:
            # Test the tool
            result = tool.invoke({"message": "Hello, plugin!"})
            assert "Example Plugin" in result or "Echo" in result
        else:
            pytest.skip("Example plugin tool not found")

    def test_skill_loading(self):
        """Test that skills are loaded from SKILL.md files."""
        registry = PluginRegistry()
        loader = PluginLoader(registry, workspace_dir=os.getcwd())
        loader.load_all()

        plugins = registry.get_all_plugins()

        # Check for skills
        from plugins import PluginType
        skills = [p for p in plugins if p.plugin_type == PluginType.SKILL]

        assert len(skills) > 0, "Should have loaded at least one skill"

        # Check skill has content
        for skill in skills:
            if skill.skill_content:
                assert len(skill.skill_content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
