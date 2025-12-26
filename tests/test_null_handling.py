"""
Tests for null handling across mappers
"""
import pytest
from app.mappers.endpoint_mapper import EndpointMapper
from app.mappers.network_mapper import NetworkMapper
from app.mappers.application_mapper import ApplicationMapper


def test_null_handling_endpoint():
    """Test null handling in endpoint mapper"""
    mapper = EndpointMapper()
    
    source_doc = {
        "@timestamp": "2024-01-01T00:00:00Z",
        "event_type": "test",
        "severity": 1,
        "hostname": None,
        "host_ip": None,
        "source_ip": None,
        "source_port": None,
    }
    
    mapped = mapper.map(source_doc)
    
    assert mapped is not None
    # All None values should be handled gracefully
    assert mapped["host"]["name"] is None
    assert mapped["source"]["ip"] is None


def test_null_handling_network():
    """Test null handling in network mapper"""
    mapper = NetworkMapper()
    
    source_doc = {
        "@timestamp": "2024-01-01T00:00:00Z",
        "event_type": "test",
        "severity": 1,
        "protocol": None,
        "source_ip": None,
    }
    
    mapped = mapper.map(source_doc)
    
    assert mapped is not None
    assert mapped["network"]["protocol"] is None
    assert mapped["source"]["ip"] is None


def test_null_handling_application():
    """Test null handling in application mapper"""
    mapper = ApplicationMapper()
    
    source_doc = {
        "@timestamp": "2024-01-01T00:00:00Z",
        "event_type": "test",
        "severity": 1,
        "service_name": None,
        "app_name": None,
        "username": None,
    }
    
    mapped = mapper.map(source_doc)
    
    assert mapped is not None
    assert mapped["service"]["name"] is None
    assert mapped["application"]["name"] is None
    assert mapped["user"]["name"] is None


def test_missing_required_fields():
    """Test that missing required fields cause validation to fail"""
    mapper = EndpointMapper()
    
    source_doc = {
        # Missing @timestamp
        "event_type": "test",
    }
    
    mapped = mapper.map(source_doc)
    
    # Should return None due to validation failure
    assert mapped is None

