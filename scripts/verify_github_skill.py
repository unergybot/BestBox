import sys
import os
import io

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tools.github import GitHubTool
from unittest.mock import MagicMock, patch
import json

def test_github_integration():
    """
    Test GitHub integration with mocked CLI.
    """
    print("Testing GitHub Tool Integration...")
    
    # Mock subprocess.run
    with patch("subprocess.run") as mock_run:
        # 1. Test list_issues
        mock_output = [
            {"number": 1, "title": "Test Issue", "state": "open", "url": "http://github.com/owner/repo/issues/1", "body": "Body", "author": {"login": "user"}}
        ]
        mock_run.return_value = MagicMock(stdout=json.dumps(mock_output), returncode=0)
        
        tool = GitHubTool()
        issues = tool.list_issues("owner/repo")
        
        print(f"List Issues Result: {len(issues)} issues found")
        assert len(issues) == 1
        assert issues[0]["title"] == "Test Issue"
        print("✅ list_issues passed")
        
        # 2. Test get_issue
        mock_issue = {"number": 1, "title": "Test Issue", "state": "open", "body": "Body", "comments": []}
        mock_run.return_value = MagicMock(stdout=json.dumps(mock_issue), returncode=0)
        
        issue = tool.get_issue("owner/repo", 1)
        print(f"Get Issue Result: ID {issue.get('number')}")
        assert issue["title"] == "Test Issue"
        print("✅ get_issue passed")
        
        # 3. Test check for missing command
        mock_run.side_effect = FileNotFoundError
        result = tool.run_raw("gh issue list")
        print(f"Missing Command Result: {result}")
        assert "not found" in result
        print("✅ missing command handling passed")

if __name__ == "__main__":
    test_github_integration()
