"""
Mold Service Agent

Handles mold troubleshooting, defect diagnosis, and manufacturing issues.
Has access to 1000+ real production troubleshooting cases with images.

Enhanced with VLM (Vision-Language Model) capabilities for real-time
image and document analysis.
"""

import os
from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm, SPEECH_FORMAT_INSTRUCTION
from agents.context_manager import apply_sliding_window
from tools.troubleshooting_tools import (
    search_troubleshooting_kb,
    get_troubleshooting_case_details,
    find_similar_defects
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
    find_similar_defects
]

# Add VLM tools if enabled and available
if VLM_ENABLED and VLM_TOOLS_AVAILABLE:
    MOLD_TOOLS.extend([
        analyze_image_realtime,
        analyze_document_realtime,
        compare_images
    ])

# Base system prompt - SIMPLIFIED for better instruction following
MOLD_SYSTEM_PROMPT_BASE = """你是模具故障排除助手。

## 规则（必须严格遵守）

1. 用户问问题时，先调用 `search_troubleshooting_kb` 工具搜索知识库
2. 收到工具返回的JSON后，**原样输出**，不要修改任何内容
3. **绝对禁止**编造案例、解决方案或case_id

## 输出格式

[SPEECH]用一句话总结搜索结果[/SPEECH]

找到相关案例：

```json
{这里直接粘贴工具返回的完整JSON，一个字都不要改}
```

以上是知识库结果。

## 示例

工具返回：
{"query":"披锋","results":[{"case_id":"TS-123","solution":"加铁0.03mm"}]}

你的输出：
[SPEECH]找到1个披锋相关案例，解决方案是加铁0.03mm。[/SPEECH]

找到相关案例：

```json
{"query":"披锋","results":[{"case_id":"TS-123","solution":"加铁0.03mm"}]}
```

以上是知识库结果。

## 严禁

- ❌ 修改JSON中的任何字段
- ❌ 添加工具没有返回的案例
- ❌ 编造case_id（如把ED736A0501改成ED736A0502）
- ❌ 编造解决方案"""

# VLM enhancement section
VLM_ENHANCEMENT = """

## Enhanced Visual Analysis Capabilities

You now have access to advanced VLM (Vision-Language Model) analysis tools:

**Real-time Image Analysis (`analyze_image_realtime`):**
- Use when users share images of defects during conversation
- Provides detailed defect identification, severity assessment, and suggested actions
- Results typically in 15-30 seconds
- Example: "分析这张图片中的缺陷" → call analyze_image_realtime

**Document Analysis (`analyze_document_realtime`):**
- Use for PDF/Excel files shared during conversation
- Extracts key insights, embedded images, and topics
- Correlates with known issues in knowledge base
- Example: "帮我分析这份报告" → call analyze_document_realtime

**Image Comparison (`compare_images`):**
- Compare new defect images with historical cases
- Identify similar defect patterns across multiple images
- Helps correlate new issues with solved problems
- Example: "这个缺陷和之前的案例相似吗" → call compare_images

**Find Similar Defects (`find_similar_defects`):**
- Automatically analyze an uploaded image and search for similar cases
- One-step workflow: VLM Analysis → Semantic Search
- Use when user uploads an image and asks "Have we seen this before?" or "Find similar cases"
- Example: "查找类似案例" → call find_similar_defects

**Enhanced Search Results:**
When using `search_troubleshooting_kb`, results now include:
- VLM-extracted tags, topics, and entity mentions
- Confidence scores for relevance
- Rich image descriptions from VLM analysis
- Severity indicators and suggested actions

**Workflow for Image-Related Queries:**
1. If user provides an image → First use `analyze_image_realtime` to understand the defect
2. Use the defect type/keywords from analysis → Search KB with `search_troubleshooting_kb`
3. If similar cases found → Use `compare_images` to find the closest match
4. Combine VLM insights with KB results for comprehensive response

**Important Notes:**
- VLM analysis may take 15-60 seconds - inform user if needed
- Always search KB after VLM analysis to find related cases
- Use Chinese for all responses unless user uses English"""

# Build final system prompt
# Note: SPEECH instruction is now integrated into MOLD_SYSTEM_PROMPT_BASE
# to avoid conflicting format instructions
if VLM_ENABLED and VLM_TOOLS_AVAILABLE:
    MOLD_SYSTEM_PROMPT = MOLD_SYSTEM_PROMPT_BASE + VLM_ENHANCEMENT
else:
    MOLD_SYSTEM_PROMPT = MOLD_SYSTEM_PROMPT_BASE


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


# Expose tools list for graph registration
def get_mold_tools():
    """Get the list of tools available for the mold agent"""
    return MOLD_TOOLS


def get_mold_system_prompt():
    """Get the mold agent system prompt"""
    return MOLD_SYSTEM_PROMPT
