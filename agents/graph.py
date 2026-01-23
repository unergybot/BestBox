from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from agents.state import AgentState
from agents.router import router_node, route_decision
from agents.erp_agent import erp_agent_node, ERP_TOOLS
from agents.crm_agent import crm_agent_node, CRM_TOOLS
from agents.it_ops_agent import it_ops_agent_node, IT_OPS_TOOLS
from agents.oa_agent import oa_agent_node, OA_TOOLS
from tools.rag_tools import search_knowledge_base
from langchain_core.messages import AIMessage

# Combine all tools for the tool node
ALL_TOOLS = ERP_TOOLS + CRM_TOOLS + IT_OPS_TOOLS + OA_TOOLS
tools_node = ToolNode(ALL_TOOLS)

def fallback_node(state: AgentState):
    """Fallback node for unclear intents."""
    return {
        "messages": [AIMessage(content="I'm not sure which specialist agent to route this to. Could you please clarify if this is related to ERP, CRM, IT Ops, or Office Automation?")],
        "current_agent": "fallback"
    }

def should_continue(state: AgentState):
    """
    Check if the last message has tool calls.
    If so, route to 'tools'. Otherwise END.
    """
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

def route_after_tools(state: AgentState):
    """
    After tools execute, return to the agent that called them.
    """
    return state["current_agent"]

# Build the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("router", router_node)
workflow.add_node("erp_agent", erp_agent_node)
workflow.add_node("crm_agent", crm_agent_node)
workflow.add_node("it_ops_agent", it_ops_agent_node)
workflow.add_node("oa_agent", oa_agent_node)
workflow.add_node("fallback", fallback_node)
workflow.add_node("tools", tools_node)

# Add edges
workflow.set_entry_point("router")

# Router -> Agent
workflow.add_conditional_edges(
    "router",
    route_decision,
    {
        "erp_agent": "erp_agent",
        "crm_agent": "crm_agent",
        "it_ops_agent": "it_ops_agent",
        "oa_agent": "oa_agent",
        "fallback": "fallback"
    }
)

# Agent -> Tools or END
agent_names = ["erp_agent", "crm_agent", "it_ops_agent", "oa_agent"]
for agent in agent_names:
    workflow.add_conditional_edges(
        agent,
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )

# Tools -> Back to Agent (loop)
workflow.add_conditional_edges(
    "tools",
    route_after_tools,
    {
        "erp_agent": "erp_agent",
        "crm_agent": "crm_agent",
        "it_ops_agent": "it_ops_agent",
        "oa_agent": "oa_agent"
    }
)

workflow.add_edge("fallback", END)

# Compile
app = workflow.compile()
