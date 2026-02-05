"""
ReAct node for BestBox agents.

Implements Think → Act → Observe loop for visible reasoning.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage

from agents.state import AgentState, ReasoningStep
from agents.utils import get_llm

logger = logging.getLogger(__name__)

REACT_MAX_ITERATIONS = int(os.getenv("REACT_MAX_ITERATIONS", "5"))


class ReActDecision(BaseModel):
    """Structured output for a single ReAct step."""

    reasoning: str = Field(..., description="What the agent is thinking and why")
    action: Literal["tool", "answer"] = Field(..., description="Whether to call a tool or answer")
    tool: Optional[str] = Field(None, description="Tool name if action=tool")
    args: Optional[Dict[str, Any]] = Field(None, description="Tool args if action=tool")
    response: Optional[str] = Field(None, description="Final answer if action=answer")


REACT_SYSTEM_PROMPT = """You are an assistant that thinks step-by-step to answer questions.

Router analysis:
- Primary domain: {primary_domain}
- Secondary domains: {secondary_domains}
- This means you should prioritize {primary_domain} tools but can use others if needed.

Available tools (by relevance):

## {primary_domain} Tools (recommended)
{primary_tools}

## Other Tools (available if needed)
{other_tools}

Previous reasoning steps:
{reasoning_trace}

User question: {question}

Decide your next action. Respond in JSON:
{{
  "reasoning": "What I'm thinking and why...",
  "action": "tool" | "answer",
  "tool": "tool_name (if action=tool)",
  "args": {{ ... (if action=tool) }},
  "response": "final answer (if action=answer)"
}}
"""


def build_react_prompt(
    question: str,
    primary_domain: str,
    secondary_domains: List[str],
    reasoning_trace: List[ReasoningStep],
    all_tools: List[str],
    tool_descriptions: Optional[Dict[str, str]] = None,
) -> str:
    """
    Build the ReAct prompt with domain hints and tool listing.

    Args:
        question: User question
        primary_domain: Primary domain from router
        secondary_domains: Secondary domains from router
        reasoning_trace: Previous ReAct steps
        all_tools: All available tool names
        tool_descriptions: Optional mapping of tool name → description

    Returns:
        Formatted prompt string
    """
    tool_descriptions = tool_descriptions or {}

    domain_tool_mapping = {
        "erp": [
            "get_purchase_orders",
            "get_inventory_levels",
            "get_financial_summary",
            "get_procurement_summary",
            "get_vendor_list",
            "get_warehouse_status",
            "get_sales_orders",
        ],
        "crm": [
            "get_customer_profiles",
            "get_sales_pipeline",
            "get_lead_status",
            "get_customer_activity",
        ],
        "it_ops": [
            "get_server_status",
            "get_incident_report",
            "get_alerts",
            "get_log_summary",
        ],
        "oa": [
            "search_knowledge_base",
            "get_meeting_schedule",
            "get_leave_requests",
        ],
        "mold": [
            "search_knowledge_base",
        ],
        "general": [
            "search_knowledge_base",
        ],
    }

    primary_tool_set = set(domain_tool_mapping.get(primary_domain, []))
    primary_tools: List[str] = []
    other_tools: List[str] = []

    for tool in all_tools:
        description = tool_descriptions.get(tool)
        tool_line = f"- {tool}"
        if description:
            tool_line = f"{tool_line}: {description}"

        if tool in primary_tool_set:
            primary_tools.append(tool_line)
        else:
            other_tools.append(tool_line)

    if not primary_tools:
        primary_tools = ["- search_knowledge_base"]

    trace_text = "None yet."
    if reasoning_trace:
        trace_lines = []
        for step in reasoning_trace:
            if step["type"] == "think":
                trace_lines.append(f"THINK: {step['content']}")
            elif step["type"] == "act":
                tool_name = step.get("tool_name") or "unknown"
                trace_lines.append(f"ACT: {tool_name}({step.get('tool_args')})")
            elif step["type"] == "observe":
                trace_lines.append(f"OBSERVE: {step['content']}")
            elif step["type"] == "answer":
                trace_lines.append(f"ANSWER: {step['content']}")
        trace_text = "\n".join(trace_lines)

    return REACT_SYSTEM_PROMPT.format(
        primary_domain=primary_domain,
        secondary_domains=", ".join(secondary_domains) if secondary_domains else "none",
        primary_tools="\n".join(primary_tools),
        other_tools="\n".join(other_tools) if other_tools else "- none",
        reasoning_trace=trace_text,
        question=question,
    )


def parse_react_response(text: str) -> ReActDecision:
    """
    Parse LLM response into a ReActDecision.

    Handles JSON wrapped in markdown code blocks and falls back to answer.
    """
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    json_obj_match = re.search(r"\{[^{}]*\"action\"[^{}]*\}", text, re.DOTALL)
    if json_obj_match:
        text = json_obj_match.group(0)

    try:
        data = json.loads(text)
        return ReActDecision(**data)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to parse ReAct response as JSON: %s", exc)
        return ReActDecision(
            reasoning="Could not parse structured response; returning answer.",
            action="answer",
            response=text.strip(),
        )


def execute_tool(tool_name: str, tool_args: Dict[str, Any], available_tools: Dict[str, Any]) -> str:
    """
    Execute a tool by name with given arguments.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool
        available_tools: Dict mapping tool names to tool objects

    Returns:
        Tool execution result as string
    """
    if tool_name not in available_tools:
        return f"Error: Tool '{tool_name}' not found"

    tool = available_tools[tool_name]
    try:
        result = tool.invoke(tool_args)
        return str(result) if result is not None else "No result"
    except Exception as exc:
        logger.error("Tool execution failed for %s: %s", tool_name, exc)
        return f"Error executing {tool_name}: {str(exc)}"


def react_loop(
    state: AgentState,
    available_tools: List[str],
    tool_objects: Optional[Dict[str, Any]] = None,
) -> AgentState:
    """
    Execute the ReAct reasoning loop.

    Think → Act → Observe → repeat until answer or max iterations.
    """
    tool_objects = tool_objects or {}

    question = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            question = msg.content
            break

    context = state.get("context", {})
    primary_domain = context.get("primary_domain", "general")
    secondary_domains = context.get("secondary_domains", [])

    reasoning_trace: List[ReasoningStep] = list(state.get("reasoning_trace") or [])
    llm = get_llm(temperature=0.3)

    for _ in range(REACT_MAX_ITERATIONS):
        prompt = build_react_prompt(
            question=question,
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            reasoning_trace=reasoning_trace,
            all_tools=available_tools,
        )

        response = llm.invoke(prompt)
        decision = parse_react_response(response.content if hasattr(response, "content") else str(response))

        reasoning_trace.append(
            {
                "type": "think",
                "content": decision.reasoning,
                "tool_name": None,
                "tool_args": None,
                "timestamp": time.time(),
            }
        )

        if decision.action == "answer":
            reasoning_trace.append(
                {
                    "type": "answer",
                    "content": decision.response or "",
                    "tool_name": None,
                    "tool_args": None,
                    "timestamp": time.time(),
                }
            )
            updated_messages = list(state["messages"]) + [AIMessage(content=decision.response or "")]
            return {**state, "reasoning_trace": reasoning_trace, "messages": updated_messages}

        tool_name = decision.tool or ""
        tool_args = decision.args or {}

        reasoning_trace.append(
            {
                "type": "act",
                "content": "",
                "tool_name": tool_name,
                "tool_args": tool_args,
                "timestamp": time.time(),
            }
        )

        result = execute_tool(tool_name, tool_args, tool_objects)

        reasoning_trace.append(
            {
                "type": "observe",
                "content": str(result),
                "tool_name": None,
                "tool_args": None,
                "timestamp": time.time(),
            }
        )

    reasoning_trace.append(
        {
            "type": "answer",
            "content": "I wasn't able to complete the request within the step limit. Here's what I found so far.",
            "tool_name": None,
            "tool_args": None,
            "timestamp": time.time(),
        }
    )

    updated_messages = list(state["messages"]) + [
        AIMessage(content="I wasn't able to complete the request within the step limit. Here's what I found so far.")
    ]
    return {**state, "reasoning_trace": reasoning_trace, "messages": updated_messages}
