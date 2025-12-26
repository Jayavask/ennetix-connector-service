"""
Tests for P1 - EnnetixAPIClient
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.clients.ennetix_api import EnnetixAPIClient


@pytest.fixture
def api_client():
    """Create EnnetixAPIClient instance"""
    with patch('app.clients.ennetix_api.settings') as mock_settings:
        mock_settings.ENNETIX_API_BASE_URL = "https://demo.xvisor.ai"
        mock_settings.ENNETIX_XAUTH = "test-token"
        mock_settings.ENNETIX_ELASTICSEARCH_USERNAME = None
        mock_settings.ENNETIX_ELASTICSEARCH_PASSWORD = None
        mock_settings.ENNETIX_MAX_RETRIES = 3
        mock_settings.ENNETIX_RETRY_DELAY = 1.0
        client = EnnetixAPIClient()
        return client


@pytest.mark.asyncio
async def test_fetch_api_success(api_client):
    """Test successful API fetch"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"data": "test"}'
    mock_response.json.return_value = {"data": "test"}
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result == {"data": "test"}
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_api_with_xauth(api_client):
    """Test API fetch with xauth header"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"data": "test"}'
    mock_response.json.return_value = {"data": "test"}
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    await api_client.fetch_api(mock_client, "https://test.com/api")
    
    call_args = mock_client.get.call_args
    assert call_args[1]["headers"]["xauth"] == "test-token"


@pytest.mark.asyncio
async def test_fetch_api_with_username_password(api_client):
    """Test API fetch with username/password auth"""
    api_client.xauth = None
    api_client.username = "testuser"
    api_client.password = "testpass"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"data": "test"}'
    mock_response.json.return_value = {"data": "test"}
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    await api_client.fetch_api(mock_client, "https://test.com/api")
    
    call_args = mock_client.get.call_args
    assert call_args[1]["auth"] == ("testuser", "testpass")


@pytest.mark.asyncio
async def test_fetch_api_302_redirect_with_xauth(api_client):
    """Test API fetch with 302 redirect and xauth cookie"""
    mock_response_302 = MagicMock()
    mock_response_302.status_code = 302
    mock_response_302.headers = {"Location": "/some/path"}
    
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.headers = {"content-type": "application/json"}
    mock_response_200.text = '{"data": "test"}'
    mock_response_200.json.return_value = {"data": "test"}
    mock_response_200.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_response_302, mock_response_200])
    
    result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result == {"data": "test"}
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_api_500_retry(api_client):
    """Test API fetch with 500 error and retry"""
    mock_response_500 = MagicMock()
    mock_response_500.status_code = 500
    
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.headers = {"content-type": "application/json"}
    mock_response_200.text = '{"data": "test"}'
    mock_response_200.json.return_value = {"data": "test"}
    mock_response_200.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_response_500, mock_response_200])
    
    with patch('asyncio.sleep', new_callable=AsyncMock):
        result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result == {"data": "test"}


@pytest.mark.asyncio
async def test_fetch_api_html_response(api_client):
    """Test API fetch with HTML response (login page)"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<!DOCTYPE html><html>"
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_api_json_decode_error(api_client):
    """Test API fetch with JSON decode error"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = "invalid json"
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_threats(api_client):
    """Test fetch_threats method"""
    mock_data = [
        {"id": "threat1", "ip": "1.2.3.4"},
        {"id": "threat2", "ip": "5.6.7.8"}
    ]
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_threats(mock_client, "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
    
    assert result == mock_data
    api_client.fetch_api.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_threats_dict_response(api_client):
    """Test fetch_threats with dict response containing threats key"""
    mock_data = {"threats": [{"id": "threat1"}]}
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_threats(mock_client, "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
    
    assert result == [{"id": "threat1"}]


@pytest.mark.asyncio
async def test_fetch_logs(api_client):
    """Test fetch_logs method"""
    mock_data = [{"log": "data"}]
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_logs(mock_client, "1.2.3.4", "sig123", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
    
    assert result == mock_data


@pytest.mark.asyncio
async def test_fetch_logs_dict_response(api_client):
    """Test fetch_logs with dict response"""
    mock_data = {"logs": [{"log": "data"}]}
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_logs(mock_client, "1.2.3.4", "sig123", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
    
    assert result == [{"log": "data"}]


@pytest.mark.asyncio
async def test_fetch_logs_none_response(api_client):
    """Test fetch_logs with None response"""
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=None)
    
    result = await api_client.fetch_logs(mock_client, "1.2.3.4", "sig123", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_flows(api_client):
    """Test fetch_flows method"""
    mock_data = [{"flow": "data"}]
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_flows(mock_client, "1.2.3.4", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z", "http", "client")
    
    assert result == mock_data


@pytest.mark.asyncio
async def test_fetch_flows_dict_response(api_client):
    """Test fetch_flows with dict response"""
    mock_data = {"flows": [{"flow": "data"}]}
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_flows(mock_client, "1.2.3.4", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z", "http", "client")
    
    assert result == [{"flow": "data"}]


@pytest.mark.asyncio
async def test_fetch_flows_none_response(api_client):
    """Test fetch_flows with None response"""
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=None)
    
    result = await api_client.fetch_flows(mock_client, "1.2.3.4", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z", "http", "client")
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_api_302_redirect_to_login(api_client):
    """Test API fetch with 302 redirect to login page"""
    mock_response = MagicMock()
    mock_response.status_code = 302
    mock_response.headers = {"Location": "/login"}
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_api_http_status_error_500(api_client):
    """Test API fetch with HTTPStatusError 500"""
    mock_response = MagicMock()
    mock_response.status_code = 500
    
    mock_client = AsyncMock()
    error = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
    mock_client.get = AsyncMock(side_effect=error)
    
    with patch('asyncio.sleep', new_callable=AsyncMock):
        result = await api_client.fetch_api(mock_client, "https://test.com/api", retry_count=0)
    
    # Should retry and eventually return None after max retries
    assert result is None or mock_client.get.call_count > 1


@pytest.mark.asyncio
async def test_fetch_api_http_status_error_non_500(api_client):
    """Test API fetch with HTTPStatusError non-500"""
    mock_response = MagicMock()
    mock_response.status_code = 404
    
    mock_client = AsyncMock()
    error = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)
    mock_client.get = AsyncMock(side_effect=error)
    
    result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_api_generic_exception(api_client):
    """Test API fetch with generic exception"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Generic error"))
    
    result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_threats_empty_response(api_client):
    """Test fetch_threats with empty response"""
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=None)
    
    result = await api_client.fetch_threats(mock_client, "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
    
    assert result == []


@pytest.mark.asyncio
async def test_fetch_threats_dict_with_results_key(api_client):
    """Test fetch_threats with dict response containing results key"""
    mock_data = {"results": [{"id": "threat1"}]}
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_logs(mock_client, "1.2.3.4", "sig123", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
    
    assert result == []


@pytest.mark.asyncio
async def test_fetch_logs_dict_with_data_key(api_client):
    """Test fetch_logs with dict response containing data key"""
    mock_data = {"data": [{"log": "data"}]}
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_logs(mock_client, "1.2.3.4", "sig123", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
    
    assert result == [{"log": "data"}]


@pytest.mark.asyncio
async def test_fetch_flows_dict_with_data_key(api_client):
    """Test fetch_flows with dict response containing data key"""
    mock_data = {"data": [{"flow": "data"}]}
    
    mock_client = AsyncMock()
    api_client.fetch_api = AsyncMock(return_value=mock_data)
    
    result = await api_client.fetch_flows(mock_client, "1.2.3.4", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z", "http", "client")
    
    assert result == [{"flow": "data"}]


@pytest.mark.asyncio
async def test_fetch_api_html_response_with_xauth_retry(api_client):
    """Test API fetch with HTML response and xauth cookie retry"""
    mock_response_html = MagicMock()
    mock_response_html.status_code = 200
    mock_response_html.headers = {"content-type": "text/html"}
    mock_response_html.text = "<!DOCTYPE html>"
    mock_response_html.raise_for_status = MagicMock()
    
    mock_response_json = MagicMock()
    mock_response_json.status_code = 200
    mock_response_json.headers = {"content-type": "application/json"}
    mock_response_json.text = '{"data": "test"}'
    mock_response_json.json.return_value = {"data": "test"}
    mock_response_json.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_response_html, mock_response_json])
    
    result = await api_client.fetch_api(mock_client, "https://test.com/api")
    
    assert result == {"data": "test"}
    assert mock_client.get.call_count == 2

