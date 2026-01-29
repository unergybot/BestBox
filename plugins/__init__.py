"""
BestBox Plugin System

Provides extensible plugin infrastructure with:
- Skill loading from SKILL.md files
- Full plugin modules with bestbox.plugin.json manifests
- Tool registration for LangGraph
- Lifecycle hooks
- Multi-source discovery (bundled, global, workspace)
"""

from .manifest import (
    PluginType,
    Requirement,
    ToolDefinition,
    HookDefinition,
    PluginManifest,
)
from .api import PluginAPI, HookEvent, HookContext
from .registry import PluginRegistry
from .loader import PluginLoader
from .hooks import HookRunner
from .skill_loader import SkillLoader

__all__ = [
    "PluginType",
    "Requirement",
    "ToolDefinition",
    "HookDefinition",
    "PluginManifest",
    "PluginAPI",
    "HookEvent",
    "HookContext",
    "PluginRegistry",
    "PluginLoader",
    "HookRunner",
    "SkillLoader",
]
