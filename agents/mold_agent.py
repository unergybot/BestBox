"""
Mold Service Agent

Handles mold troubleshooting, defect diagnosis, and manufacturing issues.
Has access to 1000+ real production troubleshooting cases with images.

Enhanced with VLM (Vision-Language Model) capabilities for real-time
image and document analysis.
"""

import os
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage
from agents.state import AgentState
from agents.utils import get_llm, SPEECH_FORMAT_INSTRUCTION
from agents.context_manager import apply_sliding_window
import uuid
from tools.troubleshooting_tools import (
    search_troubleshooting_kb,
    get_troubleshooting_case_details,
    find_similar_defects,
    # NEW: Structured/Hybrid search tools
    search_troubleshooting_structured,
    save_troubleshooting_learning,
    learn_troubleshooting_synonym,
)

# Import VLM tools if available
VLM_ENABLED = os.getenv("VLM_ENABLED", "false").lower() == "true"

try:
    from tools.document_tools import (
        analyze_image_realtime,
        analyze_document_realtime,
        compare_images
    )
    VLM_TOOLS_AVAILABLE = True
except ImportError:
    VLM_TOOLS_AVAILABLE = False

# Build tools list based on availability
MOLD_TOOLS = [
    search_troubleshooting_kb,
    get_troubleshooting_case_details,
    find_similar_defects,
    # NEW: Structured/Hybrid search tools
    search_troubleshooting_structured,
    save_troubleshooting_learning,
    learn_troubleshooting_synonym,
]

# Add VLM tools if enabled and available
if VLM_ENABLED and VLM_TOOLS_AVAILABLE:
    MOLD_TOOLS.extend([
        analyze_image_realtime,
        analyze_document_realtime,
        compare_images
    ])

# Base system prompt - Condensed for context efficiency
MOLD_SYSTEM_PROMPT_BASE = """You are the Mold Service Agent.

## MANDATORY: Tool Use on EVERY Query
You MUST call a search tool for EVERY user question, even if you already answered a similar question before.
NEVER reuse previous results or answer from memory. Each query deserves a fresh search.
If the user asks the same question again, call the tool again.

## Tools
- `search_troubleshooting_kb`: Semantic search for "how to solve X" questions
- `search_troubleshooting_structured`: SQL+Vector search for counting/filtering/statistics

## Response Rules
IMPORTANT: Frontend automatically renders tool results as cards. DO NOT copy JSON data.

After tool calls, provide BRIEF analysis in Chinese:
1. Summarize findings (e.g., "找到X个案例")
2. Highlight key solutions and patterns
3. Point out most relevant cases

Example:
```
找到3个披锋案例。主要解决方向：加铁0.03-0.06mm修正间隙。建议参考案例1。
```

DO: Use tools for EVERY question, provide analysis, use Chinese
DO NOT: Copy JSON, make up data, output json blocks, answer without calling tools
"""


# VLM enhancement section - condensed
VLM_ENHANCEMENT = """

## VLM Tools
- `analyze_image_realtime`: Analyze defect images (15-30s)
- `analyze_document_realtime`: Analyze PDF/Excel reports
- `compare_images`: Compare images with historical cases
- `find_similar_defects`: Analyze image + search similar cases

For image queries: analyze_image_realtime → search_troubleshooting_kb → compare_images"""

# Build final system prompt
# Note: SPEECH instruction is now integrated into MOLD_SYSTEM_PROMPT_BASE
# to avoid conflicting format instructions
if VLM_ENABLED and VLM_TOOLS_AVAILABLE:
    MOLD_SYSTEM_PROMPT = MOLD_SYSTEM_PROMPT_BASE + VLM_ENHANCEMENT
else:
    MOLD_SYSTEM_PROMPT = MOLD_SYSTEM_PROMPT_BASE


def _is_tool_result_pass(messages) -> bool:
    """Check if the last message is a ToolMessage (meaning tools just ran)."""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            return True
        if isinstance(msg, HumanMessage):
            return False
    return False


def _extract_user_query(messages) -> str:
    """Extract the latest user query from messages."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            return content
    return ""


def mold_agent_node(state: AgentState):
    """Mold service agent node for LangGraph"""
    llm = get_llm()
    llm_with_tools = llm.bind_tools(MOLD_TOOLS)

    managed_messages = apply_sliding_window(
        state["messages"],
        max_tokens=4000,
        max_messages=6,
        keep_system=False
    )

    response = llm_with_tools.invoke([
        ("system", MOLD_SYSTEM_PROMPT),
    ] + managed_messages)

    # If the LLM skipped tool calling on the first pass (no prior ToolMessage),
    # force a search_troubleshooting_kb call so the frontend always gets card data.
    if (isinstance(response, AIMessage)
            and not response.tool_calls
            and not _is_tool_result_pass(state["messages"])):
        user_query = _extract_user_query(state["messages"])
        if user_query:
            tool_call_id = f"forced_{uuid.uuid4().hex[:8]}"
            forced_response = AIMessage(
                content="",
                tool_calls=[{
                    "id": tool_call_id,
                    "name": "search_troubleshooting_kb",
                    "args": {"query": user_query}
                }]
            )
            return {"messages": [forced_response], "current_agent": "mold_agent"}

    return {"messages": [response], "current_agent": "mold_agent"}


# Expose tools list for graph registration
def get_mold_tools():
    """Get the list of tools available for the mold agent"""
    return MOLD_TOOLS


def get_mold_system_prompt():
    """Get the mold agent system prompt"""
    return MOLD_SYSTEM_PROMPT
