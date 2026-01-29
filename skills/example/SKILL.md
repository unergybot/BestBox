---
name: example-skill
description: Example skill demonstrating SKILL.md format with tools and hooks
version: 1.0.0
author: BestBox Team
requires:
  bins: []
  python_packages: []
  env_vars: []
tools:
  - name: skill_example_tool
    description: Example tool defined in a skill
    parameters:
      type: object
      properties:
        text:
          type: string
          description: Text to process
      required:
        - text
hooks:
  - event: AFTER_ROUTING
    handler: skills.example.handlers.log_after_routing
    priority: 100
---

# Example Skill

This skill demonstrates the enhanced SKILL.md format with:

- YAML frontmatter defining metadata
- Tool definitions for LangGraph integration
- Hook definitions for lifecycle events
- Optional Python module for handlers

## Usage

This skill is automatically discovered and loaded by the plugin system.

## Tool: skill_example_tool

Processes text input and returns it with a skill prefix.

## Hook: AFTER_ROUTING

Logs when routing is complete.
