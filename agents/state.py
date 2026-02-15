from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class ReasoningStep(TypedDict):
    """
    A single step in the ReAct reasoning trace.
    """
    type: Literal["think", "act", "observe", "answer"]
    content: str
    tool_name: Optional[str]
    tool_args: Optional[Dict[str, Any]]
    timestamp: float


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


class UserContext(TypedDict, total=False):
    """
    Per-request authenticated user context for tool authorization.
    """
    user_id: str
    roles: List[str]
    org_id: str
    permissions: List[str]


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

    # ReAct reasoning trace (optional)
    reasoning_trace: Optional[List[ReasoningStep]]

    # Session ID for persistence (optional)
    session_id: Optional[str]

    # Authenticated user context for RBAC-aware tool calls (optional)
    user_context: Optional[UserContext]
