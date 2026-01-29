import pytest
from unittest.mock import Mock, patch
from services.erpnext_client import ERPNextClient

@pytest.fixture
def mock_requests():
    with patch("services.erpnext_client.requests.Session") as mock:
        yield mock

def test_client_init(mock_requests):
    client = ERPNextClient(url="http://test:8000", api_key="key", api_secret="secret")
    assert client.url == "http://test:8000"
    
    # Check if headers were updated correctly
    # self.session is the mock returned by requests.Session()
    # verify headers.update was called with auth token
    args, _ = client.session.headers.update.call_args
    assert args[0]["Authorization"] == "token key:secret"

def test_is_available_success(mock_requests):
    client = ERPNextClient()
    
    # Mock successful ping
    mock_response = Mock()
    mock_response.status_code = 200
    client.session.get.return_value = mock_response
    
    assert client.is_available() is True
    client.session.get.assert_called_with(
        "http://localhost:8002/api/method/ping",
        timeout=2
    )

def test_is_available_failure(mock_requests):
    client = ERPNextClient()
    
    # Mock failed ping
    client.session.get.side_effect = Exception("Connection refused")
    
    assert client.is_available() is False

def test_is_available_caching(mock_requests):
    client = ERPNextClient()
    client._availability_ttl = 60
    
    # First call - success
    mock_response = Mock()
    mock_response.status_code = 200
    client.session.get.return_value = mock_response
    
    assert client.is_available() is True
    assert client.session.get.call_count == 1
    
    # Second call - should use cache
    assert client.is_available() is True
    assert client.session.get.call_count == 1

def test_get_list_success(mock_requests):
    client = ERPNextClient()
    # Force available
    client._is_available_cache = True
    client._last_availability_check = 9999999999
    
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"name": "Test1"}]}
    mock_response.status_code = 200
    client.session.get.return_value = mock_response
    
    result = client.get_list("TestDoc", filters={"status": "Open"})
    
    assert result == [{"name": "Test1"}]
    args, kwargs = client.session.get.call_args
    assert "filters" in kwargs["params"]
    assert '{"status": "Open"}' in kwargs["params"]["filters"]

def test_get_list_api_error(mock_requests):
    client = ERPNextClient()
    client._is_available_cache = True
    client._last_availability_check = 9999999999

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("API Error")
    client.session.get.return_value = mock_response
    
    result = client.get_list("TestDoc")
    assert result is None
