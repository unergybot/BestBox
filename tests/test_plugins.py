"""
Tests for the plugin system.
"""

import pytest
import tempfile
import json
from pathlib import Path

from plugins import (
    PluginRegistry,
    PluginLoader,
    PluginAPI,
    HookEvent,
    HookRunner,
    SkillLoader,
    PluginManifest,
    PluginType,
    Requirement,
)


class TestPluginRegistry:
    """Test PluginRegistry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = PluginRegistry()
        registry.clear()

    def test_singleton(self):
        """Test that PluginRegistry is a singleton."""
        registry1 = PluginRegistry()
        registry2 = PluginRegistry()
        assert registry1 is registry2

    def test_register_plugin(self):
        """Test plugin registration."""
        registry = PluginRegistry()
        manifest = PluginManifest(
            name="test-plugin",
            description="Test plugin",
            version="1.0.0",
            plugin_type=PluginType.PLUGIN,
        )

        assert registry.register_plugin(manifest) is True
        assert registry.get_plugin("test-plugin") is not None

        # Duplicate registration should fail
        assert registry.register_plugin(manifest) is False

    def test_register_tool(self):
        """Test tool registration."""
        from langchain_core.tools import StructuredTool

        registry = PluginRegistry()

        def dummy_func(x: str) -> str:
            return x

        tool = StructuredTool.from_function(
            func=dummy_func,
            name="test_tool",
            description="Test tool",
        )

        assert registry.register_tool("test-plugin", tool) is True
        assert registry.get_tool("test_tool") is not None
        assert len(registry.get_all_tools()) == 1

    def test_register_hook(self):
        """Test hook registration."""
        registry = PluginRegistry()

        def dummy_hook(context):
            return None

        registry.register_hook(
            "test-plugin",
            HookEvent.BEFORE_ROUTING.value,
            dummy_hook,
            priority=100,
        )

        handlers = registry.get_hook_handlers(HookEvent.BEFORE_ROUTING.value)
        assert len(handlers) == 1
        assert handlers[0]["plugin"] == "test-plugin"
        assert handlers[0]["priority"] == 100

    def test_hook_priority_sorting(self):
        """Test that hooks are sorted by priority."""
        registry = PluginRegistry()

        def hook1(context):
            return None

        def hook2(context):
            return None

        def hook3(context):
            return None

        # Register in random order
        registry.register_hook("plugin2", HookEvent.BEFORE_ROUTING.value, hook2, priority=200)
        registry.register_hook("plugin1", HookEvent.BEFORE_ROUTING.value, hook1, priority=100)
        registry.register_hook("plugin3", HookEvent.BEFORE_ROUTING.value, hook3, priority=300)

        handlers = registry.get_hook_handlers(HookEvent.BEFORE_ROUTING.value)
        assert len(handlers) == 3
        assert handlers[0]["plugin"] == "plugin1"  # Lowest priority first
        assert handlers[1]["plugin"] == "plugin2"
        assert handlers[2]["plugin"] == "plugin3"


class TestSkillLoader:
    """Test SkillLoader functionality."""

    def test_parse_skill(self):
        """Test parsing a SKILL.md file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "SKILL.md"
            skill_file.write_text("""---
name: test-skill
description: Test skill
version: 1.0.0
requires:
  bins: [git]
  python_packages: [requests]
  env_vars: [API_KEY]
tools:
  - name: test_tool
    description: Test tool
    parameters:
      type: object
      properties:
        query:
          type: string
hooks:
  - event: BEFORE_ROUTING
    handler: test.hooks.before_routing
    priority: 50
---

This is the skill content.
""")

            manifest = SkillLoader.parse_skill(skill_file)

            assert manifest is not None
            assert manifest.name == "test-skill"
            assert manifest.description == "Test skill"
            assert manifest.version == "1.0.0"
            assert manifest.plugin_type == PluginType.SKILL
            assert len(manifest.requires.bins) == 1
            assert len(manifest.requires.python_packages) == 1
            assert len(manifest.requires.env_vars) == 1
            assert len(manifest.tools) == 1
            assert manifest.tools[0].name == "test_tool"
            assert len(manifest.hooks) == 1
            assert manifest.hooks[0].event == "BEFORE_ROUTING"
            assert manifest.hooks[0].priority == 50
            assert "This is the skill content." in manifest.skill_content

    def test_discover_skills(self):
        """Test discovering SKILL.md files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested skill files
            skill1 = Path(tmpdir) / "skill1" / "SKILL.md"
            skill1.parent.mkdir()
            skill1.write_text("---\nname: skill1\n---\nContent")

            skill2 = Path(tmpdir) / "nested" / "skill2" / "SKILL.md"
            skill2.parent.mkdir(parents=True)
            skill2.write_text("---\nname: skill2\n---\nContent")

            skills = SkillLoader.discover_skills(tmpdir)
            assert len(skills) == 2


class TestHookRunner:
    """Test HookRunner functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = PluginRegistry()
        registry.clear()

    def test_run_sync_hooks(self):
        """Test running hooks synchronously."""
        registry = PluginRegistry()
        runner = HookRunner(registry)

        call_order = []

        def hook1(context):
            call_order.append("hook1")
            return None

        def hook2(context):
            call_order.append("hook2")
            return None

        registry.register_hook("plugin1", HookEvent.BEFORE_ROUTING.value, hook1, priority=100)
        registry.register_hook("plugin2", HookEvent.BEFORE_ROUTING.value, hook2, priority=200)

        state = {"messages": []}
        runner.run_sync(HookEvent.BEFORE_ROUTING, state)

        assert call_order == ["hook1", "hook2"]

    def test_hook_state_modification(self):
        """Test that hooks can modify state."""
        registry = PluginRegistry()
        runner = HookRunner(registry)

        def modifying_hook(context):
            state = context.state.copy()
            state["modified"] = True
            return state

        registry.register_hook(
            "plugin1",
            HookEvent.BEFORE_ROUTING.value,
            modifying_hook,
            priority=100,
        )

        state = {"messages": []}
        result = runner.run_sync(HookEvent.BEFORE_ROUTING, state)

        assert result.get("modified") is True


class TestPluginLoader:
    """Test PluginLoader functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = PluginRegistry()
        registry.clear()

    def test_parse_plugin_manifest(self):
        """Test parsing bestbox.plugin.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "bestbox.plugin.json"
            manifest_data = {
                "name": "test-plugin",
                "description": "Test plugin",
                "version": "1.0.0",
                "requires": {
                    "bins": ["docker"],
                    "python_packages": ["fastapi"],
                    "env_vars": ["SECRET_KEY"],
                },
                "tools": [
                    {
                        "name": "test_tool",
                        "description": "Test tool",
                        "parameters": {"type": "object"},
                    }
                ],
                "hooks": [
                    {
                        "event": "BEFORE_ROUTING",
                        "handler": "test.hooks.handler",
                        "priority": 100,
                    }
                ],
            }

            manifest_file.write_text(json.dumps(manifest_data))

            loader = PluginLoader()
            manifest = loader._parse_plugin_manifest(manifest_file)

            assert manifest is not None
            assert manifest.name == "test-plugin"
            assert manifest.plugin_type == PluginType.PLUGIN
            assert len(manifest.requires.bins) == 1
            assert len(manifest.tools) == 1
            assert len(manifest.hooks) == 1


class TestPluginAPI:
    """Test PluginAPI functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = PluginRegistry()
        registry.clear()

    def test_register_tool_via_api(self):
        """Test registering a tool via PluginAPI."""
        registry = PluginRegistry()
        api = PluginAPI("test-plugin", registry)

        def test_func(message: str) -> str:
            return f"Echo: {message}"

        result = api.register_tool(
            name="test_tool",
            description="Test tool",
            func=test_func,
        )

        assert result is True
        tool = registry.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

    def test_register_hook_via_api(self):
        """Test registering a hook via PluginAPI."""
        registry = PluginRegistry()
        api = PluginAPI("test-plugin", registry)

        def test_hook(context):
            return None

        api.register_hook(HookEvent.BEFORE_ROUTING, test_hook, priority=100)

        handlers = registry.get_hook_handlers(HookEvent.BEFORE_ROUTING.value)
        assert len(handlers) == 1
        assert handlers[0]["plugin"] == "test-plugin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
