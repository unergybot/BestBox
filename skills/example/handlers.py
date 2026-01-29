"""
Example skill hook handlers.
"""

import logging

logger = logging.getLogger(__name__)


def log_after_routing(context):
    """
    Hook that logs after routing is complete.

    Args:
        context: HookContext with event, state, plugin_name, metadata

    Returns:
        Optionally returns modified state
    """
    logger.info(f"[Example Skill Hook] AFTER_ROUTING triggered")

    # Access routed agent
    current_agent = context.state.get("current_agent")
    if current_agent:
        logger.info(f"[Example Skill Hook] Routed to: {current_agent}")

    return None
