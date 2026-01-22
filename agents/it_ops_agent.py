from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm
from tools.it_ops_tools import (
    query_system_logs,
    get_active_alerts,
    diagnose_fault
)

IT_OPS_TOOLS = [query_system_logs, get_active_alerts, diagnose_fault]

IT_OPS_SYSTEM_PROMPT = """You are the IT Operations Agent.
You assist with system status, troubleshooting, log analysis, and incident management.
Use available tools to check system health.
"""

def it_ops_agent_node(state: AgentState):
    llm = get_llm()
    llm_with_tools = llm.bind_tools(IT_OPS_TOOLS)
    
    response = llm_with_tools.invoke([
        ("system", IT_OPS_SYSTEM_PROMPT),
    ] + state["messages"])
    
    return {"messages": [response], "current_agent": "it_ops_agent"}
