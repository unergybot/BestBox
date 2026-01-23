from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm
from tools.erp_tools import (
    get_purchase_orders,
    get_inventory_levels,
    get_financial_summary,
    get_vendor_price_trends,
    get_procurement_summary
)

ERP_TOOLS = [
    get_purchase_orders,
    get_inventory_levels,
    get_financial_summary,
    get_vendor_price_trends,
    get_procurement_summary
]


ERP_SYSTEM_PROMPT = """You are the ERP Copilot.
You assist with finance, procurement, inventory, and vendor management.
You have access to tools to query the ERP system.
Use them to answer user questions with real data.
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
