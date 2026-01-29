#!/usr/bin/env python
"""
Verify that the plugin system is working correctly.

This script:
1. Loads plugins
2. Verifies tools are registered
3. Verifies hooks are registered
4. Tests plugin functionality
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins import PluginRegistry, PluginLoader, HookEvent


def main():
    print("=" * 60)
    print("BestBox Plugin System Verification")
    print("=" * 60)

    # Initialize registry and loader
    registry = PluginRegistry()
    loader = PluginLoader(registry, workspace_dir=os.getcwd())

    # Load plugins
    print("\n1. Loading plugins...")
    plugin_count = loader.load_all()
    print(f"   ✅ Loaded {plugin_count} plugins")

    # List loaded plugins
    plugins = registry.get_all_plugins()
    print("\n2. Loaded plugins:")
    for plugin in plugins:
        print(f"   - {plugin.name} v{plugin.version} ({plugin.plugin_type.value})")

    # Check tools
    tools = registry.get_all_tools()
    print(f"\n3. Registered tools: {len(tools)}")
    for tool in tools[:5]:  # Show first 5
        print(f"   - {tool.name}: {tool.description}")
    if len(tools) > 5:
        print(f"   ... and {len(tools) - 5} more")

    # Check hooks
    print("\n4. Registered hooks:")
    for event in HookEvent:
        handlers = registry.get_hook_handlers(event.value)
        if handlers:
            print(f"   - {event.value}: {len(handlers)} handler(s)")

    # Test example plugin tool
    print("\n5. Testing example plugin tool...")
    example_tool = registry.get_tool("example_tool")
    if example_tool:
        result = example_tool.invoke({"message": "Hello, BestBox!"})
        print(f"   ✅ Tool result: {result}")
    else:
        print("   ⚠️  Example tool not found")

    # Test skill tool
    print("\n6. Testing example skill tool...")
    skill_tool = registry.get_tool("skill_example_tool")
    if skill_tool:
        result = skill_tool.invoke({"text": "Testing skill"})
        print(f"   ✅ Tool result: {result}")
    else:
        print("   ⚠️  Skill tool not found")

    # Verify graph integration
    print("\n7. Checking graph integration...")
    try:
        from agents.graph import UNIQUE_TOOLS, _plugin_registry, _hook_runner
        print(f"   ✅ Graph has {len(UNIQUE_TOOLS)} total tools")
        print(f"   ✅ Graph has plugin registry: {_plugin_registry is not None}")
        print(f"   ✅ Graph has hook runner: {_hook_runner is not None}")
    except Exception as e:
        print(f"   ❌ Graph integration error: {e}")

    print("\n" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
