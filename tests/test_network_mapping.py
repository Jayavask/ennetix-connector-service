"""
Tests for network mapping
"""
import pytest
from app.mappers.network_mapper import NetworkMapper


def test_network_mapper_basic():
    """Test basic network mapping"""
    mapper = NetworkMapper()
    
    source_doc = {
        "@timestamp": "2024-01-01T00:00:00Z",
        "event_type": "suspicious_connection",
        "severity": 4,
        "protocol": "tcp",
        "transport": "tcp",
        "source_ip": "10.0.0.1",
        "source_port": 12345,
        "source_mac": "00:11:22:33:44:55",
        "dest_ip": "192.168.1.2",
        "dest_port": 443,
        "dest_mac": "AA:BB:CC:DD:EE:FF",
        "bytes": 1024,
        "packets": 10,
        "message": "Test network alert"
    }
    
    mapped = mapper.map(source_doc)
    
    assert mapped is not None
    assert mapped["event"]["category"] == "network"
    assert mapped["network"]["protocol"] == "tcp"
    assert mapped["source"]["ip"] == "10.0.0.1"
    assert mapped["destination"]["ip"] == "192.168.1.2"


def test_network_mapper_minimal():
    """Test network mapping with minimal fields"""
    mapper = NetworkMapper()
    
    source_doc = {
        "@timestamp": "2024-01-01T00:00:00Z",
        "event_type": "connection",
        "severity": 1,
    }
    
    mapped = mapper.map(source_doc)
    
    assert mapped is not None
    assert mapped["event"]["category"] == "network"

