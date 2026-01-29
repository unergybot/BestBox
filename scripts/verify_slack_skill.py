import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock slack_sdk before importing the tool
sys.modules["slack_sdk"] = MagicMock()
sys.modules["slack_sdk.errors"] = MagicMock()

from services.tools.slack import SlackTool

class TestSlackTool(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        # Mocking os.environ to ensure SLACK_SDK_AVAILABLE logic works as expected if we mock the import success
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test-token"}):
             # We need to manually set the client because __init__ might have run before we patched environ if we just instantiated it
             # But here we instantiate inside the test usually.
             pass

    @patch("services.tools.slack.WebClient")
    @patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test-token"})
    def test_send_message(self, mock_web_client):
        # Setup mock
        mock_instance = mock_web_client.return_value
        mock_instance.chat_postMessage.return_value = {"ok": True, "ts": "1234.5678", "channel": "C123"}
        
        tool = SlackTool()
        result = tool.chat_postMessage("C123", "Hello World")
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["ts"], "1234.5678")
        mock_instance.chat_postMessage.assert_called_with(channel="C123", text="Hello World")
        print("✅ chat_postMessage passed")

    @patch("services.tools.slack.WebClient")
    @patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test-token"})
    def test_get_history(self, mock_web_client):
        mock_instance = mock_web_client.return_value
        mock_instance.conversations_history.return_value = {
            "ok": True, 
            "messages": [{"text": "hi", "user": "U1"}]
        }
        
        tool = SlackTool()
        result = tool.conversations_history("C123")
        
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["messages"]), 1)
        mock_instance.conversations_history.assert_called_with(channel="C123", limit=10)
        print("✅ conversations_history passed")

if __name__ == "__main__":
    unittest.main()
