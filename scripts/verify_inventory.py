import sys
import os
import logging
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools.erp_tools import get_inventory_levels

# Configure logging
logging.basicConfig(level=logging.INFO)

def check_inventory():
    print("Checking Inventory Levels (Expectation: Non-zero for received items)...")
    
    # We mainly expect stock in Main Warehouse (WH-001) as per our script default
    result = get_inventory_levels.func("WH-001")
    
    if result.get("source") != "erpnext":
        print("❌ Warning: Tool returned demo data, not ERPNext data.")
        return

    items = result.get("items", [])
    print(f"Found {len(items)} items in Main Warehouse.")
    
    total_qty = 0
    for item in items:
        print(f"- {item['sku']} ({item['name']}): {item['quantity']}")
        total_qty += item['quantity']
        
    if total_qty > 0:
        print(f"\n✅ SUCCESS: Total stock quantity is {total_qty}. Inventory updated!")
    else:
        print("\n❌ FAILURE: Total stock is 0. Purchase Receipts may not have been submitted.")

if __name__ == "__main__":
    check_inventory()
