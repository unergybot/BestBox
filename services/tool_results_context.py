"""Request-scoped context for correlating UI tool results.

The troubleshooting KB tool stores full results for UI rendering.
We need to scope those results to the active chat request/session to avoid
cross-talk between concurrent requests.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional


# Set by API handlers during agent execution.
# Read by tools to store tool results in the correct bucket.
BESTBOX_TOOL_RESULTS_SESSION_ID: ContextVar[Optional[str]] = ContextVar(
    "bestbox_tool_results_session_id", default=None
)
