"""Integration-style tests for LLM configuration flow."""

from unittest.mock import MagicMock, patch

import services.agent_api as agent_api
from agents.utils import get_llm
from fastapi.testclient import TestClient
from services.llm_manager import LLMManager


class MutableConfigService:
    def __init__(self):
        self.current = {
            "provider": "local_vllm",
            "base_url": "http://localhost:8001/v1",
            "model": "qwen3-30b",
            "api_key": None,
            "parameters": {
                "temperature": 0.7,
                "max_tokens": 4096,
                "streaming": True,
                "max_retries": 2,
            },
        }

    def get_active_config(self):
        return self.current


def setup_function():
    LLMManager._instance = None


@patch("services.llm_manager.ChatOpenAI")
def test_hot_reload_flow(mock_chat_openai):
    service = MutableConfigService()
    manager = LLMManager.get_instance()
    manager.config_service = service

    first_client = MagicMock(name="local-client")
    second_client = MagicMock(name="nvidia-client")
    mock_chat_openai.side_effect = [first_client, second_client]

    client1 = get_llm()

    service.current = {
        **service.current,
        "provider": "nvidia",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "minimaxai/minimax-m2",
        "api_key": "nvapi-test",
    }
    manager.force_refresh()

    client2 = get_llm()

    assert client1 is first_client
    assert client2 is second_client


def test_save_endpoint_triggers_refresh(monkeypatch):
    from services.admin_auth import create_jwt_token

    client = TestClient(agent_api.app)
    fake_service = MagicMock()
    fake_service.save_config.return_value = 99
    fake_manager = MagicMock()

    monkeypatch.setattr("services.admin_endpoints.get_llm_config_service", lambda: fake_service)
    monkeypatch.setattr("services.llm_manager.LLMManager.get_instance", lambda: fake_manager)

    token = create_jwt_token(user_id="admin-id", username="admin", role="admin")
    response = client.post(
        "/admin/settings/llm",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "local_vllm",
            "base_url": "http://localhost:8001/v1",
            "model": "qwen3-30b",
            "parameters": {
                "temperature": 0.9,
                "max_tokens": 2048,
                "streaming": True,
                "max_retries": 2,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    fake_manager.force_refresh.assert_called_once()
