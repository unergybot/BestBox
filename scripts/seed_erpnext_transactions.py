"""
Seed transaction data: Purchase Orders and Purchase Receipts
Requires: seed_erpnext_basic.py completed
"""
import sys
import os
import logging
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.erpnext_client import ERPNextClient
from tools.erp_tools import get_demo_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_transactions")

def seed_transactions():
    client = ERPNextClient()
    
    if not client.is_available():
        logger.error("ERPNext is not available. Skipping seeding.")
        sys.exit(1)
        
    data = get_demo_data()
    if not data:
        logger.error("No demo data found.")
        sys.exit(1)

    # 1. Seed Purchase Orders
    logger.info("Seeding Purchase Orders...")
    orders = data.get("purchase_orders", [])
    vendors_map = {v["id"]: v["name"] for v in data.get("vendors", [])}
    
    created_count = 0
    pr_count = 0

    for po in orders:
        supplier_name = vendors_map.get(po["vendor_id"], po.get("vendor_name"))
        if not supplier_name:
            continue
            
        # Check if PO exists
        filters = {
            "supplier": supplier_name,
            "transaction_date": po["date"],
            "grand_total": po["total"]
        }
        
        existing = client.get_list("Purchase Order", filters=filters, limit=1)
        po_name = None
        po_docstatus = 0
        
        if existing:
            po_name = existing[0]['name']
            
            # Get full details to check docstatus
            try:
                # get_list might return docstatus if requested, but safe to get_value or Assume
                # Actually get_list returns dict with requested fields. default is usually name.
                # Let's request docstatus explicitly
                chk = client.get_list("Purchase Order", filters={"name": po_name}, fields=["name", "docstatus"])
                if chk:
                    po_docstatus = chk[0]['docstatus']
            except:
                pass
                
            logger.info(f"PO {po_name} already exists (Status: {po_docstatus})")
        else:
            # Create PO
            po_items = []
            for item in po.get("items", []):
                po_items.append({
                    "item_code": item["item_code"],
                    "qty": item["qty"],
                    "rate": item["rate"],
                    "schedule_date": po["date"]
                })
                
            po_doc = {
                "doctype": "Purchase Order",
                "transaction_date": po["date"],
                "supplier": supplier_name,
                "company": data.get("company", {}).get("name", "Unergy Robotics"),
                "currency": po.get("currency", "CNY"),
                "conversion_rate": 0.14 if po.get("currency", "CNY") == "CNY" else 1.0,
                "items": po_items,
                "docstatus": 0 # Always create Draft first
            }
            
            try:
                resp = client.session.post(f"{client.url}/api/resource/Purchase Order", json=po_doc)
                if resp.status_code == 200:
                    new_po = resp.json().get("data", {})
                    po_name = new_po.get("name")
                    po_docstatus = 0
                    logger.info(f"Created PO {po_name}")
                    created_count += 1
                else:
                    logger.error(f"Failed to create PO: {resp.text}")
                    continue
            except Exception as e:
                logger.error(f"Error creating PO: {e}")
                continue

        # 2. Handle Submission and Receipt
        target_status = po.get("status") # "Completed", "To Bill", etc.
        
        if target_status in ["Completed", "To Bill"]:
            # Ensure PO is Submitted (docstatus=1)
            if po_docstatus == 0:
                logger.info(f"Submitting PO {po_name}...")
                try:
                    resp = client.session.put(
                        f"{client.url}/api/resource/Purchase Order/{po_name}",
                        json={"docstatus": 1}
                    )
                    if resp.status_code == 200:
                        po_docstatus = 1
                    else:
                        logger.error(f"Failed to submit PO {po_name}: {resp.text}")
                except Exception as e:
                    logger.error(f"Error submitting PO: {e}")

            # Ensure Purchase Receipt exists
            if po_docstatus == 1:
                ensure_purchase_receipt(client, po_name)

    logger.info("Transaction seeding complete.")

def ensure_purchase_receipt(client, po_name):
    # Check if any PR is linked to this PO
    # PR Items usually link back to PO
    # Or we can search PRs created against this PO
    # Simple check: List Purchase Receipt where items.purchase_order = po_name?
    # No, simple is: List PR linked.
    
    # We can use the 'Connections' logic or just brute force check
    # Let's try to fetch PRs that have this PO as reference?
    # Hard to query item level efficiently without complex filters.
    
    # EASIER: Just try to 'make_purchase_receipt'. 
    # If it returns items, we create it.
    # If it returns "No items", it means full already.
    
    logger.info(f"Checking Purchase Receipt for {po_name}...")
    try:
        resp = client.session.post(
            f"{client.url}/api/method/erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt",
            json={"source_name": po_name}
        )
        
        if resp.status_code == 200:
            pr_doc = resp.json().get("message")
            if not pr_doc or not pr_doc.get("items"):
                logger.info(f"No items pending receipt for {po_name} (Already received).")
                return

            # Set warehouse defaults
            for item in pr_doc.get("items", []):
                if not item.get("warehouse"):
                    item["warehouse"] = "Main Warehouse - UR" # Standard convention might include Abbr?
                    # Let's double check warehouse name. It is "Main Warehouse" in existing seeds.
                    item["warehouse"] = "Main Warehouse"

            # Create PR
            create_resp = client.session.post(f"{client.url}/api/resource/Purchase Receipt", json=pr_doc)
            if create_resp.status_code == 200:
                pr_name = create_resp.json().get("data", {}).get("name")
                logger.info(f"Created Draft PR {pr_name}")
                
                # Submit PR
                sub_resp = client.session.put(
                    f"{client.url}/api/resource/Purchase Receipt/{pr_name}", 
                    json={"docstatus": 1}
                )
                if sub_resp.status_code == 200:
                    logger.info(f"Submitted PR {pr_name} - Inventory Updated")
                else:
                    logger.warning(f"Failed to submit PR {pr_name}: {sub_resp.text}")
            else:
                logger.error(f"Failed to create PR doc: {create_resp.text}")
        else:
             # This happens if already received too
             logger.warning(f"Could not map PO to PR (Status {resp.status_code}): {resp.text}")

    except Exception as e:
        logger.error(f"Error ensuring PR: {e}")

if __name__ == "__main__":
    seed_transactions()
