"""
Seed basic master data into ERPNext.
Creates: Suppliers, Items
"""
import requests
import os
import sys
import json
import logging
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.erpnext_client import ERPNextClient
from tools.erp_tools import get_demo_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_basic")

def seed_basic():
    client = ERPNextClient()
    
    if not client.is_available():
        logger.error("ERPNext is not available. Skipping seeding.")
        sys.exit(1)
        
    data = get_demo_data()
    if not data:
        logger.error("No demo data found.")
        sys.exit(1)

    # 1. Seed Suppliers
    logger.info("Seeding Suppliers...")
    vendors = data.get("vendors", [])
    for v in vendors:
        supplier_data = {
            "doctype": "Supplier",
            "supplier_name": v["name"],
            "supplier_group": v.get("category", "Services"),
            "supplier_type": "Company",
            "country": "China" # Default for demo
        }
        
        # Check existence
        existing = client.get_list("Supplier", filters={"supplier_name": v["name"]}, limit=1)
        if existing:
            logger.info(f"Supplier {v['name']} already exists.")
            # We could store the mapping of v['id'] to ERPNext name if needed, 
            # but we assume name is unique enough or we use the name
            continue
            
        try:
            # Create
            resp = client.session.post(
                f"{client.url}/api/resource/Supplier",
                json=supplier_data,
                timeout=5
            )
            if resp.status_code == 200:
                logger.info(f"Created Supplier: {v['name']}")
            else:
                logger.warning(f"Failed to create Supplier {v['name']}: {resp.text}")
        except Exception as e:
            logger.error(f"Error creating Supplier {v['name']}: {e}")

    # 2. Seed Items
    logger.info("Seeding Items...")
    items = data.get("items", [])
    for item in items:
        item_data = {
            "doctype": "Item",
            "item_code": item["code"],
            "item_name": item["name"],
            "item_group": item.get("group", "All Item Groups"),
            "stock_uom": item.get("uom", "Nos"),
            "is_stock_item": 1,
            "valuation_rate": item.get("rate", 0),
            "standard_rate": item.get("rate", 0)
        }
        
        existing = client.get_list("Item", filters={"item_code": item["code"]}, limit=1)
        if existing:
            logger.info(f"Item {item['code']} already exists.")
            continue
            
        try:
            resp = client.session.post(
                f"{client.url}/api/resource/Item",
                json=item_data,
                timeout=5
            )
            if resp.status_code == 200:
                logger.info(f"Created Item: {item['code']}")
            else:
                # 409 Conflict means exists, but we checked get_list. 
                logger.warning(f"Failed to create Item {item['code']}: {resp.text}")
        except Exception as e:
            logger.error(f"Error creating Item {item['code']}: {e}")

    logger.info("Basic seeding complete.")

if __name__ == "__main__":
    seed_basic()
