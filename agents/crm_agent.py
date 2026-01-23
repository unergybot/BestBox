from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm
from tools.crm_tools import (
    get_leads,
    predict_churn,
    get_customer_360,
    generate_quote
)
from tools.rag_tools import search_knowledge_base

CRM_TOOLS = [get_leads, predict_churn, get_customer_360, generate_quote, search_knowledge_base]

CRM_SYSTEM_PROMPT = """You are the CRM Sales Assistant.
You assist with leads, opportunities, customer data, and sales churn prediction.
Use available tools to fetch real CRM data.

You have access to a knowledge base via search_knowledge_base(query, domain).
Use it when you need specific procedures, policies, or technical information
beyond your training data. For CRM queries, use domain="crm" to filter results.
"""

def crm_agent_node(state: AgentState):
    llm = get_llm()
    llm_with_tools = llm.bind_tools(CRM_TOOLS)
    
    response = llm_with_tools.invoke([
        ("system", CRM_SYSTEM_PROMPT),
    ] + state["messages"])
    
    return {"messages": [response], "current_agent": "crm_agent"}
