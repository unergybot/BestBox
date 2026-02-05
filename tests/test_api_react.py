"""Tests for ReAct API endpoint."""

import os
from fastapi.testclient import TestClient
from types import SimpleNamespace
from unittest.mock import AsyncMock

import services.agent_api as agent_api


class DummySessionStore:
    async def create_session(self, user_id: str, channel: str) -> str:
        return "session-123"

    async def add_message(self, **kwargs):
        return None


def test_react_endpoint_returns_trace(monkeypatch):
    os.environ["SESSION_STORE_ENABLED"] = "false"
    mock_result = {
        "messages": [SimpleNamespace(content="Answer")],
        "reasoning_trace": [{"type": "answer", "content": "Answer"}],
    }
    client = TestClient(agent_api.app)
    monkeypatch.setattr(agent_api, "session_store", DummySessionStore())
    mock_app = AsyncMock()
    mock_app.ainvoke.return_value = mock_result
    monkeypatch.setattr(agent_api, "react_app", mock_app)
    response = client.post(
        "/chat/react",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "reasoning_trace" in payload
