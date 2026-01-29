"""
Example skill module.
"""

import logging

logger = logging.getLogger(__name__)


def skill_example_tool(text: str) -> str:
    """
    Example tool defined in a skill.

    Args:
        text: Text to process

    Returns:
        Processed text with prefix
    """
    logger.info(f"Skill example tool called with: {text}")
    return f"[Example Skill] Processed: {text}"


def register(api):
    """
    Optional skill registration function.

    Args:
        api: PluginAPI instance
    """
    # Register the skill tool
    api.register_tool(
        name="skill_example_tool",
        description="Example tool defined in a skill",
        func=skill_example_tool,
    )

    api.log_info("Example skill registered")
