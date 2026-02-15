#!/usr/bin/env python3
"""
Seed ERPNext with BestBox demo data.

This script loads the demo data from data/demo/demo_data.json and creates:
- Suppliers/Vendors
- Customers
- Items
- Purchase Orders
- Sales Orders

Usage:
    python scripts/seed_erpnext_demo_data.py [--dry-run]

Environment variables required:
    ERPNEXT_URL - ERPNext base URL (default: http://localhost:8080)
    ERPNEXT_SITE - Site name (default: frontend)
    ERPNEXT_API_KEY - API key
    ERPNEXT_API_SECRET - API secret
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ERPNextSeeder:
    def __init__(self, dry_run: bool = False):
        self.base_url = os.getenv('ERPNEXT_URL', 'http://localhost:8080')
        self.site = os.getenv('ERPNEXT_SITE', 'frontend')
        self.api_key = os.getenv('ERPNEXT_API_KEY')
        self.api_secret = os.getenv('ERPNEXT_API_SECRET')
        self.dry_run = dry_run

        if not self.api_key or not self.api_secret:
            raise ValueError("ERPNEXT_API_KEY and ERPNEXT_API_SECRET must be set")

        self.headers = {
            'Authorization': f'token {self.api_key}:{self.api_secret}',
            'Host': self.site,
            'Content-Type': 'application/json'
        }

        self.stats = {
            'suppliers': {'created': 0, 'skipped': 0},
            'customers': {'created': 0, 'skipped': 0},
            'items': {'created': 0, 'skipped': 0},
            'purchase_orders': {'created': 0, 'skipped': 0},
            'sales_orders': {'created': 0, 'skipped': 0}
        }

    def load_demo_data(self) -> Dict:
        """Load demo data from JSON file."""
        data_path = Path(__file__).parent.parent / 'data' / 'demo' / 'demo_data.json'
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def check_exists(self, doctype: str, name: str) -> bool:
        """Check if a document exists."""
        url = f"{self.base_url}/api/resource/{doctype.replace(' ', '%20')}/{name.replace(' ', '%20')}"
        response = requests.get(url, headers=self.headers)
        return response.status_code == 200

    def create_document(self, doctype: str, data: Dict) -> bool:
        """Create a document in ERPNext."""
        if self.dry_run:
            print(f"  [DRY RUN] Would create {doctype}: {data.get('name', data.get('supplier_name', data.get('customer_name', data.get('item_code', 'Unknown'))))}")
            return True

        url = f"{self.base_url}/api/resource/{doctype.replace(' ', '%20')}"
        response = requests.post(url, headers=self.headers, json=data)

        if response.status_code in [200, 201]:
            return True
        else:
            print(f"  ✗ Error creating {doctype}: {response.text[:200]}")
            return False

    def seed_suppliers(self, vendors: List[Dict]):
        """Seed suppliers/vendors."""
        print("\n📦 Seeding Suppliers...")

        for vendor in vendors:
            supplier_name = vendor['name']

            if self.check_exists('Supplier', supplier_name):
                print(f"  ⊙ {supplier_name} (exists)")
                self.stats['suppliers']['skipped'] += 1
                continue

            supplier_data = {
                'supplier_name': supplier_name,
                'supplier_group': vendor.get('category', 'General'),
                'supplier_type': 'Company'
            }

            if self.create_document('Supplier', supplier_data):
                print(f"  ✓ {supplier_name}")
                self.stats['suppliers']['created'] += 1
            time.sleep(0.1)  # Rate limiting

    def seed_customers(self, customers: List[Dict]):
        """Seed customers."""
        print("\n👥 Seeding Customers...")

        for customer in customers:
            customer_name = customer['name']

            if self.check_exists('Customer', customer_name):
                print(f"  ⊙ {customer_name} (exists)")
                self.stats['customers']['skipped'] += 1
                continue

            customer_data = {
                'customer_name': customer_name,
                'customer_group': customer.get('category', 'Demo Customer Group'),
                'customer_type': 'Company',
                'territory': 'China'
            }

            if self.create_document('Customer', customer_data):
                print(f"  ✓ {customer_name}")
                self.stats['customers']['created'] += 1
            time.sleep(0.1)

    def seed_items(self, items: List[Dict]):
        """Seed items."""
        print("\n📋 Seeding Items...")

        for item in items:
            item_code = item['code']

            if self.check_exists('Item', item_code):
                print(f"  ⊙ {item_code}: {item['name']} (exists)")
                self.stats['items']['skipped'] += 1
                continue

            item_data = {
                'item_code': item_code,
                'item_name': item['name'],
                'item_group': item.get('group', 'Demo Item Group'),
                'stock_uom': 'Nos',
                'is_stock_item': 1
            }

            if self.create_document('Item', item_data):
                print(f"  ✓ {item_code}: {item['name']}")
                self.stats['items']['created'] += 1
            time.sleep(0.1)

    def seed_purchase_orders(self, purchase_orders: List[Dict]):
        """Seed purchase orders."""
        print("\n🛒 Seeding Purchase Orders...")

        for po in purchase_orders:
            po_id = po['id']

            if self.check_exists('Purchase Order', po_id):
                print(f"  ⊙ {po_id} (exists)")
                self.stats['purchase_orders']['skipped'] += 1
                continue

            # Note: ERPNext auto-generates PO IDs, so we can't set custom IDs directly
            # This is a simplified version - in production, you'd need to handle ID generation
            print(f"  ⚠ Skipping {po_id} (manual creation recommended for order IDs)")
            self.stats['purchase_orders']['skipped'] += 1

    def seed_sales_orders(self, sales_orders: List[Dict]):
        """Seed sales orders."""
        print("\n💰 Seeding Sales Orders...")

        for so in sales_orders:
            so_id = so['id']

            if self.check_exists('Sales Order', so_id):
                print(f"  ⊙ {so_id} (exists)")
                self.stats['sales_orders']['skipped'] += 1
                continue

            # Note: ERPNext auto-generates SO IDs, so we can't set custom IDs directly
            print(f"  ⚠ Skipping {so_id} (manual creation recommended for order IDs)")
            self.stats['sales_orders']['skipped'] += 1

    def print_summary(self):
        """Print seeding summary."""
        print("\n" + "="*60)
        print("📊 SEEDING SUMMARY")
        print("="*60)

        for entity, counts in self.stats.items():
            total = counts['created'] + counts['skipped']
            print(f"{entity.replace('_', ' ').title():20} | Created: {counts['created']:3} | Skipped: {counts['skipped']:3} | Total: {total:3}")

        print("="*60)

        if self.dry_run:
            print("\n💡 This was a dry run. Use without --dry-run to actually create data.")

    def run(self):
        """Run the seeding process."""
        print("="*60)
        print("🌱 BestBox ERPNext Demo Data Seeder")
        print("="*60)
        print(f"Target: {self.base_url} (site: {self.site})")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print("="*60)

        # Load demo data
        data = self.load_demo_data()

        # Seed in order of dependencies
        self.seed_suppliers(data.get('vendors', []))
        self.seed_customers(data.get('customers', []))
        self.seed_items(data.get('items', []))
        self.seed_purchase_orders(data.get('purchase_orders', []))
        self.seed_sales_orders(data.get('sales_orders', []))

        # Print summary
        self.print_summary()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv

    try:
        seeder = ERPNextSeeder(dry_run=dry_run)
        seeder.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
