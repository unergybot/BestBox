from unittest.mock import MagicMock, patch

from agents.utils import get_llm


@patch("services.llm_manager.LLMManager.get_instance")
def test_get_llm_uses_manager(mock_get_instance):
    manager = MagicMock()
    client = MagicMock()
    manager.get_client.return_value = client
    mock_get_instance.return_value = manager

    result = get_llm()

    assert result == client
    manager.get_client.assert_called_once()


@patch("services.llm_manager.LLMManager.get_instance")
def test_get_llm_with_overrides(mock_get_instance):
    manager = MagicMock()
    client = MagicMock()
    client.bind.return_value = "bound_client"
    manager.get_client.return_value = client
    mock_get_instance.return_value = manager

    result = get_llm(temperature=0.5, max_tokens=2048)

    client.bind.assert_called_once_with(temperature=0.5, max_tokens=2048)
    assert result == "bound_client"
