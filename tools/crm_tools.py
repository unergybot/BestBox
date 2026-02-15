"""CRM tools with ERPNext-backed integration and demo fallback."""

from datetime import datetime
from functools import lru_cache
import json
import os
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from services.customer_config import get_integration_config
from services.erpnext_client import ERPNextClient

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


_crm_client: Optional[ERPNextClient] = None


def get_crm_backend() -> str:
    cfg = get_integration_config("crm")
    backend = os.getenv("CRM_BACKEND") or cfg.get("backend") or "demo"
    return str(backend).lower()


def get_crm_client() -> ERPNextClient:
    global _crm_client
    if _crm_client is None:
        cfg = get_integration_config("crm")
        _crm_client = ERPNextClient(
            url=os.getenv("CRM_URL") or cfg.get("base_url") or os.getenv("ERPNEXT_URL"),
            api_key=os.getenv("CRM_API_KEY") or os.getenv("ERPNEXT_API_KEY"),
            api_secret=os.getenv("CRM_API_SECRET") or os.getenv("ERPNEXT_API_SECRET"),
            site=os.getenv("CRM_SITE") or os.getenv("ERPNEXT_SITE", "bestbox.local"),
        )
    return _crm_client


def _normalize_lead(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("name", ""),
        "company": row.get("company_name") or row.get("lead_name") or "Unknown",
        "tier": row.get("customer_group") or "Unknown",
        "status": (row.get("status") or "Open").lower(),
        "score": int(row.get("score") or 60),
        "stage": row.get("status") or "Open",
        "source": row.get("source") or "unknown",
    }


def _get_leads_from_erpnext(status: str, tier: Optional[str], limit: int) -> Optional[List[Dict[str, Any]]]:
    client = get_crm_client()
    if get_crm_backend() not in {"erpnext", "erpnext_crm"} or not client.is_available():
        return None

    filters: Dict[str, Any] = {}
    if status and status.lower() != "all":
        filters["status"] = ["=", status.title()]

    fields = ["name", "lead_name", "company_name", "status", "source"]
    leads = client.get_list("Lead", fields=fields, filters=filters, limit=limit, order_by="modified desc")
    if leads is None:
        return None

    normalized = [_normalize_lead(lead) for lead in leads]
    if tier:
        normalized = [lead for lead in normalized if str(lead.get("tier", "")).lower() == tier.lower()]
    return normalized[:limit]


@tool
def get_leads(status: str = "active", tier: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get a list of sales leads/customers with their current score and status.
    
    Args:
        status: Lead status filter ("active", "all")
        tier: Customer tier filter ("Enterprise", "Mid-Market", "SMB")
        limit: Maximum number of leads to return
    
    Returns:
        List of leads with scoring and activity information
    """
    erp_results = _get_leads_from_erpnext(status=status, tier=tier, limit=limit)
    if erp_results is not None:
        return erp_results

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
def predict_churn(customer_id: str) -> Dict[str, Any]:
    """
    Predict the churn probability for a specific customer using ML models.
    
    Args:
        customer_id: Customer identifier (e.g., "CUS-003")
    
    Returns:
        Churn probability, risk level, and contributing factors
    """
    client = get_crm_client()
    if get_crm_backend() in {"erpnext", "erpnext_crm"} and client.is_available():
        customer = client.get_doc("Customer", customer_id)
        if customer:
            outstanding = float(customer.get("outstanding_amount") or 0)
            disabled = int(customer.get("disabled") or 0)
            churn_prob = 0.75 if disabled else (0.6 if outstanding > 0 else 0.2)
            risk_level = "HIGH" if churn_prob >= 0.7 else "MEDIUM" if churn_prob >= 0.4 else "LOW"
            return {
                "customer_id": customer_id,
                "customer_name": customer.get("customer_name") or customer.get("name"),
                "tier": customer.get("customer_group") or "Unknown",
                "churn_probability": round(churn_prob, 2),
                "risk_level": risk_level,
                "key_factors": [
                    f"Outstanding amount: {outstanding}",
                    f"Account disabled: {'yes' if disabled else 'no'}",
                ],
                "recommendation": "Immediate outreach required" if risk_level == "HIGH" else "Schedule check-in call",
                "source": "erpnext",
            }

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
def get_customer_360(customer_id: str) -> Dict[str, Any]:
    """
    Get a complete 360-degree view of a customer.
    
    Args:
        customer_id: Customer identifier (e.g., "CUS-001")
    
    Returns:
        Complete customer profile with orders, value, and engagement
    """
    client = get_crm_client()
    if get_crm_backend() in {"erpnext", "erpnext_crm"} and client.is_available():
        customer = client.get_doc("Customer", customer_id)
        if customer:
            invoices = client.get_list(
                "Sales Invoice",
                fields=["name", "grand_total", "outstanding_amount", "posting_date", "status"],
                filters={"customer": customer.get("name")},
                limit=50,
                order_by="posting_date desc",
            ) or []

            total_spend = sum(float(inv.get("grand_total") or 0) for inv in invoices)
            return {
                "id": customer_id,
                "name": customer.get("customer_name") or customer.get("name"),
                "tier": customer.get("customer_group") or "Unknown",
                "territory": customer.get("territory") or "Unknown",
                "currency": customer.get("default_currency") or "CNY",
                "total_spend": round(total_spend, 2),
                "total_orders": len(invoices),
                "completed_orders": len([inv for inv in invoices if str(inv.get("status", "")).lower() == "paid"]),
                "last_order_date": invoices[0].get("posting_date") if invoices else None,
                "recent_orders": invoices[:3],
                "source": "erpnext",
            }

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
def get_high_churn_customers(threshold: float = 0.5, limit: int = 10) -> Dict[str, Any]:
    """
    Get list of customers with high churn risk.
    
    Args:
        threshold: Minimum churn probability threshold (0-1)
        limit: Maximum number of customers to return
    
    Returns:
        List of high-churn-risk customers sorted by risk
    """
    client = get_crm_client()
    if get_crm_backend() in {"erpnext", "erpnext_crm"} and client.is_available():
        customers = client.get_list(
            "Customer",
            fields=["name", "customer_name", "customer_group", "disabled", "outstanding_amount"],
            limit=max(limit * 3, 30),
            order_by="modified desc",
        ) or []

        high_risk: List[Dict[str, Any]] = []
        for customer in customers:
            disabled = int(customer.get("disabled") or 0)
            outstanding = float(customer.get("outstanding_amount") or 0)
            churn_risk = 0.8 if disabled else (0.65 if outstanding > 0 else 0.25)
            if churn_risk < threshold:
                continue
            high_risk.append(
                {
                    "id": customer.get("name"),
                    "name": customer.get("customer_name") or customer.get("name"),
                    "tier": customer.get("customer_group") or "Unknown",
                    "churn_risk": churn_risk,
                    "risk_level": "HIGH" if churn_risk >= 0.7 else "MEDIUM",
                    "source": "erpnext",
                }
            )

        high_risk = sorted(high_risk, key=lambda x: x["churn_risk"], reverse=True)
        return {"threshold": threshold, "count": len(high_risk), "customers": high_risk[:limit]}

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
def generate_quote(customer_id: str, products: List[str]) -> Dict[str, Any]:
    """
    Generate a sales quote for a customer.
    
    Args:
        customer_id: Customer identifier
        products: List of product codes to include
    
    Returns:
        Generated quote with pricing
    """
    client = get_crm_client()
    if get_crm_backend() in {"erpnext", "erpnext_crm"} and client.is_available():
        customer = client.get_doc("Customer", customer_id)
        if customer:
            quote_items: List[Dict[str, Any]] = []
            total = 0.0
            for product_code in products:
                item = client.get_doc("Item", product_code)
                if not item:
                    continue
                rate = float(item.get("standard_rate") or item.get("valuation_rate") or 0)
                amount = rate
                quote_items.append(
                    {
                        "code": item.get("item_code") or product_code,
                        "name": item.get("item_name") or product_code,
                        "qty": 1,
                        "rate": rate,
                        "amount": amount,
                    }
                )
                total += amount

            now = datetime.utcnow()
            valid_until = now.replace(day=min(now.day, 28)).strftime("%Y-%m-%d")
            return {
                "quote_id": f"DRAFT-{customer_id}-{now.strftime('%Y%m%d%H%M%S')}",
                "customer_id": customer_id,
                "customer_name": customer.get("customer_name") or customer.get("name"),
                "items": quote_items,
                "subtotal": round(total, 2),
                "tax": round(total * 0.13, 2),
                "total": round(total * 1.13, 2),
                "currency": customer.get("default_currency") or "CNY",
                "valid_until": valid_until,
                "status": "draft",
                "source": "erpnext",
            }

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
