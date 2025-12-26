"""
Tests for P2 - RawAlertFetcher
"""
import pytest
from unittest.mock import MagicMock, patch
from app.fetcher.raw_alert_fetcher import RawAlertFetcher


@pytest.fixture
def fetcher():
    """Create RawAlertFetcher instance"""
    with patch('app.fetcher.raw_alert_fetcher.settings') as mock_settings:
        mock_settings.THREATS_INDEX = "ennetix-threats1"
        mock_settings.LOGS_INDEX = "ennetix-logs1"
        mock_settings.FLOWS_INDEX = "ennetix-flows1"
        mock_settings.RAW_ALERT_INDEX = "c-ecs-raw-alert1"
        mock_settings.RAW_ALERT_PROCESSING_BATCH_SIZE = 100
        mock_settings.BATCH_SIZE = 500
        fetcher = RawAlertFetcher()
        return fetcher


def test_fetch_all_threats_empty(fetcher):
    """Test fetch_all_threats with empty result"""
    mock_scan = MagicMock(return_value=iter([]))
    fetcher.client.scan = mock_scan
    
    result = fetcher.fetch_all_threats()
    
    assert result == {}


def test_fetch_all_threats_with_data(fetcher):
    """Test fetch_all_threats with data"""
    mock_hits = [
        {"_source": {"alert_id": "alert1", "data": "threat1"}},
        {"_source": {"alert_id": "alert2", "data": "threat2"}}
    ]
    mock_scan = MagicMock(return_value=iter(mock_hits))
    fetcher.client.scan = mock_scan
    
    result = fetcher.fetch_all_threats()
    
    assert len(result) == 2
    assert "alert1" in result
    assert "alert2" in result


def test_fetch_all_threats_no_alert_id(fetcher):
    """Test fetch_all_threats with documents missing alert_id"""
    mock_hits = [
        {"_source": {"data": "threat1"}},  # No alert_id
        {"_source": {"alert_id": "alert2", "data": "threat2"}}
    ]
    mock_scan = MagicMock(return_value=iter(mock_hits))
    fetcher.client.scan = mock_scan
    
    result = fetcher.fetch_all_threats()
    
    assert len(result) == 1
    assert "alert2" in result


def test_fetch_all_threats_exception(fetcher):
    """Test fetch_all_threats handles exceptions"""
    fetcher.client.scan = MagicMock(side_effect=Exception("Test error"))
    
    result = fetcher.fetch_all_threats()
    
    assert result == {}


def test_fetch_all_logs_empty(fetcher):
    """Test fetch_all_logs with empty result"""
    mock_scan = MagicMock(return_value=iter([]))
    fetcher.client.scan = mock_scan
    
    result = fetcher.fetch_all_logs()
    
    assert result == {}


def test_fetch_all_logs_with_data(fetcher):
    """Test fetch_all_logs with data"""
    mock_hits = [
        {"_source": {"alert_id": "alert1", "logs": ["log1"]}},
        {"_source": {"alert_id": "alert1", "logs": ["log2"]}},
        {"_source": {"alert_id": "alert2", "logs": ["log3"]}}
    ]
    mock_scan = MagicMock(return_value=iter(mock_hits))
    fetcher.client.scan = mock_scan
    
    result = fetcher.fetch_all_logs()
    
    assert len(result) == 2
    assert len(result["alert1"]) == 2
    assert len(result["alert2"]) == 1


def test_fetch_all_flows_empty(fetcher):
    """Test fetch_all_flows with empty result"""
    mock_scan = MagicMock(return_value=iter([]))
    fetcher.client.scan = mock_scan
    
    result = fetcher.fetch_all_flows()
    
    assert result == {}


def test_fetch_all_flows_with_data(fetcher):
    """Test fetch_all_flows with data"""
    mock_hits = [
        {"_source": {"alert_id": "alert1", "flow": "flow1"}},
        {"_source": {"alert_id": "alert1", "flow": "flow2"}}
    ]
    mock_scan = MagicMock(return_value=iter(mock_hits))
    fetcher.client.scan = mock_scan
    
    result = fetcher.fetch_all_flows()
    
    assert len(result) == 1
    assert len(result["alert1"]) == 2


def test_process_and_store_no_threats(fetcher):
    """Test process_and_store with no threats"""
    fetcher.client.connect = MagicMock(return_value=MagicMock())
    fetcher.fetch_all_threats = MagicMock(return_value={})
    
    result = fetcher.process_and_store()
    
    assert result["status"] == "completed"
    assert result["threats_processed"] == 0


def test_process_and_store_with_threats(fetcher):
    """Test process_and_store with threats"""
    threats = {
        "alert1": {
            "alert_id": "alert1",
            "alert": {
                "id": "alert1",
                "type": "threat",
                "start": "2024-01-01T00:00:00Z",
                "entityIds": {"ips": ["1.2.3.4"]},
                "metadata": {}
            }
        }
    }
    
    fetcher.client.connect = MagicMock(return_value=MagicMock())
    fetcher.fetch_all_threats = MagicMock(return_value=threats)
    fetcher.fetch_all_logs = MagicMock(return_value={})
    fetcher.fetch_all_flows = MagicMock(return_value={})
    fetcher.client.bulk_index = MagicMock(return_value=(1, 0))
    
    with patch('app.fetcher.raw_alert_fetcher.build_raw_alert_document') as mock_build:
        mock_build.return_value = {
            "_index": "test-index",
            "_id": "alert1",
            "_source": {}
        }
        
        result = fetcher.process_and_store()
        
        assert result["status"] == "completed"
        assert result["threats_processed"] == 1
        assert result["raw_alerts_indexed"] == 1


def test_process_and_store_batch_processing(fetcher):
    """Test process_and_store processes in batches"""
    # Create more threats than batch size
    threats = {
        f"alert{i}": {
            "alert_id": f"alert{i}",
            "alert": {
                "id": f"alert{i}",
                "type": "threat",
                "start": "2024-01-01T00:00:00Z",
                "entityIds": {"ips": ["1.2.3.4"]},
                "metadata": {}
            }
        }
        for i in range(250)  # More than batch size (100)
    }
    
    fetcher.client.connect = MagicMock(return_value=MagicMock())
    fetcher.fetch_all_threats = MagicMock(return_value=threats)
    fetcher.fetch_all_logs = MagicMock(return_value={})
    fetcher.fetch_all_flows = MagicMock(return_value={})
    fetcher.client.bulk_index = MagicMock(return_value=(100, 0))
    
    with patch('app.fetcher.raw_alert_fetcher.build_raw_alert_document') as mock_build:
        mock_build.return_value = {
            "_index": "test-index",
            "_id": "alert1",
            "_source": {}
        }
        
        result = fetcher.process_and_store()
        
        assert result["status"] == "completed"
        # Should process in multiple batches
        assert fetcher.client.bulk_index.call_count >= 2


def test_process_and_store_client_not_available(fetcher):
    """Test process_and_store when client is not available"""
    fetcher.client.connect = MagicMock(return_value=None)
    
    result = fetcher.process_and_store()
    
    assert result["status"] == "error"
    assert "not available" in result["message"]


def test_process_and_store_no_raw_alerts_built(fetcher):
    """Test process_and_store when no raw alerts are built"""
    threats = {
        "alert1": {
            "alert_id": "alert1",
            "alert": {
                "id": "alert1",
                "type": "threat",
                "start": "2024-01-01T00:00:00Z",
                "entityIds": {"ips": ["1.2.3.4"]},
                "metadata": {}
            }
        }
    }
    
    fetcher.client.connect = MagicMock(return_value=MagicMock())
    fetcher.fetch_all_threats = MagicMock(return_value=threats)
    fetcher.fetch_all_logs = MagicMock(return_value={})
    fetcher.fetch_all_flows = MagicMock(return_value={})
    
    with patch('app.fetcher.raw_alert_fetcher.build_raw_alert_document') as mock_build:
        mock_build.return_value = None  # No document built
        
        result = fetcher.process_and_store()
        
        assert result["status"] == "completed"
        assert result["raw_alerts_indexed"] == 0


def test_process_and_store_with_errors(fetcher):
    """Test process_and_store handles indexing errors"""
    threats = {
        "alert1": {
            "alert_id": "alert1",
            "alert": {
                "id": "alert1",
                "type": "threat",
                "start": "2024-01-01T00:00:00Z",
                "entityIds": {"ips": ["1.2.3.4"]},
                "metadata": {}
            }
        }
    }
    
    fetcher.client.connect = MagicMock(return_value=MagicMock())
    fetcher.fetch_all_threats = MagicMock(return_value=threats)
    fetcher.fetch_all_logs = MagicMock(return_value={})
    fetcher.fetch_all_flows = MagicMock(return_value={})
    fetcher.client.bulk_index = MagicMock(return_value=(0, 1))  # 1 error
    
    with patch('app.fetcher.raw_alert_fetcher.build_raw_alert_document') as mock_build:
        mock_build.return_value = {
            "_index": "test-index",
            "_id": "alert1",
            "_source": {}
        }
        
        result = fetcher.process_and_store()
        
        assert result["status"] == "completed"
        assert result["errors"] == 1

