"""
Tests for P1 - AlertProcessor
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.processor.alert_processor import AlertProcessor, SERVICES, ROLES


@pytest.fixture
def alert_processor():
    """Create AlertProcessor instance"""
    with patch('app.processor.alert_processor.settings') as mock_settings:
        mock_settings.ENNETIX_API_BATCH_SIZE = 100
        mock_settings.ENNETIX_API3_BATCH_SIZE = 10
        mock_settings.ENNETIX_API3_DELAY = 0.05
        processor = AlertProcessor()
        return processor


def test_get_earliest_signature_ids_empty(alert_processor):
    """Test get_earliest_signature_ids with empty list"""
    result = alert_processor.get_earliest_signature_ids([])
    assert result == []


def test_get_earliest_signature_ids_no_timestamp(alert_processor):
    """Test get_earliest_signature_ids with no timestamp"""
    logs = [{"signatureId": "123"}]
    result = alert_processor.get_earliest_signature_ids(logs)
    assert result == []


def test_get_earliest_signature_ids_single(alert_processor):
    """Test get_earliest_signature_ids with single log"""
    logs = [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "signatureId": "123"
        }
    ]
    result = alert_processor.get_earliest_signature_ids(logs)
    assert result == ["123"]


def test_get_earliest_signature_ids_multiple(alert_processor):
    """Test get_earliest_signature_ids with multiple logs"""
    logs = [
        {
            "timestamp": "2024-01-01T01:00:00Z",
            "signatureId": "456"
        },
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "signatureId": "123"
        },
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "signatureId": "789"
        }
    ]
    result = alert_processor.get_earliest_signature_ids(logs)
    assert "123" in result
    assert "789" in result
    assert "456" not in result


def test_get_earliest_signature_ids_duplicates(alert_processor):
    """Test get_earliest_signature_ids removes duplicates"""
    logs = [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "signatureId": "123"
        },
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "signatureId": "123"
        }
    ]
    result = alert_processor.get_earliest_signature_ids(logs)
    assert result == ["123"]


def test_find_matching_flow(alert_processor):
    """Test find_matching_flow"""
    flows = [
        {"@timestamp": "2024-01-01T00:00:00Z", "data": "flow1"},
        {"@timestamp": "2024-01-01T01:00:00Z", "data": "flow2"}
    ]
    result = alert_processor.find_matching_flow(flows, "2024-01-01T00:00:00Z")
    assert result == {"@timestamp": "2024-01-01T00:00:00Z", "data": "flow1"}


def test_find_matching_flow_no_match(alert_processor):
    """Test find_matching_flow with no match"""
    flows = [
        {"@timestamp": "2024-01-01T01:00:00Z", "data": "flow2"}
    ]
    result = alert_processor.find_matching_flow(flows, "2024-01-01T00:00:00Z")
    assert result is None


def test_find_matching_flow_empty(alert_processor):
    """Test find_matching_flow with empty list"""
    result = alert_processor.find_matching_flow([], "2024-01-01T00:00:00Z")
    assert result is None


@pytest.mark.asyncio
async def test_process_alert_with_suricata_logs(alert_processor):
    """Test process_alert with suricata logs"""
    alert = {
        "id": "alert123",
        "start": "2024-01-01T00:00:00Z",
        "time": "2024-01-01T01:00:00Z",
        "entityIds": {"ips": ["1.2.3.4"]},
        "metadata": {
            "suricataLogs": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "signatureId": "123"
                }
            ]
        }
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    # Mock API calls
    alert_processor.api_client.fetch_logs = AsyncMock(return_value=[
        {"sourceIp": "1.2.3.4", "@timestamp": "2024-01-01T00:00:00Z"}
    ])
    alert_processor.api_client.fetch_flows = AsyncMock(return_value=[
        {"@timestamp": "2024-01-01T00:00:00Z", "flow": "data"}
    ])
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, "1.2.3.4", mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is not None
    assert threat_doc["_id"] == "alert123"
    assert len(logs_docs) > 0
    assert len(flows_docs) > 0


@pytest.mark.asyncio
async def test_process_alert_no_alert_id(alert_processor):
    """Test process_alert with missing alert ID"""
    alert = {
        "start": "2024-01-01T00:00:00Z",
        "entityIds": {"ips": ["1.2.3.4"]}
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, "1.2.3.4", mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is None
    assert logs_docs == []
    assert flows_docs == []


@pytest.mark.asyncio
async def test_process_alert_no_ips(alert_processor):
    """Test process_alert with no IPs"""
    alert = {
        "id": "alert123",
        "start": "2024-01-01T00:00:00Z",
        "entityIds": {}
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, None, mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is None
    assert logs_docs == []
    assert flows_docs == []


@pytest.mark.asyncio
async def test_process_alert_no_suricata_logs(alert_processor):
    """Test process_alert without suricata logs"""
    alert = {
        "id": "alert123",
        "start": "2024-01-01T00:00:00Z",
        "time": "2024-01-01T01:00:00Z",
        "entityIds": {"ips": ["1.2.3.4"]},
        "metadata": {}
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    alert_processor.api_client.fetch_flows = AsyncMock(return_value=[
        {"@timestamp": "2024-01-01T00:00:00Z", "flow": "data"}
    ])
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, "1.2.3.4", mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is not None
    assert logs_docs == []
    assert len(flows_docs) > 0


@pytest.mark.asyncio
async def test_process_alert_logs_api_returns_none(alert_processor):
    """Test process_alert when logs API returns None"""
    alert = {
        "id": "alert123",
        "start": "2024-01-01T00:00:00Z",
        "time": "2024-01-01T01:00:00Z",
        "entityIds": {"ips": ["1.2.3.4"]},
        "metadata": {
            "suricataLogs": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "signatureId": "123"
                }
            ]
        }
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    alert_processor.api_client.fetch_logs = AsyncMock(return_value=None)
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, "1.2.3.4", mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is not None
    assert logs_docs == []


@pytest.mark.asyncio
async def test_process_alert_flows_no_match(alert_processor):
    """Test process_alert when flows don't match timestamp"""
    alert = {
        "id": "alert123",
        "start": "2024-01-01T00:00:00Z",
        "time": "2024-01-01T01:00:00Z",
        "entityIds": {"ips": ["1.2.3.4"]},
        "metadata": {
            "suricataLogs": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "signatureId": "123"
                }
            ]
        }
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    alert_processor.api_client.fetch_logs = AsyncMock(return_value=[
        {"sourceIp": "1.2.3.4", "@timestamp": "2024-01-01T00:00:00Z"}
    ])
    alert_processor.api_client.fetch_flows = AsyncMock(return_value=[
        {"@timestamp": "2024-01-01T02:00:00Z", "flow": "data"}
    ])
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, "1.2.3.4", mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is not None
    assert len(logs_docs) > 0
    assert len(flows_docs) == 0


@pytest.mark.asyncio
async def test_process_alert_uses_end_time_from_time_field(alert_processor):
    """Test process_alert uses time field for end_time"""
    alert = {
        "id": "alert123",
        "start": "2024-01-01T00:00:00Z",
        "time": "2024-01-01T01:00:00Z",
        "entityIds": {"ips": ["1.2.3.4"]},
        "metadata": {}
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    alert_processor.api_client.fetch_flows = AsyncMock(return_value=[])
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, "1.2.3.4", mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is not None
    assert threat_doc["_source"]["end_time"] == "2024-01-01T01:00:00Z"


@pytest.mark.asyncio
async def test_process_alert_uses_end_time_from_end_field(alert_processor):
    """Test process_alert uses end field for end_time if time not present"""
    alert = {
        "id": "alert123",
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-01-01T02:00:00Z",
        "entityIds": {"ips": ["1.2.3.4"]},
        "metadata": {}
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    alert_processor.api_client.fetch_flows = AsyncMock(return_value=[])
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, "1.2.3.4", mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is not None
    assert threat_doc["_source"]["end_time"] == "2024-01-01T02:00:00Z"


@pytest.mark.asyncio
async def test_process_alert_flow_matching_found_early_break(alert_processor):
    """Test process_alert stops searching flows when match is found"""
    alert = {
        "id": "alert123",
        "start": "2024-01-01T00:00:00Z",
        "time": "2024-01-01T01:00:00Z",
        "entityIds": {"ips": ["1.2.3.4"]},
        "metadata": {
            "suricataLogs": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "signatureId": "123"
                }
            ]
        }
    }
    
    mock_http_client = AsyncMock()
    mock_semaphore = AsyncMock()
    mock_api3_semaphore = AsyncMock()
    
    alert_processor.api_client.fetch_logs = AsyncMock(return_value=[
        {"sourceIp": "1.2.3.4", "@timestamp": "2024-01-01T00:00:00Z"}
    ])
    alert_processor.api_client.fetch_flows = AsyncMock(return_value=[
        {"@timestamp": "2024-01-01T00:00:00Z", "flow": "matched"}
    ])
    
    threat_doc, logs_docs, flows_docs = await alert_processor.process_alert(
        mock_http_client, alert, "1.2.3.4", mock_semaphore, mock_api3_semaphore
    )
    
    assert threat_doc is not None
    assert len(flows_docs) > 0

