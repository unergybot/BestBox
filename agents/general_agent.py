"""General agent for cross-domain queries and general assistance."""
from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm, SPEECH_FORMAT_INSTRUCTION
from agents.context_manager import apply_sliding_window
from tools.rag_tools import search_knowledge_base

GENERAL_TOOLS = [
    search_knowledge_base
]

GENERAL_SYSTEM_PROMPT = """You are the BestBox General Assistant.

Capabilities:
1. ERP/Finance: Purchase orders, inventory, vendors, financial reports
2. CRM/Sales: Customers, leads, deals, sales pipeline
3. IT Operations: Servers, logs, alerts, troubleshooting
4. Office Automation: Emails, scheduling, documents
5. Knowledge Base: Company policies, procedures, and Hudson Group information

Be concise and helpful. For greetings, offer assistance briefly.

{SPEECH_FORMAT_INSTRUCTION}
"""


def general_agent_node(state: AgentState):
    """
    General Agent node with context management.
    """
    llm = get_llm()
    llm_with_tools = llm.bind_tools(GENERAL_TOOLS)
    
    managed_messages = apply_sliding_window(
        state["messages"],
        max_tokens=6000,
        max_messages=8,
        keep_system=False
    )
    
    response = llm_with_tools.invoke([
        ("system", GENERAL_SYSTEM_PROMPT),
    ] + managed_messages)
    
    return {
        "messages": [response],
        "current_agent": "general_agent"
    }
