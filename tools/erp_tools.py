"""
ERP Tools for BestBox AI Agent

These tools connect to the ERPNext API or fall back to demo data.
Demo data is loaded from data/demo/demo_data.json.
"""
from langchain_core.tools import tool
from typing import List, Optional
import os
import json
from datetime import datetime
from functools import lru_cache

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
    data = get_demo_data()
    if data and "purchase_orders" in data:
        orders = data["purchase_orders"]
    else:
        # Fallback mock data
        orders = [
            {"id": "PO-1001", "vendor_id": "VND-001", "vendor_name": "Shanghai Steel", "total": 5000, "status": "Draft", "date": "2025-10-15"},
            {"id": "PO-1002", "vendor_id": "VND-002", "vendor_name": "Guangzhou Parts", "total": 12000, "status": "Completed", "date": "2025-09-10"},
        ]
    
    # Apply filters
    filtered = orders
    
    if vendor_id:
        filtered = [o for o in filtered if o.get("vendor_id") == vendor_id]
    
    if status:
        filtered = [o for o in filtered if o.get("status", "").lower() == status.lower()]
    
    if quarter:
        # Parse quarter like "Q4-2025" to date range
        q_num, year = quarter.split("-")
        year = int(year)
        q_num = int(q_num[1])  # Extract number from "Q4"
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
    
    # Calculate summary stats
    total_amount = sum(o.get("total", 0) for o in filtered)
    
    return {
        "count": len(filtered),
        "total_amount": round(total_amount, 2),
        "currency": "CNY",
        "orders": filtered[:20]  # Limit to 20 for response size
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
    data = get_demo_data()
    items = data.get("items", []) if data else []
    
    # Simulate inventory levels based on items
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
        
        # Add alert if low stock
        if qty < reorder_point:
            entry["alert"] = "LOW_STOCK"
        
        inventory.append(entry)
    
    # Add some specific low stock items for demo
    if warehouse_id == "WH-001":
        for inv in inventory:
            if inv["sku"] == "CP-002":  # Coolant Pump
                inv["quantity"] = 12
                inv["reorder_point"] = 20
                inv["alert"] = "LOW_STOCK"
    
    low_stock_count = sum(1 for i in inventory if i.get("alert") == "LOW_STOCK")
    
    return {
        "warehouse_id": warehouse_id,
        "warehouse_name": {"WH-001": "Main Warehouse", "WH-002": "Staging Area", "WH-003": "Finished Goods Store"}.get(warehouse_id, warehouse_id),
        "total_items": len(inventory),
        "low_stock_alerts": low_stock_count,
        "items": inventory
    }


@tool
def get_financial_summary(period: str = "Q4-2025"):
    """
    Get P&L summary for a specific financial period.
    
    Args:
        period: Financial period (e.g., "Q4-2025", "Q3-2025", "2025")
    
    Returns:
        Revenue, expenses, profit, margin, and category breakdowns
    """
    data = get_demo_data()
    
    # Calculate from purchase orders for the period
    pos = data.get("purchase_orders", []) if data else []
    sos = data.get("sales_orders", []) if data else []
    
    # Parse period
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
    
    # Mock other expenses
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
        "sales_order_count": len(period_sos)
    }


@tool
def get_vendor_price_trends(vendor_id: str, compare_periods: Optional[str] = "Q3-Q4"):
    """
    Analyze price trends for a specific vendor by comparing periods.
    
    Args:
        vendor_id: Vendor identifier (e.g., "VND-001")
        compare_periods: Periods to compare (e.g., "Q3-Q4" to compare Q3 vs Q4)
    
    Returns:
        Price trend analysis with percentage change and affected items
    """
    data = get_demo_data()
    vendors = data.get("vendors", []) if data else []
    pos = data.get("purchase_orders", []) if data else []
    
    # Find vendor info
    vendor = next((v for v in vendors if v["id"] == vendor_id), None)
    
    if not vendor:
        return {"error": f"Vendor {vendor_id} not found"}
    
    # Get POs for this vendor
    vendor_pos = [p for p in pos if p.get("vendor_id") == vendor_id]
    
    # Separate by quarter
    q3_pos = [p for p in vendor_pos if p.get("date") and 7 <= datetime.strptime(p["date"], "%Y-%m-%d").month <= 9]
    q4_pos = [p for p in vendor_pos if p.get("date") and 10 <= datetime.strptime(p["date"], "%Y-%m-%d").month <= 12]
    
    q3_total = sum(p.get("total", 0) for p in q3_pos)
    q4_total = sum(p.get("total", 0) for p in q4_pos)
    
    # Calculate price trend
    if q3_total > 0:
        change_pct = ((q4_total / len(q4_pos) if q4_pos else 0) / (q3_total / len(q3_pos) if q3_pos else 1) - 1) * 100
    else:
        change_pct = 0
    
    # Use vendor's known price trend for accurate demo
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
        "recommendation": "Consider renegotiating contract or evaluating alternative suppliers" if price_trend > 15 else "Price within acceptable range"
    }


@tool
def get_procurement_summary(period: str = "Q4-2025"):
    """
    Get a summary of procurement spend by vendor for a period.
    
    Args:
        period: Financial period (e.g., "Q4-2025")
    
    Returns:
        Procurement spend breakdown by vendor with trends
    """
    data = get_demo_data()
    vendors = data.get("vendors", []) if data else []
    pos = data.get("purchase_orders", []) if data else []
    
    # Parse period
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
    
    # Group by vendor
    vendor_spend = {}
    for po in period_pos:
        vid = po.get("vendor_id")
        if vid not in vendor_spend:
            vendor_spend[vid] = {"total": 0, "count": 0, "name": po.get("vendor_name", vid)}
        vendor_spend[vid]["total"] += po.get("total", 0)
        vendor_spend[vid]["count"] += 1
    
    # Add trend info
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
        ]
    }
