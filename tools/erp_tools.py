from langchain_core.tools import tool
from typing import List, Optional

@tool
def get_purchase_orders(vendor_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, status: Optional[str] = None):
    """
    Retrieve purchase orders from the ERP system.
    
    Args:
        vendor_id: Optional vendor identifier (e.g., "VND-001")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        status: Status of the PO (e.g., "pending", "approved", "completed")
    """
    # Mock data
    orders = [
        {"id": "PO-1001", "vendor": "VND-001", "amount": 5000, "status": "pending", "date": "2026-01-15"},
        {"id": "PO-1002", "vendor": "VND-002", "amount": 12000, "status": "approved", "date": "2026-01-10"},
        {"id": "PO-1003", "vendor": "VND-001", "amount": 3500, "status": "completed", "date": "2025-12-20"},
    ]
    
    # Simple filtering
    filtered = orders
    if vendor_id:
        filtered = [o for o in filtered if o["vendor"] == vendor_id]
    if status:
        filtered = [o for o in filtered if o["status"] == status]
        
    return filtered

@tool
def get_inventory_levels(warehouse_id: str = "WH-001"):
    """
    Get current inventory levels for a specific warehouse.
    """""
    return {
        "warehouse_id": warehouse_id,
        "items": [
            {"sku": "ITEM-A1", "name": "Compressor Valve", "quantity": 450, "reorder_point": 100},
            {"sku": "ITEM-B2", "name": "Coolant Pump", "quantity": 12, "reorder_point": 20, "alert": "LOW_STOCK"},
            {"sku": "ITEM-C3", "name": "Filter Mesh", "quantity": 1500, "reorder_point": 500}
        ]
    }

@tool
def get_financial_summary(period: str = "Q4-2025"):
    """
    Get P&L summary for a specific financial period.
    """
    return {
        "period": period,
        "revenue": 1500000,
        "expenses": 1100000,
        "net_profit": 400000,
        "margin": "26.7%",
        "top_expense_categories": ["Procurement", "Payroll", "Logistics"]
    }

@tool
def get_vendor_price_trends(vendor_id: str):
    """Analyze price trends for a specific vendor."""
    return {
        "vendor_id": vendor_id,
        "trend": "increasing",
        "average_increase": "15%",
        "affected_items": ["Steel Sheets", "Aluminum Profiles"]
    }
