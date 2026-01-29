import subprocess
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ClawdBotSkillTool:
    """
    Base class for ClawdBot skills adapted for BestBox.
    """
    skill_name: str
    
    def __init__(self, skill_name: str):
        self.skill_name = skill_name

    def _execute_command(self, command: List[str], cwd: Optional[str] = None) -> str:
        """
        Execute a CLI command and return the output.
        """
        try:
            logger.info(f"Executing command: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                cwd=cwd
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with error: {e.stderr}")
            return f"Error: Command failed with exit code {e.returncode}. Output: {e.stderr}"
        except FileNotFoundError:
            logger.error(f"Command not found: {command[0]}")
            return f"Error: Command '{command[0]}' not found. Is it installed?"
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return f"Error: An unexpected error occurred: {e}"

    def run_raw(self, command_str: str) -> str:
        """
        Run a raw command string (splitting by space), use with caution.
        """
        parts = command_str.split()
        return self._execute_command(parts)
