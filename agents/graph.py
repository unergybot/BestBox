from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from agents.state import AgentState
from agents.router import router_node, route_decision
from agents.erp_agent import erp_agent_node, ERP_TOOLS
from agents.crm_agent import crm_agent_node, CRM_TOOLS
from agents.it_ops_agent import it_ops_agent_node, IT_OPS_TOOLS
from agents.oa_agent import oa_agent_node, OA_TOOLS
from agents.mold_agent import mold_agent_node, MOLD_TOOLS
from agents.general_agent import general_agent_node, GENERAL_TOOLS
from agents.react_node import react_loop
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
import logging
import os
import time
from typing import Any, Dict, List, Set

# Import plugin system
from plugins import PluginRegistry, HookRunner, HookEvent

logger = logging.getLogger(__name__)

# Initialize plugin system
_plugin_registry = PluginRegistry()
_hook_runner = HookRunner(_plugin_registry)

# Combine all tools for the tool node
ALL_TOOLS = ERP_TOOLS + CRM_TOOLS + IT_OPS_TOOLS + OA_TOOLS + MOLD_TOOLS + GENERAL_TOOLS

# Add plugin tools
plugin_tools = _plugin_registry.get_all_tools()
if plugin_tools:
    logger.info(f"Adding {len(plugin_tools)} plugin tools to graph")
    ALL_TOOLS.extend(plugin_tools)

# Add dynamically discovered OpenAPI tools (optional)
openapi_spec_url = os.getenv("OPENAPI_SPEC_URL")
if openapi_spec_url:
    try:
        from tools.discovery import load_tools_from_spec

        allowlist_raw = os.getenv("OPENAPI_TOOL_ALLOWLIST", "").strip()
        allowlist = [item.strip() for item in allowlist_raw.split(",") if item.strip()]
        auth_header = os.getenv("OPENAPI_AUTH_HEADER")

        openapi_tools = load_tools_from_spec(
            spec_url=openapi_spec_url,
            allowlist=allowlist,
            auth_header=auth_header,
        )

        if openapi_tools:
            logger.info(f"Adding {len(openapi_tools)} OpenAPI-discovered tools")
            ALL_TOOLS.extend(openapi_tools)
    except Exception as exc:
        logger.warning(f"Failed to load OpenAPI tools: {exc}")

# Remove duplicates (search_knowledge_base is in multiple tool lists)
seen = set()
UNIQUE_TOOLS = []
for tool in ALL_TOOLS:
    if tool.name not in seen:
        seen.add(tool.name)
        UNIQUE_TOOLS.append(tool)

tools_node = ToolNode(UNIQUE_TOOLS)


PROTECTED_TOOL_ROLES: Dict[str, Set[str]] = {
    "get_financial_summary": {"admin", "finance"},
    "get_procurement_summary": {"admin", "procurement", "finance"},
    "get_top_vendors": {"admin", "procurement", "finance"},
    "get_purchase_orders": {"admin", "procurement", "finance", "viewer"},
}


def _extract_requested_tools(state: AgentState) -> List[str]:
    """Return requested tool names from the latest AI message tool calls."""
    messages = state.get("messages") or []
    if not messages:
        return []

    last_message = messages[-1]
    if not isinstance(last_message, AIMessage):
        return []

    tool_calls = getattr(last_message, "tool_calls", None) or []
    names: List[str] = []
    for tool_call in tool_calls:
        if isinstance(tool_call, dict):
            name = tool_call.get("name")
            if isinstance(name, str) and name:
                names.append(name)
    return names


def _get_user_roles(state: AgentState) -> Set[str]:
    """Extract normalized user roles from AgentState."""
    user_context = state.get("user_context") or {}
    roles = user_context.get("roles", [])
    if isinstance(roles, str):
        return {roles.lower()}
    if isinstance(roles, list):
        return {str(role).lower() for role in roles if role}
    return set()


def _unauthorized_tools(state: AgentState) -> List[str]:
    """Return list of protected tools current user is not allowed to call."""
    requested_tools = _extract_requested_tools(state)
    if not requested_tools:
        return []

    strict_mode = os.getenv("STRICT_TOOL_AUTH", "false").lower() == "true"
    user_roles = _get_user_roles(state)

    denied: List[str] = []
    for tool_name in requested_tools:
        required_roles = PROTECTED_TOOL_ROLES.get(tool_name)
        if not required_roles:
            continue

        if not user_roles:
            if strict_mode:
                denied.append(tool_name)
            continue

        if user_roles.intersection(required_roles):
            continue
        denied.append(tool_name)

    return denied

def router_node_with_hooks(state: AgentState):
    """Router node with lifecycle hooks."""
    # Run BEFORE_ROUTING hooks
    state = _hook_runner.run_sync(HookEvent.BEFORE_ROUTING, state)

    # Execute router
    result = router_node(state)

    # Merge result into state
    if isinstance(result, dict):
        state.update(result)

    # Run AFTER_ROUTING hooks
    state = _hook_runner.run_sync(HookEvent.AFTER_ROUTING, state)

    return state


def tools_node_with_hooks(state: AgentState):
    """Tools node with lifecycle hooks."""
    # Run BEFORE_TOOL_CALL hooks
    state = _hook_runner.run_sync(HookEvent.BEFORE_TOOL_CALL, state)

    denied_tools = _unauthorized_tools(state)
    if denied_tools:
        logger.warning(f"Denied tool calls due to role check: {', '.join(denied_tools)}")

        context = state.get("context") or {}
        context["authz_denied_tools"] = denied_tools

        denied_message = AIMessage(
            content=(
                "Permission denied for tool execution: "
                f"{', '.join(denied_tools)}. "
                "Please request access from an administrator."
            )
        )

        state["context"] = context
        state["messages"] = [*state.get("messages", []), denied_message]

        # Preserve hook lifecycle symmetry even when skipping tool invocation.
        state = _hook_runner.run_sync(HookEvent.AFTER_TOOL_CALL, state)
        return state

    # Extract tool call info before execution (for audit metadata)
    messages = state.get("messages", [])
    tool_name = None
    tool_params = {}
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            tool_call = last_message.tool_calls[0]
            if isinstance(tool_call, dict):
                tool_name = tool_call.get("name")
                tool_params = tool_call.get("args", {})
            else:
                tool_name = getattr(tool_call, "name", None)
                tool_params = getattr(tool_call, "args", {})

    # Start timing
    start_time = time.time()

    # Execute tools
    result = tools_node.invoke(state)

    # Extract tool result from response messages
    tool_result = None
    if isinstance(result, dict):
        result_messages = result.get("messages", [])
        for msg in reversed(result_messages):
            if isinstance(msg, ToolMessage):
                tool_result = msg.content
                break

    # Merge result into state
    if isinstance(result, dict):
        state.update(result)

    # Run AFTER_TOOL_CALL hooks with execution metadata
    metadata = {
        "tool_name": tool_name,
        "tool_params": tool_params,
        "tool_result": tool_result,
        "start_time": start_time,
    }
    state = _hook_runner.run_sync(HookEvent.AFTER_TOOL_CALL, state, metadata=metadata)

    return state


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

# Add nodes (use hooked versions for router and tools)
workflow.add_node("router", router_node_with_hooks)
workflow.add_node("erp_agent", erp_agent_node)
workflow.add_node("crm_agent", crm_agent_node)
workflow.add_node("it_ops_agent", it_ops_agent_node)
workflow.add_node("oa_agent", oa_agent_node)
workflow.add_node("mold_agent", mold_agent_node)
workflow.add_node("general_agent", general_agent_node)
workflow.add_node("fallback", fallback_node)
workflow.add_node("tools", tools_node_with_hooks)

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
        "mold_agent": "mold_agent",
        "general_agent": "general_agent",
        "fallback": "fallback"
    }
)

# Agent -> Tools or END
agent_names = ["erp_agent", "crm_agent", "it_ops_agent", "oa_agent", "mold_agent", "general_agent"]
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
        "mold_agent": "mold_agent",
        "general_agent": "general_agent"
    }
)

workflow.add_edge("fallback", END)

# Compile
app = workflow.compile()

# ============================================================
# ReAct Graph (Parallel Path)
# ============================================================


def react_node_wrapper(state: AgentState):
    """Execute the ReAct loop using all available tools."""
    tool_objects = {tool.name: tool for tool in UNIQUE_TOOLS}
    tool_names = [tool.name for tool in UNIQUE_TOOLS]
    return react_loop(state=state, available_tools=tool_names, tool_objects=tool_objects)


react_workflow = StateGraph(AgentState)

react_workflow.add_node("router", router_node_with_hooks)
react_workflow.add_node("react", react_node_wrapper)
react_workflow.add_node("fallback", fallback_node)

react_workflow.set_entry_point("router")


def route_to_react_or_fallback(state: AgentState) -> str:
    """Route to ReAct node unless fallback is needed."""
    return "fallback" if state.get("current_agent") == "fallback" else "react"


react_workflow.add_conditional_edges(
    "router",
    route_to_react_or_fallback,
    {
        "react": "react",
        "fallback": "fallback",
    },
)

react_workflow.add_edge("react", END)
react_workflow.add_edge("fallback", END)

react_app = react_workflow.compile()
