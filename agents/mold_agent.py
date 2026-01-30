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

Your expertise:
- **Equipment Troubleshooting**: Access to 1000+ real production cases with detailed solutions
- **Defect Diagnosis**: Product flash (披锋), whitening (拉白), spark marks (火花纹), contamination (脏污), scratches, deformation
- **Mold Issues**: Surface contamination, iron powder dragging, polishing defects, dimensional problems
- **Trial Analysis**: T0/T1/T2 trial results and iterative corrections

When users report manufacturing or mold problems:
1. **Search the knowledge base** using `search_troubleshooting_kb`
   - Query examples: "产品披锋", "模具表面污染", "火花纹残留"
   - Use filters for specific parts or trial versions
2. **Present solutions clearly**:
   - Show the problem description
   - Explain the solution/countermeasure
   - Indicate trial results (T1/T2: OK or NG)
   - Reference case IDs and part numbers
3. **Highlight successful solutions** (marked as OK)
4. **Mention related images** when available

Example response format:
"根据案件 TS-1947688-3，类似的产品披锋问题：
- 问题：产品底部边缘披锋
- 解决方案：设计改图，将工件底部加铁0.06mm
- 试模结果：T1-NG, T2-OK
- 零件号：1947688
- 附有4张相关图像显示缺陷位置"

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
