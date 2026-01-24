from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from agents.state import AgentState
from agents.router import router_node, route_decision
from agents.erp_agent import erp_agent_node, ERP_TOOLS
from agents.crm_agent import crm_agent_node, CRM_TOOLS
from agents.it_ops_agent import it_ops_agent_node, IT_OPS_TOOLS
from agents.oa_agent import oa_agent_node, OA_TOOLS
from agents.general_agent import general_agent_node, GENERAL_TOOLS
from langchain_core.messages import AIMessage, BaseMessage

# Combine all tools for the tool node
ALL_TOOLS = ERP_TOOLS + CRM_TOOLS + IT_OPS_TOOLS + OA_TOOLS + GENERAL_TOOLS
# Remove duplicates (search_knowledge_base is in multiple tool lists)
seen = set()
UNIQUE_TOOLS = []
for tool in ALL_TOOLS:
    if tool.name not in seen:
        seen.add(tool.name)
        UNIQUE_TOOLS.append(tool)
tools_node = ToolNode(UNIQUE_TOOLS)

def fallback_node(state: AgentState):
    """Fallback node for completely out-of-scope requests."""
    return {
        "messages": [AIMessage(content="I'm sorry, I can only help with enterprise-related tasks like ERP, CRM, IT Operations, and Office Automation. Could you please ask about one of these areas?")],
        "current_agent": "fallback"
    }

def should_continue(state: AgentState):
    """
    Check if the last message has tool calls.
    If so, route to 'tools'. Otherwise END.
    """
    last_message: BaseMessage = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
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
workflow.add_node("general_agent", general_agent_node)
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
        "general_agent": "general_agent",
        "fallback": "fallback"
    }
)

# Agent -> Tools or END
agent_names = ["erp_agent", "crm_agent", "it_ops_agent", "oa_agent", "general_agent"]
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
        "oa_agent": "oa_agent",
        "general_agent": "general_agent"
    }
)

workflow.add_edge("fallback", END)

# Compile
app = workflow.compile()
