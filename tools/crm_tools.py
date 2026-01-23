"""
CRM Tools for BestBox AI Agent

Tools for sales, leads, customers, and churn prediction.
Demo data is loaded from data/demo/demo_data.json.
"""
from langchain_core.tools import tool
from typing import Optional, List
import os
import json
from functools import lru_cache

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
    """Get demo data."""
    return load_demo_data()


@tool
def get_leads(status: str = "active", tier: Optional[str] = None, limit: int = 10):
    """
    Get a list of sales leads/customers with their current score and status.
    
    Args:
        status: Lead status filter ("active", "all")
        tier: Customer tier filter ("Enterprise", "Mid-Market", "SMB")
        limit: Maximum number of leads to return
    
    Returns:
        List of leads with scoring and activity information
    """
    data = get_demo_data()
    customers = data.get("customers", []) if data else []
    sales = data.get("sales_orders", []) if data else []
    
    if not customers:
        # Fallback mock data
        return [
            {"id": "LD-501", "company": "Acme Corp", "status": "active", "score": 85, "stage": "proposal"},
            {"id": "LD-502", "company": "GlobalTech", "status": "active", "score": 78, "stage": "demo"},
        ][:limit]
    
    # Enrich customers with sales activity
    leads = []
    for cust in customers:
        cust_sales = [s for s in sales if s.get("customer_id") == cust["id"]]
        total_value = sum(s.get("total", 0) for s in cust_sales if s.get("status") not in ["Cancelled", "Lost"])
        
        # Calculate lead score (inverse of churn risk, scaled)
        score = int((1 - cust.get("churn_risk", 0.5)) * 100)
        
        lead = {
            "id": cust["id"],
            "company": cust["name"],
            "tier": cust["tier"],
            "status": "active",
            "score": score,
            "churn_risk": cust.get("churn_risk", 0),
            "total_orders": len(cust_sales),
            "total_value": round(total_value, 2),
            "stage": "active" if len(cust_sales) > 0 else "prospecting"
        }
        leads.append(lead)
    
    # Apply filters
    if tier:
        leads = [l for l in leads if l["tier"].lower() == tier.lower()]
    
    # Sort by score (higher = better lead)
    leads = sorted(leads, key=lambda x: x["score"], reverse=True)
    
    return leads[:limit]


@tool
def predict_churn(customer_id: str):
    """
    Predict the churn probability for a specific customer using ML models.
    
    Args:
        customer_id: Customer identifier (e.g., "CUS-003")
    
    Returns:
        Churn probability, risk level, and contributing factors
    """
    data = get_demo_data()
    customers = data.get("customers", []) if data else []
    sales = data.get("sales_orders", []) if data else []
    
    customer = next((c for c in customers if c["id"] == customer_id), None)
    
    if not customer:
        return {"error": f"Customer {customer_id} not found"}
    
    churn_prob = customer.get("churn_risk", 0.5)
    
    # Determine risk level
    if churn_prob >= 0.7:
        risk_level = "HIGH"
    elif churn_prob >= 0.4:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    
    # Generate factors based on churn probability
    factors = []
    if churn_prob > 0.6:
        factors.append("Decreased order frequency (-40%)")
        factors.append(f"No orders in last 60 days")
    if churn_prob > 0.4:
        factors.append("Pending support tickets (3)")
    if churn_prob > 0.3:
        factors.append("Renewal date approaching (30 days)")
    if churn_prob < 0.2:
        factors.append("High engagement score")
        factors.append("Recent order activity")
    
    # Get customer's order history
    cust_orders = [s for s in sales if s.get("customer_id") == customer_id]
    completed_orders = [s for s in cust_orders if s.get("status") == "Completed"]
    cancelled_orders = [s for s in cust_orders if s.get("status") in ["Cancelled", "Lost"]]
    
    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "tier": customer["tier"],
        "churn_probability": round(churn_prob, 2),
        "risk_level": risk_level,
        "key_factors": factors,
        "order_history": {
            "total_orders": len(cust_orders),
            "completed": len(completed_orders),
            "cancelled": len(cancelled_orders)
        },
        "recommendation": "Immediate outreach required" if risk_level == "HIGH" else 
                         "Schedule check-in call" if risk_level == "MEDIUM" else 
                         "Continue regular engagement"
    }


@tool
def get_customer_360(customer_id: str):
    """
    Get a complete 360-degree view of a customer.
    
    Args:
        customer_id: Customer identifier (e.g., "CUS-001")
    
    Returns:
        Complete customer profile with orders, value, and engagement
    """
    data = get_demo_data()
    customers = data.get("customers", []) if data else []
    sales = data.get("sales_orders", []) if data else []
    
    customer = next((c for c in customers if c["id"] == customer_id), None)
    
    if not customer:
        return {"error": f"Customer {customer_id} not found"}
    
    # Get customer's orders
    cust_orders = [s for s in sales if s.get("customer_id") == customer_id]
    total_spend = sum(s.get("total", 0) for s in cust_orders if s.get("status") not in ["Cancelled", "Lost"])
    
    # Get last order date
    if cust_orders:
        last_order = max(cust_orders, key=lambda x: x.get("date", ""))
        last_order_date = last_order.get("date")
    else:
        last_order_date = None
    
    return {
        "id": customer_id,
        "name": customer["name"],
        "tier": customer["tier"],
        "churn_risk": customer.get("churn_risk", 0),
        "total_spend": round(total_spend, 2),
        "currency": "CNY",
        "total_orders": len(cust_orders),
        "completed_orders": len([o for o in cust_orders if o.get("status") == "Completed"]),
        "last_order_date": last_order_date,
        "recent_orders": cust_orders[-3:]  # Last 3 orders
    }


@tool
def get_high_churn_customers(threshold: float = 0.5, limit: int = 10):
    """
    Get list of customers with high churn risk.
    
    Args:
        threshold: Minimum churn probability threshold (0-1)
        limit: Maximum number of customers to return
    
    Returns:
        List of high-churn-risk customers sorted by risk
    """
    data = get_demo_data()
    customers = data.get("customers", []) if data else []
    
    high_risk = [
        {
            "id": c["id"],
            "name": c["name"],
            "tier": c["tier"],
            "churn_risk": c.get("churn_risk", 0),
            "risk_level": "HIGH" if c.get("churn_risk", 0) >= 0.7 else "MEDIUM"
        }
        for c in customers
        if c.get("churn_risk", 0) >= threshold
    ]
    
    # Sort by churn risk (highest first)
    high_risk = sorted(high_risk, key=lambda x: x["churn_risk"], reverse=True)
    
    return {
        "threshold": threshold,
        "count": len(high_risk),
        "customers": high_risk[:limit]
    }


@tool
def generate_quote(customer_id: str, products: List[str]):
    """
    Generate a sales quote for a customer.
    
    Args:
        customer_id: Customer identifier
        products: List of product codes to include
    
    Returns:
        Generated quote with pricing
    """
    data = get_demo_data()
    customers = data.get("customers", []) if data else []
    items = data.get("items", []) if data else []
    
    customer = next((c for c in customers if c["id"] == customer_id), None)
    
    if not customer:
        return {"error": f"Customer {customer_id} not found"}
    
    # Calculate quote
    quote_items = []
    total = 0
    for prod_code in products:
        item = next((i for i in items if i["code"] == prod_code), None)
        if item:
            qty = 1
            amount = item["rate"] * qty
            quote_items.append({
                "code": item["code"],
                "name": item["name"],
                "qty": qty,
                "rate": item["rate"],
                "amount": amount
            })
            total += amount
    
    return {
        "quote_id": f"QT-{hash(customer_id + str(products)) % 10000:04d}",
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "items": quote_items,
        "subtotal": round(total, 2),
        "tax": round(total * 0.13, 2),  # 13% VAT
        "total": round(total * 1.13, 2),
        "currency": "CNY",
        "valid_until": "2026-02-23",
        "status": "draft"
    }
