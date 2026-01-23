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
    "name": "BestBox Manufacturing Ltd",
    "abbr": "BBM",
    "country": "China",
    "default_currency": "CNY"
}

VENDORS = [
    {"id": "VND-001", "name": "Shanghai Steel Supply Co.", "category": "Raw Materials", "price_trend": 0.25},  # 25% increase in Q4
    {"id": "VND-002", "name": "Guangzhou Parts Ltd", "category": "Components", "price_trend": 0.05},
    {"id": "VND-003", "name": "Beijing Industrial Tools", "category": "Equipment", "price_trend": -0.02},
    {"id": "VND-004", "name": "Shenzhen Electronics", "category": "Electronics", "price_trend": 0.10},
    {"id": "VND-005", "name": "Suzhou Precision Mfg", "category": "Precision Parts", "price_trend": 0.08},
]

CUSTOMERS = [
    {"id": "CUS-001", "name": "Acme Corporation", "tier": "Enterprise", "churn_risk": 0.15},
    {"id": "CUS-002", "name": "GlobalTech Industries", "tier": "Enterprise", "churn_risk": 0.10},
    {"id": "CUS-003", "name": "Delta Manufacturing", "tier": "Mid-Market", "churn_risk": 0.85},  # High churn risk
    {"id": "CUS-004", "name": "Omega Solutions", "tier": "Mid-Market", "churn_risk": 0.20},
    {"id": "CUS-005", "name": "Tech Innovators Inc", "tier": "Enterprise", "churn_risk": 0.05},
    {"id": "CUS-006", "name": "Pacific Trading Co", "tier": "SMB", "churn_risk": 0.40},
    {"id": "CUS-007", "name": "Eastern Steel Works", "tier": "Enterprise", "churn_risk": 0.12},
    {"id": "CUS-008", "name": "Summit Industrial", "tier": "Mid-Market", "churn_risk": 0.65},
    {"id": "CUS-009", "name": "Harbor Logistics", "tier": "SMB", "churn_risk": 0.30},
    {"id": "CUS-010", "name": "Prime Manufacturing", "tier": "Enterprise", "churn_risk": 0.08},
]

ITEMS = [
    # Raw Materials
    {"code": "RM-001", "name": "Steel Sheet 4mm", "group": "Raw Materials", "uom": "Kg", "rate": 8.50},
    {"code": "RM-002", "name": "Aluminum Profile", "group": "Raw Materials", "uom": "Meter", "rate": 25.00},
    {"code": "RM-003", "name": "Copper Wire 2mm", "group": "Raw Materials", "uom": "Meter", "rate": 4.20},
    {"code": "RM-004", "name": "Stainless Steel Rod", "group": "Raw Materials", "uom": "Kg", "rate": 15.80},
    {"code": "RM-005", "name": "Rubber Gasket Material", "group": "Raw Materials", "uom": "Sheet", "rate": 120.00},
    # Components
    {"code": "CP-001", "name": "Compressor Valve", "group": "Components", "uom": "Nos", "rate": 450.00},
    {"code": "CP-002", "name": "Coolant Pump", "group": "Components", "uom": "Nos", "rate": 1200.00},
    {"code": "CP-003", "name": "Filter Mesh Assembly", "group": "Components", "uom": "Nos", "rate": 85.00},
    {"code": "CP-004", "name": "Pressure Sensor", "group": "Components", "uom": "Nos", "rate": 320.00},
    {"code": "CP-005", "name": "Control Board PCB", "group": "Components", "uom": "Nos", "rate": 580.00},
    # Finished Goods
    {"code": "FG-001", "name": "Industrial Compressor Unit A", "group": "Finished Goods", "uom": "Nos", "rate": 25000.00},
    {"code": "FG-002", "name": "Industrial Compressor Unit B", "group": "Finished Goods", "uom": "Nos", "rate": 35000.00},
    {"code": "FG-003", "name": "Cooling System Module", "group": "Finished Goods", "uom": "Nos", "rate": 8500.00},
    # Consumables
    {"code": "CN-001", "name": "Lubricant Oil 5L", "group": "Consumables", "uom": "Can", "rate": 180.00},
    {"code": "CN-002", "name": "Coolant Fluid 10L", "group": "Consumables", "uom": "Can", "rate": 250.00},
    {"code": "CN-003", "name": "Cleaning Solvent", "group": "Consumables", "uom": "Liter", "rate": 45.00},
    # Spare Parts
    {"code": "SP-001", "name": "Valve Seal Kit", "group": "Spare Parts", "uom": "Kit", "rate": 65.00},
    {"code": "SP-002", "name": "Bearing Assembly", "group": "Spare Parts", "uom": "Nos", "rate": 280.00},
    {"code": "SP-003", "name": "Filter Cartridge", "group": "Spare Parts", "uom": "Nos", "rate": 95.00},
    {"code": "SP-004", "name": "Gasket Set", "group": "Spare Parts", "uom": "Set", "rate": 42.00},
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
        
        # Select 1-5 items for this order
        num_items = random.randint(1, 5)
        selected_items = random.sample(ITEMS[:10], min(num_items, 10))  # Only raw materials and components
        
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
        
        # Select finished goods
        num_items = random.randint(1, 3)
        selected_items = random.sample(ITEMS[10:14], min(num_items, 4))  # Finished goods
        
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


def seed_to_erpnext(client: ERPNextClient):
    """Seed data to a live ERPNext instance."""
    print("Seeding data to ERPNext...")
    
    # This would create actual documents via API
    # For now, we'll save to JSON for mock data
    raise NotImplementedError("Live ERPNext seeding not yet implemented")


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
