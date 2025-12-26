"""
Tests for P1 - EnnetixAPIFetcher
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.fetcher.ennetix_api_fetcher import EnnetixAPIFetcher


@pytest.fixture
def fetcher():
    """Create EnnetixAPIFetcher instance"""
    with patch('app.fetcher.ennetix_api_fetcher.settings') as mock_settings:
        mock_settings.ENNETIX_API_BATCH_SIZE = 100
        mock_settings.ENNETIX_API3_BATCH_SIZE = 10
        mock_settings.BATCH_SIZE = 500
        mock_settings.P1_DATE_RANGE_DAYS = 30
        mock_settings.ENNETIX_XAUTH = "test-token"
        mock_settings.ENNETIX_ELASTICSEARCH_USERNAME = None
        mock_settings.ENNETIX_ELASTICSEARCH_PASSWORD = None
        mock_settings.ENNETIX_MAX_RETRIES = 3
        mock_settings.THREATS_INDEX = "ennetix-threats1"
        mock_settings.LOGS_INDEX = "ennetix-logs1"
        mock_settings.FLOWS_INDEX = "ennetix-flows1"
        fetcher = EnnetixAPIFetcher()
        return fetcher


@pytest.mark.asyncio
async def test_fetch_and_store_no_threats(fetcher):
    """Test fetch_and_store with no threats"""
    mock_http_client = AsyncMock()
    fetcher.api_client.fetch_threats = AsyncMock(return_value=[])
    
    mock_es_client = MagicMock()
    mock_es_client.client = MagicMock()
    fetcher.cygeniq_client.client = mock_es_client
    fetcher.cygeniq_client.connect = AsyncMock()
    
    result = await fetcher.fetch_and_store()
    
    assert result["status"] == "completed"
    assert result["threats_processed"] == 0
    assert result["alerts_processed"] == 0


@pytest.mark.asyncio
async def test_fetch_and_store_with_threats(fetcher):
    """Test fetch_and_store with threats"""
    threats = [
        {
            "ip": "1.2.3.4",
            "alerts": [
                {
                    "id": "alert1",
                    "start": "2024-01-01T00:00:00Z",
                    "time": "2024-01-01T01:00:00Z",
                    "entityIds": {"ips": ["1.2.3.4"]},
                    "metadata": {}
                }
            ]
        }
    ]
    
    mock_http_client = AsyncMock()
    fetcher.api_client.fetch_threats = AsyncMock(return_value=threats)
    
    mock_es_client = MagicMock()
    mock_es_client.client = MagicMock()
    fetcher.cygeniq_client.client = mock_es_client
    fetcher.cygeniq_client.connect = AsyncMock()
    fetcher.cygeniq_client.bulk_index_with_ids = AsyncMock(return_value=(1, 0))
    
    # Mock processor
    fetcher.processor.process_alert = AsyncMock(return_value=(
        {"_id": "alert1", "_source": {}},
        [],
        []
    ))
    
    result = await fetcher.fetch_and_store()
    
    assert result["status"] == "completed"
    assert result["threats_processed"] == 1
    assert result["alerts_processed"] == 1


@pytest.mark.asyncio
async def test_fetch_and_store_custom_dates(fetcher):
    """Test fetch_and_store with custom dates"""
    mock_http_client = AsyncMock()
    fetcher.api_client.fetch_threats = AsyncMock(return_value=[])
    
    mock_es_client = MagicMock()
    mock_es_client.client = MagicMock()
    fetcher.cygeniq_client.client = mock_es_client
    fetcher.cygeniq_client.connect = AsyncMock()
    
    start_date = "2024-01-01T00:00:00.000Z"
    end_date = "2024-01-31T23:59:59.000Z"
    
    await fetcher.fetch_and_store(start_date, end_date)
    
    fetcher.api_client.fetch_threats.assert_called_once()
    call_args = fetcher.api_client.fetch_threats.call_args[0]
    assert call_args[1] == start_date
    assert call_args[2] == end_date


@pytest.mark.asyncio
async def test_fetch_and_store_es_client_not_available(fetcher):
    """Test fetch_and_store when ES client is not available"""
    fetcher.cygeniq_client.connect = AsyncMock()
    fetcher.cygeniq_client.client = None
    
    result = await fetcher.fetch_and_store()
    
    assert result["status"] == "error"
    assert "not available" in result["message"]


@pytest.mark.asyncio
async def test_fetch_and_store_batch_processing(fetcher):
    """Test fetch_and_store processes alerts in batches"""
    threats = [
        {
            "ip": "1.2.3.4",
            "alerts": [
                {"id": f"alert{i}", "start": "2024-01-01T00:00:00Z", "entityIds": {"ips": ["1.2.3.4"]}, "metadata": {}}
                for i in range(250)  # More than batch size
            ]
        }
    ]
    
    mock_http_client = AsyncMock()
    fetcher.api_client.fetch_threats = AsyncMock(return_value=threats)
    
    mock_es_client = MagicMock()
    mock_es_client.client = MagicMock()
    fetcher.cygeniq_client.client = mock_es_client
    fetcher.cygeniq_client.connect = AsyncMock()
    fetcher.cygeniq_client.bulk_index_with_ids = AsyncMock(return_value=(100, 0))
    
    fetcher.processor.process_alert = AsyncMock(return_value=(
        {"_id": "alert1", "_source": {}},
        [],
        []
    ))
    
    result = await fetcher.fetch_and_store()
    
    assert result["status"] == "completed"
    # Should process in batches
    assert fetcher.cygeniq_client.bulk_index_with_ids.call_count >= 2


@pytest.mark.asyncio
async def test_fetch_and_store_exception_handling(fetcher):
    """Test fetch_and_store handles exceptions in alert processing"""
    threats = [
        {
            "ip": "1.2.3.4",
            "alerts": [
                {
                    "id": "alert1",
                    "start": "2024-01-01T00:00:00Z",
                    "entityIds": {"ips": ["1.2.3.4"]},
                    "metadata": {}
                }
            ]
        }
    ]
    
    mock_http_client = AsyncMock()
    fetcher.api_client.fetch_threats = AsyncMock(return_value=threats)
    
    mock_es_client = MagicMock()
    mock_es_client.client = MagicMock()
    fetcher.cygeniq_client.client = mock_es_client
    fetcher.cygeniq_client.connect = AsyncMock()
    fetcher.cygeniq_client.bulk_index_with_ids = AsyncMock(return_value=(1, 0))
    
    # Mock processor to raise exception
    fetcher.processor.process_alert = AsyncMock(side_effect=Exception("Test error"))
    
    result = await fetcher.fetch_and_store()
    
    # Should still complete but with errors
    assert result["status"] == "completed"

