from unittest.mock import MagicMock, patch

from services.llm_manager import LLMManager


def setup_function():
    LLMManager._instance = None


def test_singleton_pattern():
    manager1 = LLMManager.get_instance()
    manager2 = LLMManager.get_instance()

    assert manager1 is manager2


@patch("services.llm_manager.ChatOpenAI")
@patch("services.llm_manager.get_llm_config_service")
def test_client_caching(mock_get_service, mock_chat_openai):
    service = MagicMock()
    service.get_active_config.return_value = {
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
    mock_get_service.return_value = service

    manager = LLMManager.get_instance()
    client1 = manager.get_client()
    client2 = manager.get_client()

    assert client1 is client2
    assert service.get_active_config.call_count == 2


@patch("services.llm_manager.ChatOpenAI")
@patch("services.llm_manager.get_llm_config_service")
def test_force_refresh(mock_get_service, mock_chat_openai):
    service = MagicMock()
    service.get_active_config.return_value = {
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
    mock_get_service.return_value = service

    mock_chat_openai.side_effect = [MagicMock(name="client1"), MagicMock(name="client2")]

    manager = LLMManager.get_instance()
    first = manager.get_client()
    manager.force_refresh()
    second = manager.get_client()

    assert first is not second
