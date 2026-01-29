import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock notion_client before importing the tool
sys.modules["notion_client"] = MagicMock()
sys.modules["notion_client.errors"] = MagicMock()

from services.tools.notion import NotionTool

class TestNotionTool(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        with patch.dict(os.environ, {"NOTION_API_KEY": "ntn_test"}):
             pass

    @patch("services.tools.notion.Client")
    @patch.dict(os.environ, {"NOTION_API_KEY": "ntn_test"})
    def test_create_page(self, mock_client_cls):
        # Setup mock
        mock_instance = mock_client_cls.return_value
        mock_instance.pages.create.return_value = {"id": "page-id", "url": "http://notion.so/page-id"}
        
        tool = NotionTool()
        result = tool.create_page(parent_id="db-id", title="Test Page")
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["id"], "page-id")
        # Verify call arguments
        # We expect a specific structure for parent and properties
        args, kwargs = mock_instance.pages.create.call_args
        self.assertEqual(kwargs["parent"], {"database_id": "db-id"})
        self.assertEqual(kwargs["properties"]["title"]["title"][0]["text"]["content"], "Test Page")
        print("✅ create_page passed")

    @patch("services.tools.notion.Client")
    @patch.dict(os.environ, {"NOTION_API_KEY": "ntn_test"})
    def test_query_database(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.databases.query.return_value = {
            "results": [{"id": "page-1", "title": "Page 1"}]
        }
        
        tool = NotionTool()
        result = tool.query_database("db-id", filter_criteria={"property": "Status", "select": {"equals": "Done"}})
        
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), 1)
        mock_instance.databases.query.assert_called_with(database_id="db-id", filter={"property": "Status", "select": {"equals": "Done"}})
        print("✅ query_database passed")

if __name__ == "__main__":
    unittest.main()
