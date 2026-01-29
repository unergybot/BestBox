"""
Example plugin hooks.
"""

import logging

logger = logging.getLogger(__name__)


def log_before_routing(context):
    """
    Example hook that logs before routing occurs.

    Args:
        context: HookContext with event, state, plugin_name, metadata

    Returns:
        Optionally returns modified state (None to keep unchanged)
    """
    logger.info(f"[Example Plugin Hook] BEFORE_ROUTING triggered")

    # Access state
    messages = context.state.get("messages", [])
    if messages:
        last_message = messages[-1]
        logger.info(f"[Example Plugin Hook] Last message type: {type(last_message).__name__}")

    # Optionally modify state (return modified state or None)
    # For this example, we just log and don't modify
    return None
