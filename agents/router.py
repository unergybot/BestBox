from typing import Literal, List
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
    secondary_domains: List[str] = Field(
        default_factory=list,
        description="Other domains that might be relevant to the request."
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

For secondary_domains: If the question may need information from multiple domains, list the secondary ones.
Example: "What's our procurement policy?" → destination=erp_agent, secondary_domains=["it_ops"] (policy docs)
"""

DESTINATION_DOMAIN_MAP = {
    "erp_agent": "erp",
    "crm_agent": "crm",
    "it_ops_agent": "it_ops",
    "oa_agent": "oa",
    "mold_agent": "mold",
    "general_agent": "general",
    "fallback": "general",
}

# Reverse map: domain -> agent name
DOMAIN_TO_AGENT_MAP = {
    "erp": "erp_agent",
    "crm": "crm_agent",
    "it_ops": "it_ops_agent",
    "itops": "it_ops_agent",
    "oa": "oa_agent",
    "mold": "mold_agent",
    "general": "general_agent",
}


def router_node(state: AgentState):
    """
    Analyzes the latest message and decides the next agent.
    Uses context management to prevent context overflow.

    Supports force_domain optimization: if state.context.force_domain is set,
    skip LLM classification and route directly to the specified domain agent.
    This saves 200-500ms per request when the caller knows the domain.
    """
    context = state.get("context", {})
    force_domain = context.get("force_domain") if context else None

    # OPTIMIZATION: Skip LLM classification if force_domain is set
    if force_domain:
        agent_name = DOMAIN_TO_AGENT_MAP.get(force_domain.lower())
        if agent_name:
            merged_context = dict(context)
            merged_context.update({
                "primary_domain": force_domain,
                "secondary_domains": [],
                "router_reasoning": f"Forced routing to {force_domain} (skipped LLM classification)",
                "router_skipped": True,
            })
            return {
                "current_agent": agent_name,
                "confidence": 1.0,
                "reasoning": f"Direct routing via force_domain={force_domain}",
                "context": merged_context,
            }

    # Standard LLM-based routing
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
        primary_domain = DESTINATION_DOMAIN_MAP.get(decision.destination, "general")
        merged_context = dict(state.get("context", {}))
        merged_context.update({
            "primary_domain": primary_domain,
            "secondary_domains": decision.secondary_domains,
            "router_reasoning": decision.reasoning,
        })
        return {
            "current_agent": decision.destination,
            "confidence": 1.0, # Placeholder
            "reasoning": decision.reasoning,
            "context": merged_context,
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
