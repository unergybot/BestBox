from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.state import AgentState
from agents.utils import get_llm
from agents.context_manager import apply_sliding_window

class RouteDecision(BaseModel):
    """Decision on which agent to route the request to."""
    destination: Literal["erp_agent", "crm_agent", "it_ops_agent", "oa_agent", "mold_agent", "general_agent", "fallback"] = Field(
        ...,
        description="The target agent to handle the user request."
    )
    reasoning: str = Field(..., description="The reasoning behind the routing decision.")

ROUTER_SYSTEM_PROMPT = """You are the BestBox Router. Route user requests to the correct agent.

Agents:
- erp_agent: Finance, procurement, inventory, invoices, vendors, suppliers, costs, P&L
- crm_agent: Sales, leads, customers, deals, opportunities, revenue, churn
- it_ops_agent: Servers, errors, logs, alerts, IT system issues, maintenance
- oa_agent: Emails, scheduling, meetings, calendar, documents, leave requests
- mold_agent: Mold troubleshooting, manufacturing defects, product quality issues (披锋/flash, 拉白/whitening, 火花纹/spark marks, 模具/mold problems, 表面污染/contamination, trial results T0/T1/T2)
- general_agent: Greetings, help requests, cross-domain, policies, AI system questions

Rules:
- Vendors/suppliers → erp_agent
- Greetings/help/Hudson Group → general_agent
- Manufacturing/mold/product defects → mold_agent
- Only use fallback for completely unrelated requests
"""

def router_node(state: AgentState):
    """
    Analyzes the latest message and decides the next agent.
    Uses context management to prevent context overflow.
    """
    llm = get_llm(temperature=0.1) # Low temp for classification
    
    # Simple structured output wrapper since we are using Qwen
    # We can ask it to output JSON directly or use with_structured_output if supported by the backend/library combo.
    # Qwen supports function calling, so we can try .with_structured_output(RouteDecision)
    
    structured_llm = llm.with_structured_output(RouteDecision)
    
    # Apply sliding window to prevent context overflow
    # Router only needs recent context for classification
    messages = apply_sliding_window(
        state["messages"], 
        max_tokens=1500,  # Router needs minimal context
        max_messages=3,   # Only recent messages matter for routing
        keep_system=False
    )
    
    # Create prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    chain = prompt | structured_llm
    
    try:
        decision: RouteDecision = chain.invoke({"messages": messages})
        return {
            "current_agent": decision.destination,
            "confidence": 1.0, # Placeholder
            "reasoning": decision.reasoning 
        }
    except Exception as e:
        # Fallback if parsing fails
        print(f"Router failed: {e}")
        return {"current_agent": "general_agent", "confidence": 0.0}

def route_decision(state: AgentState) -> str:
    """
    Conditional edge function to determine the next node.
    """
    return state["current_agent"]
