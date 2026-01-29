"""
Plugin discovery and loading system.

Supports multi-source discovery with priority:
1. Bundled (skills/, plugins_contrib/)
2. Global (~/.bestbox/plugins/)
3. Workspace (.bestbox/plugins/)
4. Config-specified paths
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import importlib

from .manifest import PluginManifest, PluginType, Requirement, ToolDefinition, HookDefinition
from .registry import PluginRegistry
from .skill_loader import SkillLoader
from .api import PluginAPI, HookEvent
from .utils import check_all_requirements

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Discovers and loads plugins from multiple sources.
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        workspace_dir: Optional[str] = None,
        config_dirs: Optional[List[str]] = None
    ):
        """
        Initialize PluginLoader.

        Args:
            registry: PluginRegistry instance (defaults to singleton)
            workspace_dir: Current workspace directory
            config_dirs: Additional plugin directories from config
        """
        self.registry = registry or PluginRegistry()
        self.workspace_dir = workspace_dir or os.getcwd()
        self.config_dirs = config_dirs or []

        # Determine project root (where this file is)
        self.project_root = Path(__file__).parent.parent

    def _get_search_paths(self) -> List[Path]:
        """
        Get all plugin search paths in priority order.

        Returns:
            List of directory paths to search
        """
        paths = []

        # 1. Bundled plugins
        bundled_skills = self.project_root / "skills"
        bundled_plugins = self.project_root / "plugins_contrib"

        if bundled_skills.exists():
            paths.append(bundled_skills)
        if bundled_plugins.exists():
            paths.append(bundled_plugins)

        # 2. Global plugins
        global_plugins = Path.home() / ".bestbox" / "plugins"
        if global_plugins.exists():
            paths.append(global_plugins)

        # 3. Workspace plugins
        workspace_plugins = Path(self.workspace_dir) / ".bestbox" / "plugins"
        if workspace_plugins.exists():
            paths.append(workspace_plugins)

        # 4. Config-specified paths
        for config_dir in self.config_dirs:
            config_path = Path(config_dir)
            if config_path.exists():
                paths.append(config_path)

        return paths

    def discover_all(self) -> List[PluginManifest]:
        """
        Discover all plugins from all sources.

        Returns:
            List of plugin manifests
        """
        manifests = []
        seen_names = set()

        search_paths = self._get_search_paths()
        logger.info(f"Searching for plugins in {len(search_paths)} locations")

        for search_path in search_paths:
            logger.debug(f"Searching: {search_path}")

            # Discover SKILL.md files
            skill_files = SkillLoader.discover_skills(str(search_path))
            for skill_file in skill_files:
                manifest = SkillLoader.parse_skill(skill_file)
                if manifest:
                    # Later paths override earlier ones
                    if manifest.name in seen_names:
                        logger.info(f"Overriding skill '{manifest.name}' from {search_path}")
                        # Remove old version
                        manifests = [m for m in manifests if m.name != manifest.name]

                    manifests.append(manifest)
                    seen_names.add(manifest.name)

            # Discover full plugin modules (bestbox.plugin.json)
            plugin_manifests = self._discover_plugin_modules(search_path)
            for manifest in plugin_manifests:
                if manifest.name in seen_names:
                    logger.info(f"Overriding plugin '{manifest.name}' from {search_path}")
                    manifests = [m for m in manifests if m.name != manifest.name]

                manifests.append(manifest)
                seen_names.add(manifest.name)

        logger.info(f"Discovered {len(manifests)} plugins")
        return manifests

    def _discover_plugin_modules(self, search_path: Path) -> List[PluginManifest]:
        """
        Discover full plugin modules with bestbox.plugin.json.

        Args:
            search_path: Directory to search

        Returns:
            List of plugin manifests
        """
        manifests = []

        # Look for bestbox.plugin.json files
        for manifest_file in search_path.rglob("bestbox.plugin.json"):
            manifest = self._parse_plugin_manifest(manifest_file)
            if manifest:
                manifests.append(manifest)

        return manifests

    def _parse_plugin_manifest(self, manifest_path: Path) -> Optional[PluginManifest]:
        """
        Parse a bestbox.plugin.json file.

        Args:
            manifest_path: Path to bestbox.plugin.json

        Returns:
            PluginManifest or None if parsing failed
        """
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extract required fields
            name = data.get("name")
            description = data.get("description", "")
            version = data.get("version", "1.0.0")

            if not name:
                logger.warning(f"Missing 'name' in {manifest_path}")
                return None

            # Parse requirements
            requires_data = data.get("requires", {})
            requires = Requirement(
                bins=requires_data.get("bins", []),
                python_packages=requires_data.get("python_packages", []),
                env_vars=requires_data.get("env_vars", []),
            )

            # Parse tools
            tools = []
            for tool_data in data.get("tools", []):
                tools.append(ToolDefinition(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    parameters=tool_data.get("parameters", {}),
                ))

            # Parse hooks
            hooks = []
            for hook_data in data.get("hooks", []):
                hooks.append(HookDefinition(
                    event=hook_data["event"],
                    handler=hook_data["handler"],
                    priority=hook_data.get("priority", 100),
                ))

            # Module path is parent directory name
            plugin_dir = manifest_path.parent
            module_path = self._get_module_path(plugin_dir)

            return PluginManifest(
                name=name,
                description=description,
                version=version,
                plugin_type=PluginType.PLUGIN,
                requires=requires,
                tools=tools,
                hooks=hooks,
                channels=data.get("channels", []),
                http_routes=data.get("http_routes", []),
                author=data.get("author"),
                source_path=str(plugin_dir),
                module_path=module_path,
            )

        except Exception as e:
            logger.error(f"Error parsing {manifest_path}: {e}")
            return None

    def _get_module_path(self, plugin_dir: Path) -> str:
        """
        Determine Python module path for a plugin directory.

        Args:
            plugin_dir: Plugin directory path

        Returns:
            Module path string (e.g., "plugins_contrib.my_plugin")
        """
        # Find relative path from project root
        try:
            rel_path = plugin_dir.relative_to(self.project_root)
            return str(rel_path).replace(os.sep, ".")
        except ValueError:
            # Not under project root, use absolute import
            return plugin_dir.name

    def load_plugin(self, manifest: PluginManifest) -> bool:
        """
        Load a single plugin.

        Args:
            manifest: Plugin manifest to load

        Returns:
            True if loaded successfully
        """
        # Check requirements
        all_met, missing = check_all_requirements(manifest.requires)
        if not all_met:
            logger.warning(
                f"Skipping plugin '{manifest.name}' due to unmet requirements: {', '.join(missing)}"
            )
            return False

        # Register manifest
        if not self.registry.register_plugin(manifest):
            return False

        # Create PluginAPI for this plugin
        api = PluginAPI(manifest.name, self.registry)

        # Load module if it exists
        if manifest.module_path:
            try:
                module = importlib.import_module(manifest.module_path)

                # Call register() function if it exists
                if hasattr(module, "register"):
                    register_func = getattr(module, "register")
                    register_func(api)
                    logger.info(f"Initialized plugin module: {manifest.module_path}")

            except ImportError as e:
                logger.warning(f"Could not import module '{manifest.module_path}': {e}")
            except Exception as e:
                logger.error(f"Error initializing plugin '{manifest.name}': {e}", exc_info=True)
                return False

        # Register hooks from manifest
        for hook_def in manifest.hooks:
            try:
                # Import handler function
                module_path, func_name = hook_def.handler.rsplit(".", 1)
                module = importlib.import_module(module_path)
                handler = getattr(module, func_name)

                # Convert event string to HookEvent
                # Support both "BEFORE_ROUTING" and "before_routing" formats
                event_str = hook_def.event
                try:
                    # Try uppercase enum name first
                    event = HookEvent[event_str]
                except KeyError:
                    # Try lowercase value
                    event = HookEvent(event_str)

                api.register_hook(event, handler, hook_def.priority)

            except Exception as e:
                logger.error(
                    f"Error loading hook '{hook_def.event}' from plugin '{manifest.name}': {e}"
                )

        return True

    def load_all(self) -> int:
        """
        Discover and load all plugins.

        Returns:
            Number of plugins loaded successfully
        """
        manifests = self.discover_all()
        loaded_count = 0

        for manifest in manifests:
            if self.load_plugin(manifest):
                loaded_count += 1

        logger.info(f"Loaded {loaded_count}/{len(manifests)} plugins")
        return loaded_count
