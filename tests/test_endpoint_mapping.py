"""
Tests for endpoint mapping
"""
import pytest
from app.mappers.endpoint_mapper import EndpointMapper


def test_endpoint_mapper_basic():
    """Test basic endpoint mapping"""
    mapper = EndpointMapper()
    
    source_doc = {
        "@timestamp": "2024-01-01T00:00:00Z",
        "event_type": "malware_detected",
        "severity": 5,
        "hostname": "test-host",
        "host_ip": "192.168.1.1",
        "source_ip": "10.0.0.1",
        "source_port": 12345,
        "dest_ip": "192.168.1.2",
        "dest_port": 80,
        "message": "Test alert"
    }
    
    mapped = mapper.map(source_doc)
    
    assert mapped is not None
    assert mapped["@timestamp"] == source_doc["@timestamp"]
    assert mapped["event"]["category"] == "endpoint"
    assert mapped["host"]["name"] == "test-host"
    assert mapped["source"]["ip"] == "10.0.0.1"


def test_endpoint_mapper_null_handling():
    """Test null value handling in endpoint mapper"""
    mapper = EndpointMapper()
    
    source_doc = {
        "@timestamp": "2024-01-01T00:00:00Z",
        "event_type": "test",
        "severity": 1,
        "hostname": None,
        "host_ip": None,
    }
    
    mapped = mapper.map(source_doc)
    
    assert mapped is not None
    assert mapped["host"]["name"] is None
    assert mapped["host"]["ip"] is None

