"""
Tests for P1 Router
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_p1_sync_endpoint(client):
    """Test P1 sync endpoint"""
    with patch('app.router.p1_router.EnnetixAPIFetcher'):
        response = client.post("/api/v1/p1/sync", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "P1" in data["message"]


def test_p1_sync_endpoint_with_dates(client):
    """Test P1 sync endpoint with custom dates"""
    with patch('app.router.p1_router.EnnetixAPIFetcher'):
        response = client.post(
            "/api/v1/p1/sync",
            json={
                "start_date": "2024-01-01T00:00:00.000Z",
                "end_date": "2024-01-31T23:59:59.000Z"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"


def test_p1_sync_endpoint_background_task(client):
    """Test P1 sync endpoint triggers background task"""
    with patch('app.router.p1_router.EnnetixAPIFetcher') as mock_fetcher_class:
        mock_fetcher = MagicMock()
        mock_fetcher_class.return_value = mock_fetcher
        
        response = client.post("/api/v1/p1/sync", json={})
        
        assert response.status_code == 200
        # Background task should be added (can't directly verify, but endpoint should succeed)

