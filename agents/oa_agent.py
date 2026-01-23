from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm
from tools.oa_tools import (
    draft_email,
    schedule_meeting,
    generate_document
)
from tools.rag_tools import search_knowledge_base

OA_TOOLS = [draft_email, schedule_meeting, generate_document, search_knowledge_base]

OA_SYSTEM_PROMPT = """You are the Office Automation (OA) Agent.
You assist with email drafting, document generation, scheduling, and approvals.
Use available tools to perform actions.

You have access to a knowledge base via search_knowledge_base(query, domain).
Use it when you need specific procedures, policies, or technical information
beyond your training data. For Office Automation queries, use domain="oa" to filter results.
"""

def oa_agent_node(state: AgentState):
    llm = get_llm()
    llm_with_tools = llm.bind_tools(OA_TOOLS)
    
    response = llm_with_tools.invoke([
        ("system", OA_SYSTEM_PROMPT),
    ] + state["messages"])
    
    return {"messages": [response], "current_agent": "oa_agent"}
