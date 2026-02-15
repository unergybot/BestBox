from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, TypedDict


class BackendHealthStatus(TypedDict, total=False):
    ok: bool
    backend: str
    latency_ms: int
    details: Dict[str, Any]


class BackendAdapter(Protocol):
    """Protocol for customer-specific backend integrations.

    Tool functions should call adapters via business operations instead of
    hardcoding transport logic.
    """

    name: str

    def is_available(self) -> bool:
        """Return True when backend is reachable and healthy."""

    def health(self) -> BackendHealthStatus:
        """Return backend health metadata for diagnostics."""

    def query(self, operation: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a read operation and return normalized payload."""
