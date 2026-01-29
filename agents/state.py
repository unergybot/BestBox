from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class PluginContext(TypedDict, total=False):
    """
    Context for plugin system integration.
    """
    # Names of active plugins
    active_plugins: List[str]

    # Results from plugin tool calls
    tool_results: Dict[str, Any]

    # Data stored by hook handlers
    hook_data: Dict[str, Any]


class AgentState(TypedDict):
    """
    Shared state for the BestBox LangGraph agents.
    """
    # Conversation history (appended to by each node)
    messages: Annotated[List[BaseMessage], add_messages]

    # Current active sub-agent (erp, crm, it_ops, oa)
    current_agent: str

    # Counter for SLA monitoring (max 5 tool calls)
    tool_calls: int

    # Confidence score of the last decision (0.0 - 1.0)
    confidence: float

    # Retrieved context from RAG or other agents
    context: Dict[str, Any]

    # Plan for the current task (list of steps)
    plan: List[str]

    # Current step index in the plan
    step: int

    # Plugin system context
    plugin_context: Optional[PluginContext]
