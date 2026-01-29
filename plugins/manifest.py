"""
Plugin manifest definitions and dataclasses.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable


class PluginType(Enum):
    """Type of plugin."""
    SKILL = "skill"  # SKILL.md files
    PLUGIN = "plugin"  # Full Python modules with bestbox.plugin.json


@dataclass
class Requirement:
    """Plugin requirement specification."""
    bins: List[str] = field(default_factory=list)
    python_packages: List[str] = field(default_factory=list)
    env_vars: List[str] = field(default_factory=list)


@dataclass
class ToolDefinition:
    """Tool definition for LangGraph integration."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Optional[Callable] = None  # Function reference for plugin tools

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class HookDefinition:
    """Hook handler definition."""
    event: str  # HookEvent enum value
    handler: str  # Module path to handler function
    priority: int = 100  # Lower = runs earlier


@dataclass
class PluginManifest:
    """Complete plugin manifest."""
    name: str
    description: str
    version: str
    plugin_type: PluginType

    # Optional fields
    requires: Requirement = field(default_factory=Requirement)
    tools: List[ToolDefinition] = field(default_factory=list)
    hooks: List[HookDefinition] = field(default_factory=list)
    channels: List[Dict[str, Any]] = field(default_factory=list)
    http_routes: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    author: Optional[str] = None
    source_path: Optional[str] = None  # Path to SKILL.md or plugin dir
    module_path: Optional[str] = None  # Python module path if applicable
    skill_content: Optional[str] = None  # Full SKILL.md content for skill type

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "type": self.plugin_type.value,
            "requires": {
                "bins": self.requires.bins,
                "python_packages": self.requires.python_packages,
                "env_vars": self.requires.env_vars,
            },
            "tools": [t.to_dict() for t in self.tools],
            "hooks": [{"event": h.event, "handler": h.handler, "priority": h.priority} for h in self.hooks],
            "channels": self.channels,
            "http_routes": self.http_routes,
            "author": self.author,
        }
