from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm
from tools.erp_tools import (
    get_purchase_orders,
    get_inventory_levels,
    get_financial_summary,
    get_vendor_price_trends,
    get_procurement_summary,
    get_top_vendors
)

ERP_TOOLS = [
    get_purchase_orders,
    get_inventory_levels,
    get_financial_summary,
    get_vendor_price_trends,
    get_procurement_summary,
    get_top_vendors
]


ERP_SYSTEM_PROMPT = """You are the ERP Copilot for BestBox Manufacturing Ltd.
You assist with finance, procurement, inventory, and vendor management.

CRITICAL: You MUST use your tools to answer ANY question about data. NEVER make up hypothetical data.

Available tools:
- get_top_vendors: For questions about top/main vendors or supplier rankings
- get_procurement_summary: For vendor spend breakdowns and procurement analysis
- get_purchase_orders: For purchase order details, filtering by vendor, date, or status
- get_inventory_levels: For warehouse stock levels and low stock alerts
- get_financial_summary: For P&L, revenue, expenses, and margin data
- get_vendor_price_trends: For analyzing price changes with specific vendors

When asked about vendors, suppliers, or spending:
1. ALWAYS call get_top_vendors or get_procurement_summary first
2. Present the ACTUAL data returned from the tool
3. Never say "I don't have access" - you DO have access via these tools
"""

def erp_agent_node(state: AgentState):
    """
    ERP Agent node execution.
    """
    llm = get_llm()
    llm_with_tools = llm.bind_tools(ERP_TOOLS)
    
    response = llm_with_tools.invoke([
        ("system", ERP_SYSTEM_PROMPT),
    ] + state["messages"])
    
    return {
        "messages": [response],
        "current_agent": "erp_agent"
    }
