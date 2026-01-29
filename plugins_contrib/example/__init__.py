"""
Example plugin for BestBox.

Demonstrates:
- Tool registration
- Hook registration
- Basic plugin structure
"""

import logging

logger = logging.getLogger(__name__)


def example_tool(message: str) -> str:
    """
    Example tool that echoes back the input with a prefix.

    Args:
        message: Message to echo

    Returns:
        Echoed message with prefix
    """
    logger.info(f"Example tool called with message: {message}")
    return f"[Example Plugin] Echo: {message}"


def register(api):
    """
    Plugin registration function called by PluginLoader.

    Args:
        api: PluginAPI instance for registration
    """
    # Register the example tool
    api.register_tool(
        name="example_tool",
        description="An example tool that echoes back the input with a prefix",
        func=example_tool,
    )

    api.log_info("Example plugin registered successfully")
