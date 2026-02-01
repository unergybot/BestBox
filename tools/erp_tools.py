"""
ERP Tools for BestBox AI Agent

These tools connect to the ERPNext API or fall back to demo data.
Demo data is loaded from data/demo/demo_data.json.
"""
from langchain_core.tools import tool
from typing import List, Optional, Dict, Any, Union
import os
import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache

from services.erpnext_client import ERPNextClient

logger = logging.getLogger(__name__)

# Try to load demo data
DEMO_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demo", "demo_data.json")

@lru_cache(maxsize=1)
def load_demo_data():
    """Load demo data from JSON file."""
    try:
        with open(DEMO_DATA_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def get_demo_data():
    """Get demo data, reloading if necessary."""
    return load_demo_data()


# Singleton client instance
_erpnext_client = None

def get_erpnext_client() -> ERPNextClient:
    """Lazy-initialized ERPNext client."""
    global _erpnext_client
    if _erpnext_client is None:
        _erpnext_client = ERPNextClient()
    return _erpnext_client


@tool
def get_purchase_orders(
    vendor_id: Optional[str] = None, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None, 
    status: Optional[str] = None,
    quarter: Optional[str] = None
):
    """
    Retrieve purchase orders from the ERP system.
    
    Args:
        vendor_id: Optional vendor identifier (e.g., "VND-001")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        status: Status of the PO (e.g., "Draft", "Completed", "To Receive and Bill")
        quarter: Financial quarter (e.g., "Q3-2025", "Q4-2025")
    
    Returns:
        List of purchase orders with id, vendor, amount, status, date, and items
    """
    client = get_erpnext_client()
    
    # Try ERPNext first
    if client.is_available():
        try:
            return _get_purchase_orders_from_erpnext(
                client, vendor_id, start_date, end_date, status, quarter
            )
        except Exception as e:
            logger.warning(f"ERPNext query failed: {e}, falling back to demo data")

    # Fallback to demo data
    return _get_purchase_orders_from_demo(
        vendor_id, start_date, end_date, status, quarter
    )


def _get_purchase_orders_from_erpnext(client, vendor_id, start_date, end_date, status, quarter):
    """Query ERPNext for Purchase Orders."""
    filters = {}

    # Need to map internal vendor ID if possible, but assuming names/IDs match or handled
    # If passed ID is distinct from name, we might need lookup. 
    # For now, assuming input can be matched to 'supplier' field.
    if vendor_id:
        filters["supplier"] = ["like", f"%{vendor_id}%"] # Loose match

    if status:
        # Map statuses if needed
        # ERPNext PO statuses: Draft, Submitted, Completed, Cancelled, Closed, To Receive and Bill
        filters["status"] = status

    # Handle date filtering
    if quarter:
        # Convert Q4-2025 to date range
        q_num, year = quarter.split("-")
        year = int(year)
        q_num = int(q_num[1])
        q_start_month = (q_num - 1) * 3 + 1
        q_end_month = q_num * 3
        start_date = f"{year}-{q_start_month:02d}-01"
        # End date logic
        import calendar
        last_day = calendar.monthrange(year, q_end_month)[1]
        end_date = f"{year}-{q_end_month:02d}-{last_day}"

    if start_date:
        filters["transaction_date"] = [">=", start_date]
    if end_date:
        if "transaction_date" in filters:
            # filters["transaction_date"] needs complex syntax for between
            # ["between", [start, end]]
            current_start = filters["transaction_date"][1]
            filters["transaction_date"] = ["between", [current_start, end_date]]
        else:
            filters["transaction_date"] = ["<=", end_date]

    # Fetch from ERPNext
    # We fetch basic fields + items if possible
    # Note: get_list doesn't return child tables (items) usually, unless supported
    # For child items, we usually need get_doc. 
    # For summary, we might not need items. Tool definition returns "items" in list description...
    # Efficiency: get_list is fast. Fetching items for all pos is slow (N+1).
    # We will fetch items only if list is small (<5) or just return summary items?
    # Let's fallback to just header info for list, unless detailed view requested (which is not this tool).
    # Or fetch top 20 and then iterate to get items? Expensive.
    # We'll omit items in list view for performance, or fetch via report?
    # Let's try to get simple fields.
    
    orders = client.get_list(
        "Purchase Order",
        fields=["name", "supplier", "supplier_name", "grand_total",
                "status", "transaction_date", "currency"],
        filters=filters,
        limit=20,
        order_by="transaction_date desc"
    )

    if orders is None:
        raise Exception("ERPNext returned None")

    # Transform to match demo data format
    transformed = []
    for po in orders:
        transformed.append({
            "id": po.get("name"),
            "vendor_id": po.get("supplier"), # Usually the ID/Name
            "vendor_name": po.get("supplier_name"),
            "total": po.get("grand_total", 0),
            "status": po.get("status"),
            "date": po.get("transaction_date"),
            "currency": po.get("currency", "CNY"),
            "items": [] # Items omitted for list performance
        })

    total_amount = sum(o["total"] for o in transformed)

    return {
        "count": len(transformed),
        "total_amount": round(total_amount, 2),
        "currency": transformed[0]["currency"] if transformed else "CNY",
        "orders": transformed,
        "source": "erpnext"
    }


def _get_purchase_orders_from_demo(vendor_id, start_date, end_date, status, quarter):
    """Original demo data implementation."""
    data = get_demo_data()
    if data and "purchase_orders" in data:
        orders = data["purchase_orders"]
    else:
        orders = [] # Fallback empty if no file
    
    # Apply filters
    filtered = orders
    
    if vendor_id:
        filtered = [o for o in filtered if o.get("vendor_id") == vendor_id]
    
    if status:
        filtered = [o for o in filtered if o.get("status", "").lower() == status.lower()]
    
    if quarter:
        q_num, year = quarter.split("-")
        year = int(year)
        q_num = int(q_num[1])
        q_start_month = (q_num - 1) * 3 + 1
        q_end_month = q_num * 3
        
        filtered = [
            o for o in filtered 
            if o.get("date") and 
               datetime.strptime(o["date"], "%Y-%m-%d").year == year and
               q_start_month <= datetime.strptime(o["date"], "%Y-%m-%d").month <= q_end_month
        ]
    
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        filtered = [o for o in filtered if o.get("date") and datetime.strptime(o["date"], "%Y-%m-%d") >= start]
    
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
        filtered = [o for o in filtered if o.get("date") and datetime.strptime(o["date"], "%Y-%m-%d") <= end]
    
    total_amount = sum(o.get("total", 0) for o in filtered)
    
    return {
        "count": len(filtered),
        "total_amount": round(total_amount, 2),
        "currency": "CNY",
        "orders": filtered[:20],
        "source": "demo"
    }


@tool
def get_inventory_levels(warehouse_id: str = "WH-001"):
    """
    Get current inventory levels for a specific warehouse.
    
    Args:
        warehouse_id: Warehouse identifier (WH-001=Main, WH-002=Staging, WH-003=Finished Goods)
    
    Returns:
        Inventory items with quantities and stock alerts
    """
    client = get_erpnext_client()
    
    if client.is_available():
        try:
            return _get_inventory_levels_from_erpnext(client, warehouse_id)
        except Exception as e:
            logger.warning(f"ERPNext inventory failed: {e}, using demo")
            
    return _get_inventory_levels_from_demo(warehouse_id)


def _get_inventory_levels_from_erpnext(client, warehouse_id):
    """Query ERPNext Bin/Item for inventory."""
    # Map warehouse ID to name if necessary
    # Assuming warehouse_id IS the name or we look it up.
    # Demo data has "Main Warehouse" for "WH-001"
    
    wh_map = {
        "WH-001": "Stores - UB",
        "WH-002": "Staging Area",
        "WH-003": "Finished Goods Store"
    }
    warehouse_name = wh_map.get(warehouse_id, warehouse_id)
    
    # Check if warehouse exists by name? Or just query.
    # ERPNext stores stock in 'Bin' doctype
    bins = client.get_list(
        "Bin",
        fields=["item_code", "actual_qty", "warehouse"],
        filters={"warehouse": ["like", f"%{warehouse_name}%"]}, # Loose match
        limit=100
    )
    
    if bins is None:
        raise Exception("Failed to fetch bins")
        
    inventory = []
    
    # We need Item details (name, group) for each bin.
    # Collect item codes
    item_codes = [b["item_code"] for b in bins]
    items_info = {}
    if item_codes:
        # Fetch item details in batch?
        # Creating a filter "in" list
        chunk_size = 20
        for i in range(0, len(item_codes), chunk_size):
            chunk = item_codes[i:i+chunk_size]
            items = client.get_list(
                "Item",
                fields=["item_code", "item_name", "item_group", "reorder_level"],
                filters={"item_code": ["in", chunk]}
            )
            if items:
                for item in items:
                    items_info[item["item_code"]] = item

    low_stock_count = 0
    
    for b in bins:
        code = b["item_code"]
        info = items_info.get(code, {})
        qty = b["actual_qty"]
        reorder = info.get("reorder_level", 0)
        
        entry = {
            "sku": code,
            "name": info.get("item_name", code),
            "group": info.get("item_group", "Unknown"),
            "quantity": qty,
            "reorder_point": reorder,
            "warehouse": warehouse_id
        }
        
        if qty < reorder:
            entry["alert"] = "LOW_STOCK"
            low_stock_count += 1
            
        inventory.append(entry)
        
    return {
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "total_items": len(inventory),
        "low_stock_alerts": low_stock_count,
        "items": inventory,
        "source": "erpnext"
    }


def _get_inventory_levels_from_demo(warehouse_id):
    data = get_demo_data()
    items = data.get("items", []) if data else []
    
    inventory = []
    for item in items:
        # Generate realistic quantities
        base_qty = 100 if "RM-" in item["code"] else 50 if "CP-" in item["code"] else 20
        qty = base_qty * (hash(item["code"] + warehouse_id) % 10 + 1)
        reorder_point = base_qty // 2
        
        entry = {
            "sku": item["code"],
            "name": item["name"],
            "group": item["group"],
            "quantity": qty,
            "reorder_point": reorder_point,
            "warehouse": warehouse_id
        }
        
        if qty < reorder_point:
            entry["alert"] = "LOW_STOCK"
        
        inventory.append(entry)
    
    if warehouse_id == "WH-001":
        for inv in inventory:
            if inv["sku"] == "CP-002":
                inv["quantity"] = 12
                inv["reorder_point"] = 20
                inv["alert"] = "LOW_STOCK"
    
    low_stock_count = sum(1 for i in inventory if i.get("alert") == "LOW_STOCK")
    
    return {
        "warehouse_id": warehouse_id,
        "warehouse_name": {"WH-001": "Main Warehouse", "WH-002": "Staging Area", "WH-003": "Finished Goods Store"}.get(warehouse_id, warehouse_id),
        "total_items": len(inventory),
        "low_stock_alerts": low_stock_count,
        "items": inventory,
        "source": "demo"
    }


@tool
def get_financial_summary(period: str = "Q4-2025"):
    """
    Get P&L summary for a specific financial period.
    Currently falls back to demo data even with ERPNext client (Phase 3).
    """
    # Placeholder for Phase 3 implementation
    return _get_financial_summary_from_demo(period)

def _get_financial_summary_from_demo(period):
    data = get_demo_data()
    pos = data.get("purchase_orders", []) if data else []
    sos = data.get("sales_orders", []) if data else []
    
    if period.startswith("Q"):
        q_num, year = period.split("-")
        year = int(year)
        q_num = int(q_num[1])
        q_start_month = (q_num - 1) * 3 + 1
        q_end_month = q_num * 3
        
        period_pos = [
            p for p in pos 
            if p.get("date") and 
               datetime.strptime(p["date"], "%Y-%m-%d").year == year and
               q_start_month <= datetime.strptime(p["date"], "%Y-%m-%d").month <= q_end_month
        ]
        period_sos = [
            s for s in sos 
            if s.get("date") and 
               datetime.strptime(s["date"], "%Y-%m-%d").year == year and
               q_start_month <= datetime.strptime(s["date"], "%Y-%m-%d").month <= q_end_month
        ]
    else:
        period_pos = pos
        period_sos = sos
    
    procurement_spend = sum(p.get("total", 0) for p in period_pos)
    revenue = sum(s.get("total", 0) for s in period_sos if s.get("status") not in ["Cancelled", "Lost"])
    
    payroll = 450000
    logistics = 120000
    overhead = 85000
    
    total_expenses = procurement_spend + payroll + logistics + overhead
    net_profit = revenue - total_expenses
    margin = (net_profit / revenue * 100) if revenue > 0 else 0
    
    return {
        "period": period,
        "revenue": round(revenue, 2),
        "expenses": round(total_expenses, 2),
        "net_profit": round(net_profit, 2),
        "margin": f"{margin:.1f}%",
        "currency": "CNY",
        "expense_breakdown": {
            "Procurement": round(procurement_spend, 2),
            "Payroll": payroll,
            "Logistics": logistics,
            "Overhead": overhead
        },
        "purchase_order_count": len(period_pos),
        "sales_order_count": len(period_sos),
        "source": "demo"
    }


@tool
def get_vendor_price_trends(vendor_id: str, compare_periods: Optional[str] = "Q3-Q4"):
    """
    Analyze price trends for a specific vendor and recommend actions.
    
    Args:
        vendor_id: Vendor identifier (e.g., "VND-001")
        compare_periods: Standard comparison period (default: "Q3-Q4")
    """
    # Placeholder for Phase 3
    return _get_vendor_price_trends_from_demo(vendor_id, compare_periods)

def _get_vendor_price_trends_from_demo(vendor_id, compare_periods):
    data = get_demo_data()
    vendors = data.get("vendors", []) if data else []
    pos = data.get("purchase_orders", []) if data else []
    
    vendor = next((v for v in vendors if v["id"] == vendor_id), None)
    if not vendor:
        return {"error": f"Vendor {vendor_id} not found"}
    
    vendor_pos = [p for p in pos if p.get("vendor_id") == vendor_id]
    
    q3_pos = [p for p in vendor_pos if p.get("date") and 7 <= datetime.strptime(p["date"], "%Y-%m-%d").month <= 9]
    q4_pos = [p for p in vendor_pos if p.get("date") and 10 <= datetime.strptime(p["date"], "%Y-%m-%d").month <= 12]
    
    q3_total = sum(p.get("total", 0) for p in q3_pos)
    q4_total = sum(p.get("total", 0) for p in q4_pos)
    
    if q3_total > 0:
        change_pct = ((q4_total / len(q4_pos) if q4_pos else 0) / (q3_total / len(q3_pos) if q3_pos else 1) - 1) * 100
    else:
        change_pct = 0
    
    price_trend = vendor.get("price_trend", 0) * 100
    trend = "increasing" if price_trend > 5 else "decreasing" if price_trend < -5 else "stable"
    
    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor.get("name", "Unknown"),
        "category": vendor.get("category", "Unknown"),
        "trend": trend,
        "price_change": f"{price_trend:+.0f}%",
        "q3_spend": round(q3_total, 2),
        "q4_spend": round(q4_total, 2),
        "q3_po_count": len(q3_pos),
        "q4_po_count": len(q4_pos),
        "affected_items": ["Steel Sheet 4mm", "Aluminum Profile"] if vendor_id == "VND-001" else [],
        "recommendation": "Consider renegotiating contract" if price_trend > 15 else "Price within acceptable range",
        "source": "demo"
    }


@tool
def get_procurement_summary(period: str = "Q4-2025"):
    """
    Get procurement summary including spend by vendor.
    
    Args:
        period: Financial period (e.g., "Q4-2025")
    """
    # Placeholder for Phase 3
    return _get_procurement_summary_from_demo(period)

def _get_procurement_summary_from_demo(period):
    data = get_demo_data()
    vendors = data.get("vendors", []) if data else []
    pos = data.get("purchase_orders", []) if data else []
    
    if period.startswith("Q"):
        q_num, year = period.split("-")
        year = int(year)
        q_num = int(q_num[1])
        q_start_month = (q_num - 1) * 3 + 1
        q_end_month = q_num * 3
        
        period_pos = [
            p for p in pos 
            if p.get("date") and 
               datetime.strptime(p["date"], "%Y-%m-%d").year == year and
               q_start_month <= datetime.strptime(p["date"], "%Y-%m-%d").month <= q_end_month
        ]
    else:
        period_pos = pos
    
    vendor_spend = {}
    for po in period_pos:
        vid = po.get("vendor_id")
        if vid not in vendor_spend:
            vendor_spend[vid] = {"total": 0, "count": 0, "name": po.get("vendor_name", vid)}
        vendor_spend[vid]["total"] += po.get("total", 0)
        vendor_spend[vid]["count"] += 1
    
    for vid, spend in vendor_spend.items():
        vendor = next((v for v in vendors if v["id"] == vid), {})
        spend["price_trend"] = f"{vendor.get('price_trend', 0) * 100:+.0f}%"
    
    total_spend = sum(s["total"] for s in vendor_spend.values())
    
    return {
        "period": period,
        "total_spend": round(total_spend, 2),
        "currency": "CNY",
        "vendor_count": len(vendor_spend),
        "po_count": len(period_pos),
        "by_vendor": [
            {
                "vendor_id": vid,
                "vendor_name": info["name"],
                "spend": round(info["total"], 2),
                "po_count": info["count"],
                "share": f"{info['total']/total_spend*100:.1f}%" if total_spend > 0 else "0%",
                "price_trend": info.get("price_trend", "0%")
            }
            for vid, info in sorted(vendor_spend.items(), key=lambda x: x[1]["total"], reverse=True)
        ],
        "source": "demo"
    }


@tool
def get_top_vendors(limit: Union[int, str] = 5, period: str = "Q4-2025"):
    """
    Get the top vendors ranked by total spend.
    Fallback pattern.
    """
    # Robust handling for Qwen-4B hallucinations
    if isinstance(limit, str):
        # If limit looks like a period (e.g. "Q4-2025"), swap it
        if "-" in limit or limit.startswith("Q"):
            # If period is default, use limit as period
            if period == "Q4-2025":
                period = limit
            limit = 5
        elif limit.isdigit():
            limit = int(limit)
        else:
            limit = 5 # Fallback
            
    # Ensure limit is int
    try:
        limit = int(limit)
    except:
        limit = 5

    client = get_erpnext_client()
    
    if client.is_available():
        try:
            return _get_top_vendors_from_erpnext(client, limit, period)
        except Exception as e:
            logger.warning(f"ERPNext top vendors failed: {e}")

    return _get_top_vendors_from_demo(limit, period)


def _get_top_vendors_from_erpnext(client, limit, period):
    # This requires massive aggregation (sum grand_total group by supplier)
    # get_list doesn't assume grouping.
    # We should use get_report or run_query (careful)
    # OR fetch all POs for period and aggregate in python (inefficient if typically large)
    # But for demo scale (~100 POs), python aggregation is fine.
    
    filters = {}
    if period.startswith("Q"):
        q_num, year = period.split("-")
        year = int(year)
        q_num = int(q_num[1])
        q_start_month = (q_num - 1) * 3 + 1
        q_end_month = q_num * 3
        start_date = f"{year}-{q_start_month:02d}-01"
        import calendar
        last_day = calendar.monthrange(year, q_end_month)[1]
        end_date = f"{year}-{q_end_month:02d}-{last_day}"
        
        filters["transaction_date"] = ["between", [start_date, end_date]]
    
    pos = client.get_list(
        "Purchase Order",
        fields=["supplier", "supplier_name", "grand_total"],
        filters=filters,
        limit=500 # Ensure we get enough to aggregate
    )
    
    if pos is None:
        raise Exception("Failed to fetch POs")
        
    vendor_spend = {}
    for po in pos:
        vid = po["supplier"]
        if vid not in vendor_spend:
            vendor_spend[vid] = {
                "total": 0,
                "count": 0,
                "name": po.get("supplier_name", vid)
            }
        vendor_spend[vid]["total"] += po.get("grand_total", 0)
        vendor_spend[vid]["count"] += 1
        
    sorted_vendors = sorted(vendor_spend.items(), key=lambda x: x[1]["total"], reverse=True)[:limit]
    total_spend = sum(s["total"] for _, s in sorted_vendors) # Not total total, but sum of top N? 
    # Actually tool impl sums all analyzed spend, not just top N.
    # But we only fetched top N? No we fetched all (limit 500).
    # Assuming total_analyzed_spend means total in the period.
    total_period_spend = sum(v["total"] for v in vendor_spend.values())
    
    top_vendors = []
    for rank, (vid, info) in enumerate(sorted_vendors, 1):
        top_vendors.append({
            "rank": rank,
            "vendor_id": vid,
            "vendor_name": info["name"],
            "category": "Unknown", # Need to fetch Supplier to get category
            "total_spend": round(info["total"], 2),
            "po_count": info["count"],
            "share_of_spend": f"{info['total']/total_period_spend*100:.1f}%" if total_period_spend > 0 else "0%"
        })
        
    return {
        "period": period,
        "top_vendors": top_vendors,
        "total_analyzed_spend": round(total_period_spend, 2),
        "currency": "CNY",
        "source": "erpnext"
    }


def _get_top_vendors_from_demo(limit, period):
    data = get_demo_data()
    vendors = data.get("vendors", []) if data else []
    pos = data.get("purchase_orders", []) if data else []
    
    if period.startswith("Q"):
        q_num, year = period.split("-")
        year = int(year)
        q_num = int(q_num[1])
        q_start_month = (q_num - 1) * 3 + 1
        q_end_month = q_num * 3
        
        period_pos = [
            p for p in pos 
            if p.get("date") and 
               datetime.strptime(p["date"], "%Y-%m-%d").year == year and
               q_start_month <= datetime.strptime(p["date"], "%Y-%m-%d").month <= q_end_month
        ]
    else:
        period_pos = pos
    
    vendor_spend = {}
    for po in period_pos:
        vid = po.get("vendor_id")
        if vid not in vendor_spend:
            vendor_info = next((v for v in vendors if v["id"] == vid), {})
            vendor_spend[vid] = {
                "total": 0, 
                "count": 0, 
                "name": po.get("vendor_name", vid),
                "category": vendor_info.get("category", "Unknown")
            }
        vendor_spend[vid]["total"] += po.get("total", 0)
        vendor_spend[vid]["count"] += 1
    
    sorted_vendors = sorted(vendor_spend.items(), key=lambda x: x[1]["total"], reverse=True)[:limit]
    total_spend = sum(v["total"] for v in vendor_spend.values())
    
    top_vendors = []
    for rank, (vid, info) in enumerate(sorted_vendors, 1):
        top_vendors.append({
            "rank": rank,
            "vendor_id": vid,
            "vendor_name": info["name"],
            "category": info["category"],
            "total_spend": round(info["total"], 2),
            "po_count": info["count"],
            "share_of_spend": f"{info['total']/total_spend*100:.1f}%" if total_spend > 0 else "0%"
        })
    
    return {
        "period": period,
        "top_vendors": top_vendors,
        "total_analyzed_spend": round(total_spend, 2),
        "currency": "CNY",
        "source": "demo"
    }
