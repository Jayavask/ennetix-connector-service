"""
Tests for P2 - CygeniqESSyncClient
"""
import pytest
from unittest.mock import MagicMock, patch
from app.clients.cygeniq_es_sync import CygeniqESSyncClient


@pytest.fixture
def sync_client():
    """Create CygeniqESSyncClient instance"""
    with patch('app.clients.cygeniq_es_sync.settings') as mock_settings:
        mock_settings.CONNECTOR_SERVICE_URL = "https://test-es:9200"
        mock_settings.ELASTICSEARCH_CYGENIQ_USERNAME = "testuser"
        mock_settings.ELASTICSEARCH_CYGENIQ_PASSWORD = "testpass"
        mock_settings.ELASTICSEARCH_CYGENIQ_VERIFY_CERTS = "false"
        mock_settings.ELASTICSEARCH_CYGENIQ_REQUEST_TIMEOUT = 100
        mock_settings.ELASTICSEARCH_CYGENIQ_MAX_RETRIES = 10
        client = CygeniqESSyncClient()
        return client


def test_connect_success(sync_client):
    """Test successful connection"""
    mock_es = MagicMock()
    mock_es.info.return_value = {"version": {"number": "8.0.0"}}
    
    with patch('app.clients.cygeniq_es_sync.Elasticsearch', return_value=mock_es):
        result = sync_client.connect()
        assert result == mock_es
        assert sync_client.client == mock_es


def test_connect_failure(sync_client):
    """Test connection failure"""
    with patch('app.clients.cygeniq_es_sync.Elasticsearch', side_effect=Exception("Connection failed")):
        result = sync_client.connect()
        assert result is None


def test_ensure_index_exists_new_index(sync_client):
    """Test ensure_index_exists creates new index"""
    mock_es = MagicMock()
    mock_es.indices.exists.return_value = False
    sync_client.client = mock_es
    
    sync_client.ensure_index_exists("test-index")
    
    mock_es.indices.create.assert_called_once()


def test_ensure_index_exists_existing_index(sync_client):
    """Test ensure_index_exists with existing index"""
    mock_es = MagicMock()
    mock_es.indices.exists.return_value = True
    sync_client.client = mock_es
    
    sync_client.ensure_index_exists("test-index")
    
    mock_es.indices.create.assert_not_called()


def test_scan(sync_client):
    """Test scan method"""
    mock_es = MagicMock()
    sync_client.client = mock_es
    
    mock_scan_result = iter([{"_source": {"data": "test"}}])
    
    with patch('elasticsearch.helpers.scan', return_value=mock_scan_result):
        result = sync_client.scan("test-index", {"query": {}}, scroll="2m", size=1000)
        assert list(result) == [{"_source": {"data": "test"}}]


def test_search(sync_client):
    """Test search method"""
    mock_es = MagicMock()
    mock_es.search.return_value = {"hits": {"hits": []}}
    sync_client.client = mock_es
    
    result = sync_client.search("test-index", {"query": {}})
    
    assert result == {"hits": {"hits": []}}
    mock_es.search.assert_called_once()


def test_bulk_index_success(sync_client):
    """Test bulk_index success"""
    mock_es = MagicMock()
    mock_es.indices.exists.return_value = True
    sync_client.client = mock_es
    
    documents = [
        {
            "_index": "test-index",
            "_id": "doc1",
            "_source": {"data": "test1"}
        },
        {
            "_index": "test-index",
            "_id": "doc2",
            "_source": {"data": "test2"}
        }
    ]
    
    with patch('elasticsearch.helpers.bulk', return_value=(2, [])):
        success, errors = sync_client.bulk_index(documents, chunk_size=500)
        
        assert success == 2
        assert errors == 0


def test_bulk_index_with_errors(sync_client):
    """Test bulk_index with errors"""
    mock_es = MagicMock()
    mock_es.indices.exists.return_value = True
    sync_client.client = mock_es
    
    documents = [
        {
            "_index": "test-index",
            "_id": "doc1",
            "_source": {"data": "test1"}
        }
    ]
    
    with patch('elasticsearch.helpers.bulk', return_value=(0, [{"error": "test"}])):
        success, errors = sync_client.bulk_index(documents, chunk_size=500)
        
        assert success == 0
        assert errors == 1


def test_bulk_index_empty_documents(sync_client):
    """Test bulk_index with empty documents"""
    mock_es = MagicMock()
    sync_client.client = mock_es
    
    success, errors = sync_client.bulk_index([], chunk_size=500)
    
    assert success == 0
    assert errors == 0


def test_bulk_index_exception(sync_client):
    """Test bulk_index handles exceptions"""
    mock_es = MagicMock()
    mock_es.indices.exists.return_value = True
    sync_client.client = mock_es
    
    documents = [
        {
            "_index": "test-index",
            "_id": "doc1",
            "_source": {"data": "test1"}
        }
    ]
    
    with patch('elasticsearch.helpers.bulk', side_effect=Exception("Test error")):
        success, errors = sync_client.bulk_index(documents, chunk_size=500)
        
        assert success == 0
        assert errors == 1

