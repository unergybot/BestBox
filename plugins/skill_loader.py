"""
Skill loader for SKILL.md files.

Parses YAML frontmatter and extracts skill content.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from .manifest import PluginManifest, PluginType, Requirement, ToolDefinition, HookDefinition
from .utils import check_all_requirements

logger = logging.getLogger(__name__)


class SkillLoader:
    """Loads and parses SKILL.md files."""

    @staticmethod
    def discover_skills(search_dir: str) -> List[Path]:
        """
        Discover all SKILL.md files in a directory.

        Args:
            search_dir: Directory to search recursively

        Returns:
            List of paths to SKILL.md files
        """
        skill_files = []
        search_path = Path(search_dir)

        if not search_path.exists():
            return skill_files

        # Recursively find SKILL.md files
        for skill_file in search_path.rglob("SKILL.md"):
            skill_files.append(skill_file)

        return skill_files

    @staticmethod
    def parse_skill(skill_path: Path) -> Optional[PluginManifest]:
        """
        Parse a SKILL.md file into a PluginManifest.

        Expected format:
        ---
        name: skill-name
        description: Description of the skill
        version: 1.0.0
        requires:
          bins: [git, jq]
          python_packages: [requests]
          env_vars: [GITHUB_TOKEN]
        tools:
          - name: my_tool
            description: Tool description
            parameters:
              type: object
              properties:
                query:
                  type: string
        hooks:
          - event: BEFORE_ROUTING
            handler: skills.my_skill.hooks.before_routing
            priority: 100
        ---

        Skill content goes here...

        Args:
            skill_path: Path to SKILL.md file

        Returns:
            PluginManifest or None if parsing failed
        """
        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract YAML frontmatter
            frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)

            if not frontmatter_match:
                logger.warning(f"No frontmatter found in {skill_path}")
                return None

            frontmatter_yaml = frontmatter_match.group(1)
            skill_content = frontmatter_match.group(2).strip()

            # Parse YAML
            frontmatter = yaml.safe_load(frontmatter_yaml)

            if not frontmatter or not isinstance(frontmatter, dict):
                logger.warning(f"Invalid frontmatter in {skill_path}")
                return None

            # Extract required fields
            name = frontmatter.get("name")
            description = frontmatter.get("description", "")
            version = frontmatter.get("version", "1.0.0")

            if not name:
                logger.warning(f"Missing 'name' field in {skill_path}")
                return None

            # Parse requirements
            requires_data = frontmatter.get("requires", {})
            requires = Requirement(
                bins=requires_data.get("bins", []),
                python_packages=requires_data.get("python_packages", []),
                env_vars=requires_data.get("env_vars", []),
            )

            # Parse tools
            tools = []
            for tool_data in frontmatter.get("tools", []):
                tools.append(ToolDefinition(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    parameters=tool_data.get("parameters", {}),
                ))

            # Parse hooks
            hooks = []
            for hook_data in frontmatter.get("hooks", []):
                hooks.append(HookDefinition(
                    event=hook_data["event"],
                    handler=hook_data["handler"],
                    priority=hook_data.get("priority", 100),
                ))

            # Determine module path from skill directory structure
            # skills/domain/skill_name/SKILL.md -> skills.domain.skill_name
            skill_dir = skill_path.parent
            module_path = None
            if skill_dir.name != "skills":
                # Find relative path from skills/ directory
                try:
                    parts = []
                    current = skill_dir
                    while current.name != "skills" and current.parent != current:
                        parts.insert(0, current.name)
                        current = current.parent
                    if current.name == "skills":
                        module_path = "skills." + ".".join(parts)
                except Exception:
                    pass

            return PluginManifest(
                name=name,
                description=description,
                version=version,
                plugin_type=PluginType.SKILL,
                requires=requires,
                tools=tools,
                hooks=hooks,
                author=frontmatter.get("author"),
                source_path=str(skill_path),
                module_path=module_path,
                skill_content=skill_content,
            )

        except Exception as e:
            logger.error(f"Error parsing {skill_path}: {e}")
            return None

    @staticmethod
    def check_requirements(manifest: PluginManifest) -> bool:
        """
        Check if all requirements for a skill are met.

        Args:
            manifest: Plugin manifest to check

        Returns:
            True if all requirements are met, False otherwise
        """
        all_met, missing = check_all_requirements(manifest.requires)

        if not all_met:
            logger.warning(
                f"Skill '{manifest.name}' has unmet requirements: {', '.join(missing)}"
            )

        return all_met

    @staticmethod
    def load_skill_module(manifest: PluginManifest) -> Optional[Any]:
        """
        Dynamically import skill module if it exists.

        Args:
            manifest: Plugin manifest with module_path

        Returns:
            Imported module or None if not found
        """
        if not manifest.module_path:
            return None

        try:
            import importlib
            module = importlib.import_module(manifest.module_path)
            logger.info(f"Loaded skill module: {manifest.module_path}")
            return module
        except ImportError as e:
            logger.debug(f"No Python module for skill '{manifest.name}': {e}")
            return None
