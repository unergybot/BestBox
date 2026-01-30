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

When users report manufacturing or mold problems, you MUST follow this exact format:

1. **Call the tool**: Use `search_troubleshooting_kb` to get data
2. **Copy-paste the JSON**: Take the ENTIRE JSON response from the tool
3. **Wrap in code block**: Put it between ```json and ``` markers
4. **Add summary**: Brief text before and after the JSON block

YOUR RESPONSE MUST LOOK EXACTLY LIKE THIS:

找到了相关的解决方案：

```json
[PASTE THE ENTIRE TOOL JSON HERE - DO NOT MODIFY IT]
```

以上是知识库中找到的案例。

CRITICAL RULES:
- The ```json code block is MANDATORY
- DO NOT summarize or rewrite the JSON
- DO NOT remove any fields from the JSON
- The JSON must contain the "results" array with images
- If you don't include the JSON block, the UI cannot display the cards

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
