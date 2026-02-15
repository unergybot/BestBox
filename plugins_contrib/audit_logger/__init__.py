"""
Audit logger plugin for BestBox.

Automatically logs all tool executions to the audit_log table with:
- User context (user_id, roles, org_id)
- Tool name and hashed parameters (PII protection)
- Execution status (success/error/not_configured)
- Latency metrics
"""

from plugins.api import PluginAPI


def register(api: PluginAPI):
    """
    Register the audit logger plugin.

    This plugin is hook-only (no tools), so registration just logs activation.
    The actual hook is registered via bestbox.plugin.json manifest.
    """
    api.logger.info("Audit logger plugin registered - tool execution tracking enabled")
    return True
