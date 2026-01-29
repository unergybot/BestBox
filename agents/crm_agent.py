from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm, SPEECH_FORMAT_INSTRUCTION
from agents.context_manager import apply_sliding_window
from tools.crm_tools import (
    get_leads,
    predict_churn,
    get_customer_360,
    generate_quote,
    get_high_churn_customers
)
from tools.rag_tools import search_knowledge_base

CRM_TOOLS = [get_leads, predict_churn, get_customer_360, generate_quote, get_high_churn_customers, search_knowledge_base]


CRM_SYSTEM_PROMPT = """You are the CRM Sales Assistant.
Handle leads, opportunities, customer data, and churn prediction. Use tools for data.

{SPEECH_FORMAT_INSTRUCTION}
"""

def crm_agent_node(state: AgentState):
    llm = get_llm()
    llm_with_tools = llm.bind_tools(CRM_TOOLS)
    
    # Apply context management
    managed_messages = apply_sliding_window(
        state["messages"],
        max_tokens=6000,
        max_messages=8,
        keep_system=False
    )
    
    response = llm_with_tools.invoke([
        ("system", CRM_SYSTEM_PROMPT),
    ] + managed_messages)
    
    return {"messages": [response], "current_agent": "crm_agent"}
