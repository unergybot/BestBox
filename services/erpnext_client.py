import os
import requests
import logging
import time
from typing import Dict, List, Any, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

class ERPNextClient:
    """
    Client for interacting with ERPNext REST API.
    Handles authentication, connection pooling, and error handling.
    """
    
    def __init__(self, url: str = None, api_key: str = None, api_secret: str = None, site: str = None):
        self.url = url or os.getenv("ERPNEXT_URL", "http://localhost:8002")
        self.api_key = api_key or os.getenv("ERPNEXT_API_KEY")
        self.api_secret = api_secret or os.getenv("ERPNEXT_API_SECRET")
        self.site = site or os.getenv("ERPNEXT_SITE", "bestbox.local")
        
        self.session = requests.Session()
        
        # Setup headers
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Add auth if keys provided
        if self.api_key and self.api_secret:
            headers["Authorization"] = f"token {self.api_key}:{self.api_secret}"

        # Add site header which is required for ERPNext routing
        if self.site:
            headers["X-Frappe-Site-Name"] = self.site
            headers["Host"] = self.site
            
        self.session.headers.update(headers)
        
        # Cache availability status to avoid spamming health checks
        self._last_availability_check = 0
        self._is_available_cache = False
        self._availability_ttl = int(os.getenv("ERPNEXT_CACHE_TTL", "60"))
        
    def is_available(self) -> bool:
        """
        Check if ERPNext is reachable.
        Cached for 'ERPNEXT_CACHE_TTL' seconds (default 60).
        """
        now = time.time()
        if now - self._last_availability_check < self._availability_ttl:
            return self._is_available_cache
            
        try:
            # Using ping method which is lightweight
            resp = self.session.get(
                f"{self.url}/api/method/ping",
                timeout=int(os.getenv("ERPNEXT_TIMEOUT", "2"))
            )
            self._is_available_cache = resp.status_code == 200
        except Exception as e:
            # logger.debug(f"ERPNext health check failed: {e}")
            self._is_available_cache = False
            
        self._last_availability_check = now
        return self._is_available_cache

    def get_list(self, doctype: str, fields: List[str] = None, filters: Any = None,
                 limit: int = 20, order_by: str = None) -> Optional[List[Dict]]:
        """
        Fetch list of documents.
        Maps to: GET /api/resource/{doctype}
        """
        if not self.is_available():
            return None
            
        params = {
            "limit_page_length": limit
        }
        
        if fields:
            params["fields"] = str(fields).replace("'", '"')
            
        if filters:
            if isinstance(filters, dict):
                import json
                params["filters"] = json.dumps(filters)
            else:
                params["filters"] = str(filters)
                
        if order_by:
            params["order_by"] = order_by
            
        try:
            resp = self.session.get(
                f"{self.url}/api/resource/{doctype}", 
                params=params,
                timeout=int(os.getenv("ERPNEXT_TIMEOUT", "5"))
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            logger.warning(f"ERPNext get_list failed for {doctype}: {e}")
            return None

    def get_doc(self, doctype: str, name: str) -> Optional[Dict]:
        """
        Fetch single document with all fields.
        Maps to: GET /api/resource/{doctype}/{name}
        """
        if not self.is_available():
            return None
            
        try:
            resp = self.session.get(
                f"{self.url}/api/resource/{doctype}/{name}",
                timeout=int(os.getenv("ERPNEXT_TIMEOUT", "5"))
            )
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception as e:
            logger.warning(f"ERPNext get_doc failed for {doctype}/{name}: {e}")
            return None

    def get_value(self, doctype: str, fieldname: str, filters: Any = None) -> Any:
        """
        Get single field value.
        Uses frappe.client.get_value
        """
        if not self.is_available():
            return None
            
        params = {
            "doctype": doctype,
            "fieldname": fieldname
        }
        
        if filters:
            import json
            params["filters"] = json.dumps(filters) if isinstance(filters, dict) else filters
            
        try:
            resp = self.session.get(
                f"{self.url}/api/method/frappe.client.get_value",
                params=params,
                timeout=int(os.getenv("ERPNEXT_TIMEOUT", "5"))
            )
            resp.raise_for_status()
            # Response format: {"message": {"fieldname": value}} or {"message": value} depending on version
            msg = resp.json().get("message", {})
            if isinstance(msg, dict):
                return msg.get(fieldname)
            return msg
        except Exception as e:
            logger.warning(f"ERPNext get_value failed for {doctype}: {e}")
            return None

    def run_query(self, query: str) -> Optional[List[Dict]]:
        """
        Execute custom SQL query.
        WARNING: Only use if absolutely necessary and input is sanitized.
        """
        if not self.is_available():
            return None

        # This typically requires admin access or specific method exposure
        # We'll use frappe.client.get_list which supports sql filters if we need complex queries,
        # but for raw SQL we might need a custom endpoint.
        # Standard ERPNext API doesn't expose raw SQL execution easily for security.
        # We will assume we are just using get_list with sophisticated filters/API for now.
        
        # If we really need raw SQL, we'd use a custom method, but let's stick to safe APIs first.
        logger.warning("run_query called but raw SQL execution is restricted. Use get_list.")
        return None

    def get_report(self, report_name: str, filters: Dict = None) -> Optional[List[Dict]]:
        """
        Run ERPNext Report.
        Maps to: POST /api/method/frappe.desk.query_report.run
        """
        if not self.is_available():
            return None
            
        data = {
            "report_name": report_name,
            "filters": filters or {}
        }
        
        try:
            # Need to verify the endpoint - query_report.run usually requires session/cookies or token
            resp = self.session.post(
                f"{self.url}/api/method/frappe.desk.query_report.run",
                json=data,
                timeout=int(os.getenv("ERPNEXT_TIMEOUT", "10"))
            )
            resp.raise_for_status()
            
            # Reports return 'message': {'result': [...], 'columns': [...]}
            message = resp.json().get("message", {})
            result = message.get("result", [])
            columns = message.get("columns", [])
            
            # We might want to map columns to dict if result provides list of lists
            # But usually result is list of dicts if simple report
            return result
        except Exception as e:
            logger.warning(f"ERPNext get_report failed: {e}")
            return None
