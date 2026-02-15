"""
Audit logger hooks for tool execution tracking.

This hook captures tool execution metadata and stores it in the agent state
for processing by agent_api.py (which has access to the database pool).
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

from plugins.api import HookContext

logger = logging.getLogger(__name__)


def _hash_params(params: Dict[str, Any]) -> str:
    """
    Create a hash of parameters for PII protection.

    Args:
        params: Tool parameters to hash

    Returns:
        16-character hex hash
    """
    try:
        params_str = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(params_str.encode()).hexdigest()[:16]
    except Exception:
        return "hash_error"


def _determine_result_status(tool_result: Any) -> str:
    """
    Determine result status from tool result.

    Args:
        tool_result: Tool execution result

    Returns:
        Status string: success, error, not_configured, or unknown
    """
    if tool_result is None:
        return "unknown"

    if isinstance(tool_result, dict):
        if "error" in tool_result:
            return "error"
        elif "status" in tool_result:
            status_val = str(tool_result.get("status", "")).lower()
            if "not_configured" in status_val:
                return "not_configured"
            elif "error" in status_val or "fail" in status_val:
                return "error"
            else:
                return "success"
        else:
            return "success"
    elif isinstance(tool_result, (list, str)):
        # Non-empty list/string = success
        return "success" if tool_result else "unknown"

    return "success"


def audit_tool_execution(context: HookContext) -> Optional[Dict[str, Any]]:
    """
    Hook handler for AFTER_TOOL_CALL event.

    Captures tool execution metadata and stores it in agent state
    for later processing by agent_api.py (which has DB access).

    Args:
        context: Hook context with state and metadata

    Returns:
        Modified state with audit info added to plugin_context
    """
    try:
        # Extract metadata passed from graph
        tool_name = context.metadata.get("tool_name")
        tool_params = context.metadata.get("tool_params", {})
        tool_result = context.metadata.get("tool_result")
        start_time = context.metadata.get("start_time")

        if not tool_name:
            logger.debug("No tool_name in metadata for AFTER_TOOL_CALL hook")
            return context.state

        # Calculate latency
        latency_ms = None
        if start_time:
            latency_ms = int((time.time() - start_time) * 1000)

        # Build audit record
        audit_record = {
            "tool_name": tool_name,
            "params_hash": _hash_params(tool_params),
            "result_status": _determine_result_status(tool_result),
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        }

        # Store in plugin_context for agent_api to process
        plugin_context = context.state.get("plugin_context") or {}
        audit_records = plugin_context.get("audit_records") or []
        audit_records.append(audit_record)
        plugin_context["audit_records"] = audit_records

        # Update state
        state = dict(context.state)
        state["plugin_context"] = plugin_context

        logger.info(
            f"Audit captured: tool={tool_name} "
            f"status={audit_record['result_status']} latency={latency_ms}ms"
        )

        return state

    except Exception as e:
        # Never fail the hook - audit logging is best-effort
        logger.error(f"Error in audit_tool_execution hook: {e}", exc_info=True)
        return context.state
