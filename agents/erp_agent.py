from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm, SPEECH_FORMAT_INSTRUCTION
from agents.context_manager import apply_sliding_window
from tools.erp_tools import (
    get_purchase_orders,
    get_inventory_levels,
    get_financial_summary,
    get_vendor_price_trends,
    get_procurement_summary,
    get_top_vendors
)
from tools.rag_tools import search_knowledge_base

ERP_TOOLS = [
    get_purchase_orders,
    get_inventory_levels,
    get_financial_summary,
    get_vendor_price_trends,
    get_procurement_summary,
    get_top_vendors,
    search_knowledge_base
]


ERP_SYSTEM_PROMPT = """You are the ERP Copilot for BestBox. You handle finance, procurement, inventory, and vendor management.

CRITICAL: Always use tools to get data. Never make up numbers.

Tools:
- get_top_vendors: Vendor rankings
- get_procurement_summary: Spend breakdowns
- get_purchase_orders: PO details
- get_inventory_levels: Stock levels
- get_financial_summary: P&L, revenue, expenses
- get_vendor_price_trends: Price analysis
- search_knowledge_base: Procedures and policies (domain="erp")

{SPEECH_FORMAT_INSTRUCTION}
"""

def erp_agent_node(state: AgentState):
    """
    ERP Agent node execution with context management.
    """
    llm = get_llm()
    llm_with_tools = llm.bind_tools(ERP_TOOLS)
    
    # Apply context management to prevent overflow
    managed_messages = apply_sliding_window(
        state["messages"],
        max_tokens=6000,  # Leave room for response
        max_messages=8,
        keep_system=False
    )
    
    response = llm_with_tools.invoke([
        ("system", ERP_SYSTEM_PROMPT),
    ] + managed_messages)
    
    return {
        "messages": [response],
        "current_agent": "erp_agent"
    }
