from .base import ClawdBotSkillTool
import logging
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

try:
    from notion_client import Client
    from notion_client.errors import APIResponseError
    NOTION_CLIENT_AVAILABLE = True
except ImportError:
    NOTION_CLIENT_AVAILABLE = False

class NotionTool(ClawdBotSkillTool):
    """
    Notion skill adapter using notion-client.
    """
    def __init__(self):
        super().__init__("notion")
        self.client = None
        if NOTION_CLIENT_AVAILABLE:
            api_key = os.environ.get("NOTION_API_KEY")
            if api_key:
                self.client = Client(auth=api_key)
            else:
                logger.warning("NOTION_API_KEY not found in environment variables.")
        else:
            logger.warning("notion-client not installed. NotionTool will not function.")

    def _check_client(self) -> Dict[str, Any]:
        """
        Check if client is initialized.
        """
        if not NOTION_CLIENT_AVAILABLE:
            return {"ok": False, "error": "notion-client library not installed"}
        if not self.client:
            return {"ok": False, "error": "NOTION_API_KEY not set"}
        return {"ok": True}

    def create_page(self, parent_id: str, title: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new page in a database or as a child of another page.
        """
        check = self._check_client()
        if not check["ok"]:
            return check

        # Basic properties construction for title if not provided in properties
        if properties is None:
            properties = {}
        
        if "Name" not in properties and "title" not in properties:
             # Try to construct a default title property (often named Name or title)
            properties["title"] = {
                "title": [{"text": {"content": title}}]
            }

        # Determine parent type (database or page) based on input format or try both?
        # For simplicity, we assume parent_id is passed and we default to database_id
        # Ideally the user specifies parent={"database_id": ...} or parent={"page_id": ...}
        # We'll support a simple parent_id argument assuming database unless specified in kwargs
        
        parent = {"database_id": parent_id} 
        # API requires specific parent object structure. 
        # If user passes a raw ID, we should try to guess or require more info.
        # But to be safe, let's just use what is passed if it is a dict, else assume database_id.
        
        try:
            response = self.client.pages.create(
                parent=parent,
                properties=properties
            )
            return {"ok": True, "id": response["id"], "url": response["url"]}
        except APIResponseError as e:
            logger.error(f"Notion API error: {e}")
            return {"ok": False, "error": str(e)}

    def query_database(self, database_id: str, filter_criteria: Optional[Dict[str, Any]] = None, sorts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Query a database.
        """
        check = self._check_client()
        if not check["ok"]:
            return check

        kwargs = {"database_id": database_id}
        if filter_criteria:
            kwargs["filter"] = filter_criteria
        if sorts:
            kwargs["sorts"] = sorts

        try:
            response = self.client.databases.query(**kwargs)
            results = response.get("results", [])
            return {"ok": True, "results": results}
        except APIResponseError as e:
            logger.error(f"Notion API error: {e}")
            return {"ok": False, "error": str(e)}

    def retrieve_page(self, page_id: str) -> Dict[str, Any]:
        """
        Retrieve a page.
        """
        check = self._check_client()
        if not check["ok"]:
            return check

        try:
            response = self.client.pages.retrieve(page_id=page_id)
            return {"ok": True, "page": response}
        except APIResponseError as e:
            logger.error(f"Notion API error: {e}")
            return {"ok": False, "error": str(e)}
            
    def append_block_children(self, block_id: str, children: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Append blocks to a parent block (or page).
        """
        check = self._check_client()
        if not check["ok"]:
            return check

        try:
            response = self.client.blocks.children.append(block_id=block_id, children=children)
            return {"ok": True, "results": response.get("results", [])}
        except APIResponseError as e:
            logger.error(f"Notion API error: {e}")
            return {"ok": False, "error": str(e)}
