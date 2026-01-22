from langchain_core.tools import tool
from typing import Optional, List

@tool
def get_leads(status: str = "active", limit: int = 5):
    """
    Get a list of sales leads with their current score and status.
    """
    return [
        {"id": "LD-501", "company": "Acme Corp", "status": "active", "score": 85, "stage": "proposal"},
        {"id": "LD-502", "company": "GlobalTech", "status": "active", "score": 78, "stage": "demo"},
        {"id": "LD-503", "company": "Stark Ind", "status": "active", "score": 92, "stage": "negotiation"},
    ][:limit]

@tool
def predict_churn(customer_id: str):
    """
    Predict the churn probability for a specific customer using ML models.
    """
    # Mock ML prediction
    return {
        "customer_id": customer_id,
        "churn_probability": 0.75,
        "risk_level": "HIGH",
        "key_factors": [
            "Decreased usage frequency (-40%)",
            "Pending support tickets (3)",
            "Renewal date approaching (30 days)"
        ]
    }

@tool
def get_customer_360(customer_id: str):
    """
    Get a complete 360-degree view of a customer.
    """
    return {
        "id": customer_id,
        "name": "Wayne Enterprises",
        "segment": "Enterprise",
        "total_spend": 500000,
        "active_deals": 2,
        "last_contact": "2026-01-20"
    }

@tool
def generate_quote(customer_id: str, products: List[str]):
    """
    Generate a sales quote for a customer.
    """
    return {
        "quote_id": "QT-9001",
        "customer_id": customer_id,
        "products": products,
        "total_amount": 25000,
        "expiry": "2026-02-23",
        "status": "draft"
    }
