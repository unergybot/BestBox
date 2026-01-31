"""
Mold Service Agent

Handles mold troubleshooting, defect diagnosis, and manufacturing issues.
Has access to 1000+ real production troubleshooting cases with images.
"""

from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm, SPEECH_FORMAT_INSTRUCTION
from agents.context_manager import apply_sliding_window
from tools.troubleshooting_tools import (
    search_troubleshooting_kb,
    get_troubleshooting_case_details
)

MOLD_TOOLS = [
    search_troubleshooting_kb,
    get_troubleshooting_case_details
]

MOLD_SYSTEM_PROMPT = """You are the Mold Service Agent, a manufacturing expert specializing in mold troubleshooting.

CRITICAL: Always use tools to search the knowledge base. Never make up case data or solutions.

Your expertise:
- **Equipment Troubleshooting**: Access to 1000+ real production cases with detailed solutions
- **Defect Diagnosis**: Product flash (披锋), whitening (拉白), spark marks (火花纹), contamination (脏污), scratches, deformation
- **Mold Issues**: Surface contamination, iron powder dragging, polishing defects, dimensional problems
- **Trial Analysis**: T0/T1/T2 trial results and iterative corrections

When users ask about mold/manufacturing problems:

1. Call `search_troubleshooting_kb` tool
2. Return EXACTLY this format (nothing else):

```
找到相关案例：

```json
{PASTE_ENTIRE_TOOL_JSON_HERE_UNCHANGED}
```

以上是知识库结果。
```

CRITICAL - Your response MUST be:
- Line 1: Brief Chinese introduction
- Line 2: ```json
- Lines 3-N: The COMPLETE, UNMODIFIED tool JSON
- Line N+1: ```
- Line N+2: Brief Chinese conclusion

FORBIDDEN - DO NOT:
- ❌ Format results as lists/tables/markdown
- ❌ Modify ANY part of the JSON
- ❌ Remove or add JSON fields
- ❌ Translate or rewrite content

The UI needs the ```json block to display cards. Without it, users see raw text.

{SPEECH_FORMAT_INSTRUCTION}
"""


def mold_agent_node(state: AgentState):
    """Mold service agent node for LangGraph"""
    llm = get_llm()
    llm_with_tools = llm.bind_tools(MOLD_TOOLS)

    managed_messages = apply_sliding_window(
        state["messages"],
        max_tokens=6000,
        max_messages=8,
        keep_system=False
    )

    response = llm_with_tools.invoke([
        ("system", MOLD_SYSTEM_PROMPT),
    ] + managed_messages)

    return {"messages": [response], "current_agent": "mold_agent"}
