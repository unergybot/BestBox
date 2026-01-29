from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.utils import get_llm, SPEECH_FORMAT_INSTRUCTION
from agents.context_manager import apply_sliding_window
from tools.oa_tools import (
    draft_email,
    schedule_meeting,
    generate_document
)
from tools.rag_tools import search_knowledge_base

OA_TOOLS = [draft_email, schedule_meeting, generate_document, search_knowledge_base]

OA_SYSTEM_PROMPT = """You are the Office Automation (OA) Agent.
Handle emails, documents, scheduling, and approvals. Use tools for actions.

{SPEECH_FORMAT_INSTRUCTION}
"""

def oa_agent_node(state: AgentState):
    llm = get_llm()
    llm_with_tools = llm.bind_tools(OA_TOOLS)
    
    managed_messages = apply_sliding_window(
        state["messages"],
        max_tokens=6000,
        max_messages=8,
        keep_system=False
    )
    
    response = llm_with_tools.invoke([
        ("system", OA_SYSTEM_PROMPT),
    ] + managed_messages)
    
    return {"messages": [response], "current_agent": "oa_agent"}
