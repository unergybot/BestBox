#!/usr/bin/env python3
"""
ERPNext Demo Data Seeding Script

Creates realistic manufacturing company demo data for AI agent demos:
- Company: BestBox Manufacturing Ltd
- Vendors: 5 suppliers with price trends
- Customers: 10 customers with varied activity
- Items: 20 manufacturing parts/materials
- Purchase Orders: 50 POs across Q3-Q4 2025
- Sales Orders: 30 orders for CRM scenarios
- Stock Entries: Inventory movements

Usage:
    python scripts/seed_demo_data.py [--erpnext-url URL] [--api-key KEY]
"""

import argparse
import json
import random
import requests
from datetime import datetime, timedelta
from typing import Optional

# Default configuration
ERPNEXT_URL = "http://localhost:8002"
API_KEY = ""
API_SECRET = ""

# Demo data definitions
COMPANY = {
    "name": "Unergy Robotics",
    "abbr": "UR",
    "country": "China",
    "default_currency": "CNY"
}

VENDORS = [
    {"id": "VND-001", "name": "Shanghai Steel Supply Co.", "category": "Raw Materials", "price_trend": 0.25},
    {"id": "VND-002", "name": "Guangzhou Parts Ltd", "category": "Components", "price_trend": 0.05},
    {"id": "VND-003", "name": "Sunlord (顺络电子)", "category": "Passive Components", "price_trend": 0.02},
    {"id": "VND-004", "name": "Fenghua Advanced (风华高科)", "category": "Passive Components", "price_trend": 0.03},
    {"id": "VND-005", "name": "Guobo Electronics (国博电子)", "category": "RF Components", "price_trend": 0.08},
]

CUSTOMERS = [
    {"id": "CUS-001", "name": "Acme Corporation", "tier": "Enterprise", "churn_risk": 0.15},
    {"id": "CUS-002", "name": "GlobalTech Industries", "tier": "Enterprise", "churn_risk": 0.10},
    {"id": "CUS-003", "name": "Delta Manufacturing", "tier": "Mid-Market", "churn_risk": 0.85},
    {"id": "CUS-004", "name": "Xiaomi Ecosystem Partner", "tier": "Enterprise", "churn_risk": 0.05},
    {"id": "CUS-005", "name": "Automotive Tier 1 Supplier", "tier": "Enterprise", "churn_risk": 0.05},
    {"id": "CUS-006", "name": "Smart Home OEM", "tier": "SMB", "churn_risk": 0.20},
    {"id": "CUS-007", "name": "Eastern Steel Works", "tier": "Enterprise", "churn_risk": 0.12},
    {"id": "CUS-008", "name": "IoT Device Maker", "tier": "Mid-Market", "churn_risk": 0.15},
    {"id": "CUS-009", "name": "Harbor Logistics", "tier": "SMB", "churn_risk": 0.30},
    {"id": "CUS-010", "name": "Prime Manufacturing", "tier": "Enterprise", "churn_risk": 0.08},
]

ITEMS = [
    # E-shine Distributor Products - Radar Modules
    {"code": "ESVSD-400", "name": "Smart Cabin Radar Module", "group": "Radar Modules", "uom": "Nos", "rate": 185.00},
    {"code": "ES58U4-2020", "name": "5.8GHz Radar Sensor", "group": "Radar Modules", "uom": "Nos", "rate": 45.00},
    {"code": "ES-IDR-V2", "name": "Inching Detection Radar", "group": "Radar Modules", "uom": "Nos", "rate": 120.00},
    {"code": "ES-DEV-RADAR", "name": "Radar Development Kit", "group": "Tooling", "uom": "Set", "rate": 1500.00},
    # RF Components
    {"code": "ES-FBAR-B1", "name": "FBAR Filter (Band 1)", "group": "RF Components", "uom": "Nos", "rate": 2.50},
    {"code": "ES-FBAR-B3", "name": "FBAR Filter (Band 3)", "group": "RF Components", "uom": "Nos", "rate": 2.80},
    {"code": "ES-SAW-WF2", "name": "SAW Filter (Wi-Fi)", "group": "RF Components", "uom": "Nos", "rate": 1.20},
    {"code": "ES-LNA-5G01", "name": "Low Noise Amplifier (LNA)", "group": "RF Discrete", "uom": "Nos", "rate": 5.50},
    # Passive Components
    {"code": "HFC-0402-100J", "name": "High-Frequency Capacitor 10pF", "group": "Passive Components", "uom": "Nos", "rate": 0.05},
    {"code": "HFI-0402-1N5", "name": "HF Ceramic Inductor 1.5nH", "group": "Passive Components", "uom": "Nos", "rate": 0.08},
    # Original Demo Items
    {"code": "RM-001", "name": "Steel Sheet 4mm", "group": "Raw Materials", "uom": "Kg", "rate": 8.50},
    {"code": "CP-001", "name": "Compressor Valve", "group": "Components", "uom": "Nos", "rate": 450.00},
    {"code": "FG-001", "name": "Industrial Compressor Unit A", "group": "Finished Goods", "uom": "Nos", "rate": 25000.00},
]

WAREHOUSES = [
    {"id": "WH-001", "name": "Main Warehouse"},
    {"id": "WH-002", "name": "Staging Area"},
    {"id": "WH-003", "name": "Finished Goods Store"},
]


class ERPNextClient:
    """Simple ERPNext API client."""
    
    def __init__(self, base_url: str, api_key: str = "", api_secret: str = ""):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if api_key and api_secret:
            self.session.headers["Authorization"] = f"token {api_key}:{api_secret}"
    
    def create_doc(self, doctype: str, data: dict) -> dict:
        """Create a document in ERPNext."""
        url = f"{self.base_url}/api/resource/{doctype}"
        response = self.session.post(url, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to create {doctype}: {response.text}")
    
    def get_list(self, doctype: str, filters: dict = None, fields: list = None) -> list:
        """Get list of documents."""
        url = f"{self.base_url}/api/resource/{doctype}"
        params = {}
        if filters:
            params["filters"] = json.dumps(filters)
        if fields:
            params["fields"] = json.dumps(fields)
        response = self.session.get(url, params=params)
        return response.json().get("data", [])

    def update_doc(self, doctype: str, name: str, data: dict) -> dict:
        """Update a document in ERPNext."""
        url = f"{self.base_url}/api/resource/{doctype}/{name}"
        response = self.session.put(url, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to update {doctype} {name}: {response.text}")


def generate_purchase_orders(start_date: datetime, end_date: datetime, count: int = 50) -> list:
    """Generate realistic purchase order data."""
    orders = []
    date_range = (end_date - start_date).days
    
    statuses = ["Draft", "To Receive and Bill", "To Bill", "To Receive", "Completed"]
    
    for i in range(count):
        vendor = random.choice(VENDORS)
        order_date = start_date + timedelta(days=random.randint(0, date_range))
        
        # Determine status based on date
        days_old = (datetime.now() - order_date).days
        if days_old < 7:
            status = random.choice(["Draft", "To Receive and Bill"])
        elif days_old < 30:
            status = random.choice(["To Receive and Bill", "To Bill", "To Receive"])
        else:
            status = random.choice(["To Bill", "Completed"])
        
        # Apply Q4 price increase for vendor VND-001
        price_multiplier = 1.0
        if vendor["id"] == "VND-001" and order_date.month >= 10:
            price_multiplier = 1.25  # 25% increase in Q4
        
        # Select 1-5 items for this order (mostly components and passives)
        num_items = random.randint(1, 5)
        selected_items = random.sample(ITEMS[4:], min(num_items, len(ITEMS[4:])))
        
        items = []
        total = 0
        for item in selected_items:
            qty = random.randint(10, 500)
            rate = item["rate"] * price_multiplier * random.uniform(0.95, 1.05)
            amount = qty * rate
            total += amount
            items.append({
                "item_code": item["code"],
                "item_name": item["name"],
                "qty": qty,
                "rate": round(rate, 2),
                "amount": round(amount, 2)
            })
        
        orders.append({
            "id": f"PO-{2025}{i+1001:04d}",
            "vendor_id": vendor["id"],
            "vendor_name": vendor["name"],
            "date": order_date.strftime("%Y-%m-%d"),
            "status": status,
            "items": items,
            "total": round(total, 2),
            "currency": "CNY"
        })
    
    return orders


def generate_sales_orders(start_date: datetime, end_date: datetime, count: int = 30) -> list:
    """Generate realistic sales order data."""
    orders = []
    date_range = (end_date - start_date).days
    
    for i in range(count):
        customer = random.choice(CUSTOMERS)
        order_date = start_date + timedelta(days=random.randint(0, date_range))
        
        # High-churn customers have more cancelled/lost orders
        if customer["churn_risk"] > 0.5 and random.random() < 0.3:
            status = random.choice(["Cancelled", "Lost"])
        else:
            status = random.choice(["To Deliver and Bill", "To Bill", "Completed"])
        
        # Select products normally sold (Radar modules and Finished Goods)
        num_items = random.randint(1, 3)
        saleable_items = ITEMS[:4] + [ITEMS[-1]] # Radar modules + Compressor
        selected_items = random.sample(saleable_items, min(num_items, len(saleable_items)))
        
        items = []
        total = 0
        for item in selected_items:
            qty = random.randint(1, 20)
            rate = item["rate"] * random.uniform(0.98, 1.10)  # Some price variance
            amount = qty * rate
            total += amount
            items.append({
                "item_code": item["code"],
                "item_name": item["name"],
                "qty": qty,
                "rate": round(rate, 2),
                "amount": round(amount, 2)
            })
        
        orders.append({
            "id": f"SO-{2025}{i+1001:04d}",
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "date": order_date.strftime("%Y-%m-%d"),
            "status": status,
            "items": items,
            "total": round(total, 2),
            "currency": "CNY"
        })
    
    return orders


def ensure_dependencies(client: ERPNextClient):
    """Ensure prerequisite data exists."""
    print("Checking dependencies...")
    
    # Item Groups
    item_groups = set(item["group"] for item in ITEMS)
    for group in item_groups:
        try:
            if not client.get_list("Item Group", filters={"item_group_name": group}):
                client.create_doc("Item Group", {"doctype": "Item Group", "item_group_name": group, "parent_item_group": "All Item Groups", "is_group": 0})
                print(f"  Created Item Group: {group}")
        except Exception as e:
            print(f"  Error checking Item Group {group}: {e}")

    # Supplier Groups
    supplier_groups = set(vendor["category"] for vendor in VENDORS)
    for group in supplier_groups:
        try:
            if not client.get_list("Supplier Group", filters={"supplier_group_name": group}):
                client.create_doc("Supplier Group", {"doctype": "Supplier Group", "supplier_group_name": group})
                print(f"  Created Supplier Group: {group}")
        except Exception as e:
            print(f"  Error checking Supplier Group {group}: {e}")
            
    # Warehouses
    for wh in WAREHOUSES:
        try:
            if not client.get_list("Warehouse", filters={"warehouse_name": wh["name"]}):
                # Need a parent warehouse, usually 'All Warehouses' - 'Company'
                # But creating under All Warehouses for simplicity if allowed
                
                # Check for Company
                company = COMPANY["name"]
                
                doc_data = {
                    "doctype": "Warehouse",
                    "warehouse_name": wh["name"],
                    "company": company,
                    "parent_warehouse": f"All Warehouses - {COMPANY['abbr']}" # This might need adjustment if company not set up exactly this way
                }
                # Fallback parent
                try:
                    client.create_doc("Warehouse", doc_data)
                    print(f"  Created Warehouse: {wh['name']}")
                except:
                     # Retry without parent or finding root
                     pass
        except Exception as e:
            print(f"  Error checking Warehouse {wh['name']}: {e}")

    # UOMs
    uoms = set(item["uom"] for item in ITEMS)
    for uom in uoms:
        try:
            if not client.get_list("UOM", filters={"uom_name": uom}):
                client.create_doc("UOM", {"doctype": "UOM", "uom_name": uom})
                print(f"  Created UOM: {uom}")
        except Exception as e:
            print(f"  Error checking UOM {uom}: {e}")


def configure_language(client: ERPNextClient):
    """Configure ERPNext to use Chinese (Simplified)."""
    print("Configuring language settings...")
    
    # 1. System Settings
    try:
        # We perform a PUT on the System Settings singleton
        print("  Setting System Language to 'zh'...")
        client.update_doc("System Settings", "System Settings", {"language": "zh"})
        print("  ✓ System language updated")
    except Exception as e:
        print(f"  Error updating System Settings: {e}")

    # 2. Administrator User
    try:
        print("  Setting Administrator Language to 'zh'...")
        client.update_doc("User", "Administrator", {"language": "zh"})
        print("  ✓ Administrator language updated")
    except Exception as e:
        print(f"  Error updating Administrator User: {e}")


def seed_to_erpnext(client: ERPNextClient):
    """Seed data to a live ERPNext instance."""
    print("Seeding data to ERPNext...")
    
    configure_language(client)
    ensure_dependencies(client)

    # 1. Setup Company (if needed, usually created by wizard/setup)
    company_name = COMPANY["name"]
    # ...

    # 2. Create Items
    print(f"Creating {len(ITEMS)} Items...")
    for item in ITEMS:
        try:
            # Check if exists
            existing = client.get_list("Item", filters={"item_code": item["code"]})
            if existing:
                print(f"  Skipping Item {item['code']} (already exists)")
                continue

            doc_data = {
                "doctype": "Item",
                "item_code": item["code"],
                "item_name": item["name"],
                "item_group": item["group"],
                "stock_uom": item["uom"],
                "is_stock_item": 1,
                "valuation_rate": item["rate"],
                "standard_rate": item["rate"],
                "opening_stock": 0 # We will add stock via Stock Entry or Purchase Receipt
            }
            client.create_doc("Item", doc_data)
            print(f"  Created Item {item['code']}")
        except Exception as e:
            print(f"  Error creating Item {item['code']}: {e}")

    # 3. Create Suppliers (Vendors)
    print(f"Creating {len(VENDORS)} Suppliers...")
    for vendor in VENDORS:
        try:
            existing = client.get_list("Supplier", filters={"supplier_name": vendor["name"]})
            if existing:
                print(f"  Skipping Supplier {vendor['name']} (already exists)")
                continue
                
            doc_data = {
                "doctype": "Supplier",
                "supplier_name": vendor["name"],
                "supplier_group": vendor["category"]
            }
            client.create_doc("Supplier", doc_data)
            print(f"  Created Supplier {vendor['name']}")
        except Exception as e:
            print(f"  Error creating Supplier {vendor['name']}: {e}")

    # 4. Create Customers
    print(f"Creating {len(CUSTOMERS)} Customers...")
    for customer in CUSTOMERS:
        try:
            existing = client.get_list("Customer", filters={"customer_name": customer["name"]})
            if existing:
                print(f"  Skipping Customer {customer['name']} (already exists)")
                continue
                
            doc_data = {
                "doctype": "Customer",
                "customer_name": customer["name"],
                "customer_group": "All Customer Groups", 
                "territory": "All Territories",
                "customer_type": "Company"
            }
            client.create_doc("Customer", doc_data)
            print(f"  Created Customer {customer['name']}")
        except Exception as e:
            print(f"  Error creating Customer {customer['name']}: {e}")

    # Generate orders in memory
    start_date = datetime(2025, 7, 1)
    end_date = datetime(2025, 12, 31)
    purchase_orders = generate_purchase_orders(start_date, end_date, 50)
    sales_orders = generate_sales_orders(start_date, end_date, 30)

    # 5. Create Purchase Orders
    print(f"Creating {len(purchase_orders)} Purchase Orders...")
    for po in purchase_orders:
        try:
            # Check duplicates by ID (internal ID we generated)
            # ERPNext might not map it directly unless we use a custom field or 'name' (if manual naming allowed)
            # We'll use title or api logic.
            # Assuming re-run is fine for now, or check via filters on supplier + date?
            # Let's just create.
            
            supplier_name = po["vendor_name"]
            
            items_list = []
            for item in po["items"]:
               items_list.append({
                   "item_code": item["item_code"],
                   "qty": item["qty"],
                   "rate": item["rate"],
                   "schedule_date": po["date"] 
               })

            doc_data = {
                "doctype": "Purchase Order",
                "company": company_name,
                "supplier": supplier_name,
                "transaction_date": po["date"],
                "schedule_date": po["date"],
                "items": items_list,
                "docstatus": 0
            }
            
            new_po = client.create_doc("Purchase Order", doc_data)
            print(f"  Created PO {new_po.get('name')} for {supplier_name}")
        except Exception as e:
            print(f"  Error creating PO for {po['vendor_name']}: {e}")

    # 6. Create Sales Orders
    print(f"Creating {len(sales_orders)} Sales Orders...")
    for so in sales_orders:
        try:
            customer_name = so["customer_name"]
            
            items_list = []
            for item in so["items"]:
               items_list.append({
                   "item_code": item["item_code"],
                   "qty": item["qty"],
                   "rate": item["rate"],
                   "delivery_date": so["date"]
               })

            doc_data = {
                "doctype": "Sales Order",
                "company": company_name,
                "customer": customer_name,
                "transaction_date": so["date"],
                "delivery_date": so["date"],
                "items": items_list,
                "docstatus": 0
            }
            
            new_so = client.create_doc("Sales Order", doc_data)
            print(f"  Created SO {new_so.get('name')} for {customer_name}")
        except Exception as e:
            print(f"  Error creating SO for {customer_name}: {e}")

    print("Seeding complete!")


def seed_to_json(output_dir: str = "data/demo"):
    """Generate demo data as JSON files for mock services."""
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("Generating demo data as JSON files...")
    
    # Date range: Q3-Q4 2025
    start_date = datetime(2025, 7, 1)
    end_date = datetime(2025, 12, 31)
    
    # Generate data
    purchase_orders = generate_purchase_orders(start_date, end_date, 50)
    sales_orders = generate_sales_orders(start_date, end_date, 30)
    
    # Save to files
    data = {
        "company": COMPANY,
        "vendors": VENDORS,
        "customers": CUSTOMERS,
        "items": ITEMS,
        "warehouses": WAREHOUSES,
        "purchase_orders": purchase_orders,
        "sales_orders": sales_orders,
    }
    
    with open(f"{output_dir}/demo_data.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"  ✓ Saved {len(purchase_orders)} purchase orders")
    print(f"  ✓ Saved {len(sales_orders)} sales orders")
    print(f"  ✓ Saved {len(VENDORS)} vendors")
    print(f"  ✓ Saved {len(CUSTOMERS)} customers")
    print(f"  ✓ Saved {len(ITEMS)} items")
    print(f"\nDemo data saved to: {output_dir}/demo_data.json")
    
    return data


def main():
    parser = argparse.ArgumentParser(description="Seed ERPNext demo data")
    parser.add_argument("--erpnext-url", default=ERPNEXT_URL, help="ERPNext URL")
    parser.add_argument("--api-key", default=API_KEY, help="ERPNext API key")
    parser.add_argument("--api-secret", default=API_SECRET, help="ERPNext API secret")
    parser.add_argument("--json-only", action="store_true", help="Only generate JSON files, don't seed to ERPNext")
    parser.add_argument("--output-dir", default="data/demo", help="Output directory for JSON files")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("ERPNext Demo Data Seeder")
    print("=" * 50)
    print(f"Company: {COMPANY['name']}")
    print(f"Date Range: Q3-Q4 2025")
    print("")
    
    # Always generate JSON for mock fallback
    data = seed_to_json(args.output_dir)
    
    if not args.json_only and args.api_key:
        try:
            client = ERPNextClient(args.erpnext_url, args.api_key, args.api_secret)
            seed_to_erpnext(client)
        except Exception as e:
            print(f"Warning: Could not seed to ERPNext: {e}")
            print("JSON files are still available for mock services.")


if __name__ == "__main__":
    main()
