"""Tests for context compression."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from agents.context_manager import compress_if_needed


@pytest.mark.asyncio
async def test_compress_if_needed_summarizes():
    messages = [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi"),
        HumanMessage(content="Long history"),
        AIMessage(content="More details"),
        HumanMessage(content="Recent"),
    ]

    llm = AsyncMock()
    llm.ainvoke.return_value = SimpleNamespace(content="Summary")

    with patch("agents.context_manager.get_llm", return_value=llm):
        compressed = await compress_if_needed(messages, token_budget=1, keep_recent=2)

    assert "Summary" in compressed[0].content
    assert len(compressed) == 3
