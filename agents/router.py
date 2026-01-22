from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.state import AgentState
from agents.utils import get_llm

class RouteDecision(BaseModel):
    """Decision on which agent to route the request to."""
    destination: Literal["erp_agent", "crm_agent", "it_ops_agent", "oa_agent", "fallback"] = Field(
        ..., 
        description="The target agent to handle the user request."
    )
    reasoning: str = Field(..., description="The reasoning behind the routing decision.")

ROUTER_SYSTEM_PROMPT = """You are the Router Agent for BestBox, an enterprise AI assistant.
Your job is to analyze the user's request and route it to the most appropriate specialist agent.

Available Agents:
1. **erp_agent**: Handles finance, procurement, inventory, invoices, and vendors.
   - Keywords: price, cost, spend, invoice, inventory, stock, vendor, procurement, P&L.
   
2. **crm_agent**: Handles sales, leads, customers, deals, and opportunities.
   - Keywords: lead, churn, customer, sales, quote, deal, opportunity, revenue pipeline.
   
3. **it_ops_agent**: Handles system status, servers, logs, alerts, and troubleshooting.
   - Keywords: server, slow, error, crash, log, alert, diagnosis, failure, maintenance.
   
4. **oa_agent**: Handles office automation, documents, emails, and scheduling.
   - Keywords: email, draft, letter, schedule, meeting, calendar, leave request, approval.

If the request is unclear, out of scope, or conversational (e.g., "hi", "help"), route to 'fallback'.
"""

def router_node(state: AgentState):
    """
    Analyzes the latest message and decides the next agent.
    """
    llm = get_llm(temperature=0.1) # Low temp for classification
    
    # Simple structured output wrapper since we are using Qwen
    # We can ask it to output JSON directly or use with_structured_output if supported by the backend/library combo.
    # Qwen supports function calling, so we can try .with_structured_output(RouteDecision)
    
    structured_llm = llm.with_structured_output(RouteDecision)
    
    # Get the last user message
    messages = state["messages"]
    
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
        return {"current_agent": "fallback", "confidence": 0.0}

def route_decision(state: AgentState) -> str:
    """
    Conditional edge function to determine the next node.
    """
    return state["current_agent"]
