from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm, SPEECH_FORMAT_INSTRUCTION
from agents.context_manager import apply_sliding_window
from tools.it_ops_tools import (
    query_system_logs,
    get_active_alerts,
    diagnose_fault
)
from tools.rag_tools import search_knowledge_base

IT_OPS_TOOLS = [query_system_logs, get_active_alerts, diagnose_fault, search_knowledge_base]

IT_OPS_SYSTEM_PROMPT = """You are the IT Operations Agent.
Handle system status, troubleshooting, logs, and incidents. Use tools for data.

{SPEECH_FORMAT_INSTRUCTION}
"""

def it_ops_agent_node(state: AgentState):
    llm = get_llm()
    llm_with_tools = llm.bind_tools(IT_OPS_TOOLS)
    
    managed_messages = apply_sliding_window(
        state["messages"],
        max_tokens=6000,
        max_messages=8,
        keep_system=False
    )
    
    response = llm_with_tools.invoke([
        ("system", IT_OPS_SYSTEM_PROMPT),
    ] + managed_messages)
    
    return {"messages": [response], "current_agent": "it_ops_agent"}
