from unittest.mock import MagicMock

import services.agent_api as agent_api
from fastapi.testclient import TestClient


def _auth_header(role: str) -> dict:
    from services.admin_auth import create_jwt_token

    token = create_jwt_token(user_id=f"{role}-id", username=role, role=role)
    return {"Authorization": f"Bearer {token}"}


def test_get_llm_config_masks_api_key(monkeypatch):
    client = TestClient(agent_api.app)

    fake_service = MagicMock()
    fake_service.get_active_config.return_value = {
        "provider": "nvidia",
        "model": "minimaxai/minimax-m2",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "sk-test-key-1234567890",
        "parameters": {"temperature": 0.7, "max_tokens": 4096},
    }

    monkeypatch.setattr("services.admin_endpoints.get_llm_config_service", lambda: fake_service)

    response = client.get("/admin/settings/llm", headers=_auth_header("admin"))

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "nvidia"
    assert "api_key" not in data
    assert "api_key_masked" in data
    assert "..." in data["api_key_masked"]


def test_save_llm_config_requires_permission(monkeypatch):
    client = TestClient(agent_api.app)

    fake_service = MagicMock()
    monkeypatch.setattr("services.admin_endpoints.get_llm_config_service", lambda: fake_service)

    response = client.post(
        "/admin/settings/llm",
        headers=_auth_header("viewer"),
        json={
            "provider": "nvidia",
            "model": "minimaxai/minimax-m2",
            "api_key": "sk-test",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "parameters": {"temperature": 0.7, "max_tokens": 4096},
        },
    )

    assert response.status_code == 403


def test_save_llm_config_success(monkeypatch):
    client = TestClient(agent_api.app)

    fake_service = MagicMock()
    fake_service.save_config.return_value = 42
    monkeypatch.setattr("services.admin_endpoints.get_llm_config_service", lambda: fake_service)

    fake_manager = MagicMock()
    monkeypatch.setattr("services.llm_manager.LLMManager.get_instance", lambda: fake_manager)

    response = client.post(
        "/admin/settings/llm",
        headers=_auth_header("admin"),
        json={
            "provider": "nvidia",
            "model": "minimaxai/minimax-m2",
            "api_key": "sk-test-key-12345",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "parameters": {
                "temperature": 0.7,
                "max_tokens": 4096,
                "streaming": True,
                "max_retries": 2,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["config_id"] == 42
    fake_manager.force_refresh.assert_called_once()
