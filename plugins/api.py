"""
Plugin API for registration and hook definitions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging

from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class HookEvent(Enum):
    """Lifecycle hook events."""
    BEFORE_AGENT_START = "before_agent_start"
    MESSAGE_RECEIVED = "message_received"
    BEFORE_ROUTING = "before_routing"
    AFTER_ROUTING = "after_routing"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    BEFORE_RESPONSE = "before_response"
    AFTER_RESPONSE = "after_response"
    ON_ERROR = "on_error"
    ON_SHUTDOWN = "on_shutdown"


@dataclass
class HookContext:
    """Context passed to hook handlers."""
    event: HookEvent
    state: Dict[str, Any]  # Agent state
    plugin_name: str
    metadata: Dict[str, Any]  # Event-specific metadata


class PluginAPI:
    """
    API provided to plugins for registration.

    Plugins receive an instance of this class in their register() function.
    """

    def __init__(self, plugin_name: str, registry: Optional[PluginRegistry] = None):
        """
        Initialize PluginAPI.

        Args:
            plugin_name: Name of the plugin using this API
            registry: PluginRegistry instance (defaults to singleton)
        """
        self.plugin_name = plugin_name
        self.registry = registry or PluginRegistry()

    def register_tool(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Register a tool.

        Args:
            name: Tool name
            description: Tool description
            func: Tool implementation function
            parameters: JSON schema for parameters

        Returns:
            True if registered successfully
        """
        from langchain_core.tools import StructuredTool

        # Create LangChain tool
        tool = StructuredTool.from_function(
            func=func,
            name=name,
            description=description,
        )

        return self.registry.register_tool(self.plugin_name, tool)

    def register_hook(
        self,
        event: HookEvent,
        handler: Callable[[HookContext], Any],
        priority: int = 100
    ) -> None:
        """
        Register a lifecycle hook.

        Args:
            event: Hook event to listen for
            handler: Hook handler function
            priority: Priority (lower runs earlier)
        """
        self.registry.register_hook(
            self.plugin_name,
            event.value,
            handler,
            priority
        )

    def register_channel(
        self,
        channel_type: str,
        config: Dict[str, Any]
    ) -> None:
        """
        Register a communication channel.

        Args:
            channel_type: Type of channel (slack, telegram, etc.)
            config: Channel configuration
        """
        self.registry.register_channel(
            self.plugin_name,
            channel_type,
            config
        )

    def register_http_route(
        self,
        route: str,
        handler: Callable,
        methods: Optional[List[str]] = None
    ) -> None:
        """
        Register an HTTP route.

        Args:
            route: Route path (e.g., "/api/custom")
            handler: FastAPI route handler
            methods: HTTP methods (default: ["GET"])
        """
        self.registry.register_http_route(
            self.plugin_name,
            route,
            handler,
            methods or ["GET"]
        )

    def log_info(self, message: str) -> None:
        """Log info message with plugin context."""
        logger.info(f"[{self.plugin_name}] {message}")

    def log_warning(self, message: str) -> None:
        """Log warning message with plugin context."""
        logger.warning(f"[{self.plugin_name}] {message}")

    def log_error(self, message: str) -> None:
        """Log error message with plugin context."""
        logger.error(f"[{self.plugin_name}] {message}")
