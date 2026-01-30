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

When users report manufacturing or mold problems:
1. **ALWAYS use `search_troubleshooting_kb` tool first** to search the knowledge base
   - Query examples: "产品披锋", "模具表面污染", "火花纹残留"
   - Use filters for specific parts or trial versions
2. **Return the EXACT tool output in a markdown code block**:
   - DO NOT modify, rewrite, or summarize the JSON from the tool
   - Wrap the EXACT tool JSON in ```json code blocks
   - Preserve ALL fields including image_url, image_id, etc.
   - Add a brief introduction before the code block
3. **After the JSON block, add a brief summary**:
   - Mention the number of solutions found
   - Highlight successful cases (result_t2: OK)
   - Note image availability

CRITICAL: Never invent case IDs, part numbers, or image URLs. Only use data from the tool.

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
