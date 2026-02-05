"""Tests for ReAct node."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from agents.react_node import (
    REACT_MAX_ITERATIONS,
    build_react_prompt,
    parse_react_response,
    react_loop,
)
from agents.state import AgentState


def test_build_react_prompt_includes_tools():
    prompt = build_react_prompt(
        question="What is the inventory level?",
        primary_domain="erp",
        secondary_domains=["it_ops"],
        reasoning_trace=[],
        all_tools=["get_inventory_levels", "search_knowledge_base"],
    )
    assert "get_inventory_levels" in prompt


def test_build_react_prompt_includes_trace():
    prompt = build_react_prompt(
        question="Question",
        primary_domain="general",
        secondary_domains=[],
        reasoning_trace=[
            {
                "type": "think",
                "content": "First thought",
                "tool_name": None,
                "tool_args": None,
                "timestamp": 0.0,
            }
        ],
        all_tools=["search_knowledge_base"],
    )
    assert "First thought" in prompt


def test_parse_valid_json():
    decision = parse_react_response(
        '{"reasoning": "ok", "action": "answer", "response": "done"}'
    )
    assert decision.action == "answer"


def test_parse_json_in_markdown():
    decision = parse_react_response(
        """```json
        {"reasoning": "ok", "action": "answer", "response": "done"}
        ```"""
    )
    assert decision.action == "answer"


def test_parse_invalid_returns_answer():
    decision = parse_react_response("plain answer")
    assert decision.action == "answer"
    assert "plain answer" in decision.response


def test_react_loop_single_tool_then_answer():
    state: AgentState = {
        "messages": [HumanMessage(content="Check inventory")],
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {"primary_domain": "erp", "secondary_domains": []},
        "plan": [],
        "step": 0,
        "plugin_context": None,
        "reasoning_trace": [],
        "session_id": None,
    }

    llm = MagicMock()
    llm.invoke.side_effect = [
        SimpleNamespace(content='{"reasoning": "need tool", "action": "tool", "tool": "get_inventory_levels", "args": {"warehouse_id": "WH-001"}}'),
        SimpleNamespace(content='{"reasoning": "done", "action": "answer", "response": "Inventory is 100"}'),
    ]

    tool = MagicMock()
    tool.invoke.return_value = "100"

    with patch("agents.react_node.get_llm", return_value=llm):
        result = react_loop(
            state=state,
            available_tools=["get_inventory_levels"],
            tool_objects={"get_inventory_levels": tool},
        )

    assert result["reasoning_trace"][-1]["type"] == "answer"
    assert result["messages"][-1].content == "Inventory is 100"


def test_react_loop_max_iterations_guard():
    state: AgentState = {
        "messages": [HumanMessage(content="Check inventory")],
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {"primary_domain": "erp", "secondary_domains": []},
        "plan": [],
        "step": 0,
        "plugin_context": None,
        "reasoning_trace": [],
        "session_id": None,
    }

    llm = MagicMock()
    llm.invoke.return_value = SimpleNamespace(
        content='{"reasoning": "need tool", "action": "tool", "tool": "get_inventory_levels", "args": {"warehouse_id": "WH-001"}}'
    )

    tool = MagicMock()
    tool.invoke.return_value = "100"

    with patch("agents.react_node.get_llm", return_value=llm):
        result = react_loop(
            state=state,
            available_tools=["get_inventory_levels"],
            tool_objects={"get_inventory_levels": tool},
        )

    assert len(result["reasoning_trace"]) >= REACT_MAX_ITERATIONS
