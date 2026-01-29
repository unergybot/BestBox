from .base import ClawdBotSkillTool
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GitHubTool(ClawdBotSkillTool):
    """
    GitHub skill adapter using `gh` CLI.
    """
    def __init__(self):
        super().__init__("github")

    def _run_gh_json(self, args: List[str]) -> List[Dict[str, Any]]:
        """
        Run a gh command and return parsed JSON output.
        """
        cmd = ["gh"] + args + ["--json", "number,title,state,url,body,author"]
        output = self._execute_command(cmd)
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON output: {output}")
            return []

    def list_issues(self, repo: str, state: str = "open", limit: int = 10) -> List[Dict[str, Any]]:
        """
        List issues in a repository.
        """
        return self._run_gh_json(["issue", "list", "--repo", repo, "--state", state, "--limit", str(limit)])

    def get_issue(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """
        Get details of a specific issue.
        """
        cmd = ["gh", "issue", "view", str(issue_number), "--repo", repo, "--json", "number,title,state,body,comments"]
        output = self._execute_command(cmd)
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {}

    def search_issues(self, query: str, repo: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for issues matching a query.
        """
        args = ["search", "issues", query, "--limit", str(limit), "--json", "number,title,state,url,body"]
        if repo:
            args.extend(["--repo", repo])
        
        output = self._execute_command(["gh"] + args)
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []
    
    def list_prs(self, repo: str, state: str = "open", limit: int = 10) -> List[Dict[str, Any]]:
        """
        List pull requests in a repository.
        """
        return self._run_gh_json(["pr", "list", "--repo", repo, "--state", state, "--limit", str(limit)])

