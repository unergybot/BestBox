"""Integration tests for ReAct system."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from agents.react_node import react_loop
from agents.state import AgentState


def test_react_integration_single_answer():
    state: AgentState = {
        "messages": [HumanMessage(content="What is the inventory level?")],
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
        content='{"reasoning": "I know this", "action": "answer", "response": "Inventory is stable"}'
    )

    with patch("agents.react_node.get_llm", return_value=llm):
        result = react_loop(state=state, available_tools=[], tool_objects={})

    assert result["messages"][-1].content == "Inventory is stable"
    assert result["reasoning_trace"][-1]["type"] == "answer"
