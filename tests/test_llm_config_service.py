from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from services.llm_config_service import LLMConfigService


@pytest.fixture
def encryption_key():
    return Fernet.generate_key().decode()


@pytest.fixture
def config_service(encryption_key):
    db_mock = MagicMock()
    return LLMConfigService(db_mock, encryption_key)


def test_encrypt_decrypt_api_key(config_service):
    original_key = "sk-test-key-12345-abcdef"

    encrypted = config_service._encrypt_key(original_key)
    decrypted = config_service._decrypt_key(encrypted)

    assert decrypted == original_key
    assert encrypted != original_key
    assert len(encrypted) > len(original_key)


def test_get_active_config_decrypts_api_key(config_service):
    encrypted_key = config_service._encrypt_key("sk-real-key-123")
    config_service.db.query = MagicMock(
        return_value={
            "provider": "nvidia",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "minimaxai/minimax-m2",
            "api_key_encrypted": encrypted_key,
            "parameters": {
                "temperature": 0.7,
                "max_tokens": 4096,
                "streaming": True,
                "max_retries": 2,
            },
        }
    )

    config = config_service.get_active_config()

    assert config["api_key"] == "sk-real-key-123"
    assert "api_key_encrypted" not in config


def test_save_config_encrypts_api_key(config_service):
    config_service.db.execute = MagicMock(return_value=None)
    config_service.db.query = MagicMock(return_value={"id": 1})

    config_id = config_service.save_config(
        provider="nvidia",
        model="minimaxai/minimax-m2",
        api_key="sk-plain-key-123",
        base_url="https://integrate.api.nvidia.com/v1",
        parameters={"temperature": 0.7, "max_tokens": 4096},
        user="admin",
    )

    insert_params = config_service.db.query.call_args[0][1]
    assert "sk-plain-key-123" not in str(insert_params)
    assert config_id == 1


def test_env_override_takes_precedence(config_service, monkeypatch):
    config_service.db.query = MagicMock(
        return_value={
            "provider": "nvidia",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "minimaxai/minimax-m2",
            "parameters": {"temperature": 0.7, "max_tokens": 4096},
        }
    )
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-override")

    config = config_service.get_active_config()

    assert config["api_key"] == "nvapi-override"
    monkeypatch.delenv("NVIDIA_API_KEY")


def test_fallback_to_env_on_db_error(encryption_key, monkeypatch):
    service = LLMConfigService(MagicMock(), encryption_key)
    service.db.query.side_effect = RuntimeError("db down")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8001/v1")

    config = service.get_active_config()

    assert config["provider"] == "local_vllm"
    assert config["base_url"] == "http://localhost:8001/v1"
    monkeypatch.delenv("LLM_BASE_URL")
