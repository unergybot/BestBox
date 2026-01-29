"""
Plugin registry singleton.

Manages all loaded plugins, tools, hooks, and HTTP routes.
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from langchain_core.tools import BaseTool, StructuredTool

from .manifest import PluginManifest, ToolDefinition

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Singleton registry for all plugins and their components.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._plugins: Dict[str, PluginManifest] = {}
        self._tools: Dict[str, BaseTool] = {}  # tool_name -> BaseTool
        self._hooks: Dict[str, List[Dict[str, Any]]] = {}  # event -> [{plugin, handler, priority}]
        self._channels: Dict[str, List[Dict[str, Any]]] = {}  # plugin_name -> channel configs
        self._http_routes: List[Dict[str, Any]] = []  # [{plugin, route, handler}]

        self._initialized = True
        logger.info("PluginRegistry initialized")

    def register_plugin(self, manifest: PluginManifest) -> bool:
        """
        Register a plugin manifest.

        Args:
            manifest: Plugin manifest to register

        Returns:
            True if registered successfully, False if already exists
        """
        if manifest.name in self._plugins:
            logger.warning(f"Plugin '{manifest.name}' is already registered")
            return False

        self._plugins[manifest.name] = manifest
        logger.info(f"Registered plugin: {manifest.name} v{manifest.version}")
        return True

    def register_tool(self, plugin_name: str, tool: BaseTool) -> bool:
        """
        Register a tool from a plugin.

        Args:
            plugin_name: Name of the plugin providing the tool
            tool: LangChain BaseTool instance

        Returns:
            True if registered successfully, False if name collision
        """
        if tool.name in self._tools:
            logger.warning(
                f"Tool '{tool.name}' from plugin '{plugin_name}' conflicts with existing tool"
            )
            return False

        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (from {plugin_name})")
        return True

    def register_hook(
        self,
        plugin_name: str,
        event: str,
        handler: Callable,
        priority: int = 100
    ) -> None:
        """
        Register a hook handler.

        Args:
            plugin_name: Name of the plugin providing the hook
            event: Hook event name (from HookEvent enum)
            handler: Callable hook handler
            priority: Priority (lower runs earlier)
        """
        if event not in self._hooks:
            self._hooks[event] = []

        self._hooks[event].append({
            "plugin": plugin_name,
            "handler": handler,
            "priority": priority,
        })

        # Sort by priority
        self._hooks[event].sort(key=lambda x: x["priority"])

        logger.info(f"Registered hook: {event} (from {plugin_name}, priority {priority})")

    def register_channel(self, plugin_name: str, channel_type: str, config: Dict[str, Any]) -> None:
        """
        Register a communication channel.

        Args:
            plugin_name: Name of the plugin providing the channel
            channel_type: Type of channel (slack, telegram, etc.)
            config: Channel configuration
        """
        if plugin_name not in self._channels:
            self._channels[plugin_name] = []

        self._channels[plugin_name].append({
            "type": channel_type,
            "config": config,
        })

        logger.info(f"Registered channel: {channel_type} (from {plugin_name})")

    def register_http_route(
        self,
        plugin_name: str,
        route: str,
        handler: Callable,
        methods: List[str] = None
    ) -> None:
        """
        Register an HTTP route.

        Args:
            plugin_name: Name of the plugin providing the route
            route: Route path (e.g., "/api/custom")
            handler: FastAPI route handler
            methods: HTTP methods (default: ["GET"])
        """
        if methods is None:
            methods = ["GET"]

        self._http_routes.append({
            "plugin": plugin_name,
            "route": route,
            "handler": handler,
            "methods": methods,
        })

        logger.info(f"Registered HTTP route: {route} (from {plugin_name})")

    def get_plugin(self, name: str) -> Optional[PluginManifest]:
        """Get plugin manifest by name."""
        return self._plugins.get(name)

    def get_all_plugins(self) -> List[PluginManifest]:
        """Get all registered plugin manifests."""
        return list(self._plugins.values())

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools for LangGraph."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a specific tool by name."""
        return self._tools.get(name)

    def get_hook_handlers(self, event: str) -> List[Dict[str, Any]]:
        """
        Get all hook handlers for an event, sorted by priority.

        Args:
            event: Hook event name

        Returns:
            List of hook handler dicts with plugin, handler, priority
        """
        return self._hooks.get(event, [])

    def get_channels(self, plugin_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get channel configurations.

        Args:
            plugin_name: Optional plugin name to filter by

        Returns:
            List of channel configs
        """
        if plugin_name:
            return self._channels.get(plugin_name, [])

        # Return all channels
        all_channels = []
        for channels in self._channels.values():
            all_channels.extend(channels)
        return all_channels

    def get_http_routes(self) -> List[Dict[str, Any]]:
        """Get all registered HTTP routes."""
        return self._http_routes

    def clear(self) -> None:
        """Clear all registrations (for testing)."""
        self._plugins.clear()
        self._tools.clear()
        self._hooks.clear()
        self._channels.clear()
        self._http_routes.clear()
        logger.info("PluginRegistry cleared")
