"""Tests for ReAct state extensions."""

from agents.state import AgentState, ReasoningStep


def test_reasoning_step_think():
    """Test think step structure."""
    step: ReasoningStep = {
        "type": "think",
        "content": "I need to check inventory levels",
        "tool_name": None,
        "tool_args": None,
        "timestamp": 0.0,
    }
    assert step["content"] == "I need to check inventory levels"


def test_reasoning_step_act():
    """Test act step structure."""
    step: ReasoningStep = {
        "type": "act",
        "content": "",
        "tool_name": "get_inventory_levels",
        "tool_args": {"warehouse_id": "WH-001"},
        "timestamp": 0.0,
    }
    assert step["tool_name"] == "get_inventory_levels"


def test_agent_state_has_reasoning_trace():
    """Test AgentState includes reasoning_trace field."""
    state: AgentState = {
        "messages": [],
        "current_agent": "router",
        "tool_calls": 0,
        "confidence": 1.0,
        "context": {},
        "plan": [],
        "step": 0,
        "plugin_context": None,
        "reasoning_trace": [],
        "session_id": None,
    }
    assert "reasoning_trace" in state
    assert "session_id" in state
