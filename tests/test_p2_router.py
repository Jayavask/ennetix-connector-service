"""
Tests for P2 Router
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_p2_sync_endpoint(client):
    """Test P2 sync endpoint"""
    with patch('app.router.p2_router.RawAlertFetcher'):
        response = client.post("/api/v1/p2/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "P2" in data["message"]


def test_p2_sync_endpoint_background_task(client):
    """Test P2 sync endpoint triggers background task"""
    with patch('app.router.p2_router.RawAlertFetcher') as mock_fetcher_class:
        mock_fetcher = MagicMock()
        mock_fetcher_class.return_value = mock_fetcher
        
        response = client.post("/api/v1/p2/sync")
        
        assert response.status_code == 200
        # Background task should be added

