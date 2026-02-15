from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


def _config_path() -> Path:
    configured = os.getenv("BESTBOX_CUSTOMER_CONFIG")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "config" / "customer.yaml"


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Very small fallback parser for key/value style YAML.

    This is only used when PyYAML is unavailable. It supports flat and one-level
    nested mappings for lightweight runtime defaults.
    """
    data: Dict[str, Any] = {}
    parents: Dict[int, Dict[str, Any]] = {0: data}

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if ":" not in line:
            continue

        key, value = line.strip().split(":", 1)
        key = key.strip()
        value = value.strip()

        parent_level = indent
        while parent_level not in parents and parent_level > 0:
            parent_level -= 2

        parent = parents.get(parent_level, data)

        if value == "":
            nested: Dict[str, Any] = {}
            parent[key] = nested
            parents[indent + 2] = nested
            continue

        # minimal type coercion
        lowered = value.lower()
        if lowered in {"true", "false"}:
            parsed: Any = lowered == "true"
        elif lowered in {"null", "none"}:
            parsed = None
        elif value.isdigit():
            parsed = int(value)
        else:
            parsed = value.strip('"').strip("'")
        parent[key] = parsed

    return data


@lru_cache(maxsize=1)
def load_customer_config() -> Dict[str, Any]:
    """Load customer deployment config from YAML file (if present)."""
    path = _config_path()
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")

    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return _parse_simple_yaml(raw)


def get_integration_config(name: str) -> Dict[str, Any]:
    """Return integration config block for an integration key (erp/crm/it_ops/oa)."""
    config = load_customer_config()
    integrations = config.get("integrations", {}) if isinstance(config, dict) else {}
    value = integrations.get(name, {}) if isinstance(integrations, dict) else {}
    return value if isinstance(value, dict) else {}


def get_security_config() -> Dict[str, Any]:
    """Return security block from customer config."""
    config = load_customer_config()
    security = config.get("security", {}) if isinstance(config, dict) else {}
    return security if isinstance(security, dict) else {}
