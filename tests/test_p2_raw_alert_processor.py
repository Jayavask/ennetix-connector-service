"""
Tests for P2 - Raw Alert Processor
"""
import pytest
from app.processor.raw_alert_processor import (
    build_suricata_from_log_entry_and_flow,
    build_raw_alert_document
)


def test_build_suricata_empty_log_entry():
    """Test build_suricata_from_log_entry_and_flow with empty log entry"""
    result = build_suricata_from_log_entry_and_flow(None, None)
    assert result == {}


def test_build_suricata_not_dict():
    """Test build_suricata_from_log_entry_and_flow with non-dict log entry"""
    result = build_suricata_from_log_entry_and_flow("not a dict", None)
    assert result == {}


def test_build_suricata_basic():
    """Test build_suricata_from_log_entry_and_flow with basic log entry"""
    log_entry = {
        "sourceIp": "1.2.3.4",
        "sourcePort": 12345,
        "destinationIp": "5.6.7.8",
        "destinationPort": 80,
        "@timestamp": "2024-01-01T00:00:00Z",
        "event_type": "alert",
        "proto": "tcp"
    }
    
    result = build_suricata_from_log_entry_and_flow(log_entry, None)
    
    assert result["source"]["ip"] == "1.2.3.4"
    assert result["source"]["port"] == 12345
    assert result["destination"]["ip"] == "5.6.7.8"
    assert result["destination"]["port"] == 80
    assert result["timestamp"] == "2024-01-01T00:00:00Z"


def test_build_suricata_with_flow_geo():
    """Test build_suricata_from_log_entry_and_flow with flow geo data"""
    log_entry = {
        "sourceIp": "1.2.3.4",
        "sourcePort": 12345,
        "destinationIp": "5.6.7.8",
        "destinationPort": 80,
        "@timestamp": "2024-01-01T00:00:00Z"
    }
    
    flow_data = {
        "flow": {
            "geo": {
                "city_name": "Test City",
                "country_name": "Test Country",
                "location": {
                    "lat": 40.7128,
                    "lon": -74.0060
                }
            }
        }
    }
    
    result = build_suricata_from_log_entry_and_flow(log_entry, flow_data)
    
    assert result["source"]["geolocation"]["city_name"] == "Test City"
    assert result["source"]["geolocation"]["country_name"] == "Test Country"
    assert result["source"]["geolocation"]["location"]["latitude"] == 40.7128


def test_build_suricata_with_flow_client_geo():
    """Test build_suricata_from_log_entry_and_flow with flow.client.geo"""
    log_entry = {
        "sourceIp": "1.2.3.4",
        "@timestamp": "2024-01-01T00:00:00Z"
    }
    
    flow_data = {
        "flow": {
            "client": {
                "geo": {
                    "city_name": "Client City",
                    "location": {"lat": 40.0, "lon": -74.0}
                },
                "as": {
                    "number": 12345,
                    "organization": {"name": "Test AS"}
                }
            }
        }
    }
    
    result = build_suricata_from_log_entry_and_flow(log_entry, flow_data)
    
    assert result["source"]["geolocation"]["city_name"] == "Client City"
    assert result["source"]["geolocation"]["as_number"] == 12345
    assert result["source"]["geolocation"]["as_organization"] == "Test AS"


def test_build_suricata_with_flow_network():
    """Test build_suricata_from_log_entry_and_flow with network info"""
    log_entry = {
        "sourceIp": "1.2.3.4",
        "@timestamp": "2024-01-01T00:00:00Z",
        "proto": "tcp"
    }
    
    flow_data = {
        "flow": {
            "network": {
                "transport": "tcp",
                "community_id": "test-community-id"
            }
        }
    }
    
    result = build_suricata_from_log_entry_and_flow(log_entry, flow_data)
    
    assert result["network_transport"] == "TCP"
    assert result["network_community_id"] == "test-community-id"


def test_build_raw_alert_document_no_alert_id():
    """Test build_raw_alert_document with no alert_id"""
    threat_data = {"alert": {}}
    result = build_raw_alert_document(threat_data, [], [], "test-id", "test-index")
    assert result is None


def test_build_raw_alert_document_basic():
    """Test build_raw_alert_document with basic data"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "msg": "Test alert",
            "start": "2024-01-01T00:00:00Z",
            "time": "2024-01-01T01:00:00Z",
            "severity": 5,
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {}
        }
    }
    
    result = build_raw_alert_document(threat_data, [], [], "alert123", "test-index")
    
    assert result is not None
    assert result["_id"] == "alert123"
    assert result["_index"] == "test-index"
    assert result["_source"]["id"] == "alert123"
    assert result["_source"]["group"] == "NETWORK"
    assert result["_source"]["entity_ids"]["ips"] == ["1.2.3.4"]


def test_build_raw_alert_document_with_logs():
    """Test build_raw_alert_document with logs data"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {}
        }
    }
    
    logs_data = [
        {
            "alert_id": "alert123",
            "logs": [
                {
                    "sourceIp": "1.2.3.4",
                    "@timestamp": "2024-01-01T00:00:00Z"
                }
            ]
        }
    ]
    
    flows_data = [
        {
            "alert_id": "alert123",
            "target_timestamp": "2024-01-01T00:00:00Z",
            "flow": {"data": "test"}
        }
    ]
    
    result = build_raw_alert_document(threat_data, logs_data, flows_data, "alert123", "test-index")
    
    assert result is not None
    assert len(result["_source"]["alert_info"]) > 0
    assert len(result["_source"]["alert_info"][0]["suricata"]) > 0


def test_build_raw_alert_document_with_mitre_info():
    """Test build_raw_alert_document with MITRE info"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {
                "mitreInfos": [
                    {
                        "name": "Test Technique",
                        "tacticId": "TA0001",
                        "techniqueId": "T1001"
                    }
                ]
            }
        }
    }
    
    result = build_raw_alert_document(threat_data, [], [], "alert123", "test-index")
    
    assert result is not None
    assert len(result["_source"]["metadata"]["mitre_info"]) > 0
    assert result["_source"]["metadata"]["mitre_info"][0]["mitre_ids"]["tactic_id"] == "TA0001"


def test_build_raw_alert_document_with_behaviours():
    """Test build_raw_alert_document with behaviours"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {
                "behaviors": ["behavior1", "behavior2"]
            }
        }
    }
    
    result = build_raw_alert_document(threat_data, [], [], "alert123", "test-index")
    
    assert result is not None
    assert result["_source"]["metadata"]["behaviours"] == ["behavior1", "behavior2"]


def test_build_raw_alert_document_with_threat():
    """Test build_raw_alert_document with threat data"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {
                "threat": ["threat1", "threat2"]
            }
        }
    }
    
    result = build_raw_alert_document(threat_data, [], [], "alert123", "test-index")
    
    assert result is not None
    assert result["_source"]["metadata"]["threat"] == ["threat1", "threat2"]


def test_build_suricata_with_flow_source_geo():
    """Test build_suricata_from_log_entry_and_flow with flow.source.geo"""
    log_entry = {
        "sourceIp": "1.2.3.4",
        "@timestamp": "2024-01-01T00:00:00Z"
    }
    
    flow_data = {
        "flow": {
            "source": {
                "geo": {
                    "city_name": "Source City",
                    "location": {"lat": 40.0, "lon": -74.0}
                }
            }
        }
    }
    
    result = build_suricata_from_log_entry_and_flow(log_entry, flow_data)
    
    assert result["source"]["geolocation"]["city_name"] == "Source City"


def test_build_suricata_with_flow_data_geo():
    """Test build_suricata_from_log_entry_and_flow with geo at top level of flow_data"""
    log_entry = {
        "sourceIp": "1.2.3.4",
        "@timestamp": "2024-01-01T00:00:00Z"
    }
    
    # The code checks top-level geo only if flow exists but doesn't have geo in expected locations
    # So we need flow to exist but not have geo in flow.geo, flow.client.geo, or flow.source.geo
    flow_data = {
        "geo": {
            "city_name": "Top Level City",
            "location": {"lat": 40.0, "lon": -74.0}
        },
        "flow": {
            "some_other_field": "value"  # flow exists but no geo in expected locations
        }
    }
    
    result = build_suricata_from_log_entry_and_flow(log_entry, flow_data)
    
    assert result["source"]["geolocation"]["city_name"] == "Top Level City"


def test_build_suricata_with_log_geo_fallback():
    """Test build_suricata_from_log_entry_and_flow uses log geo as fallback"""
    log_entry = {
        "sourceIp": "1.2.3.4",
        "@timestamp": "2024-01-01T00:00:00Z",
        "src_geoip": {
            "city_name": "Log City",
            "country_name": "Log Country",
            "latitude": 40.0,
            "longitude": -74.0
        }
    }
    
    result = build_suricata_from_log_entry_and_flow(log_entry, None)
    
    assert result["source"]["geolocation"]["city_name"] == "Log City"
    assert result["source"]["geolocation"]["country_name"] == "Log Country"


def test_build_suricata_with_destination_geo():
    """Test build_suricata_from_log_entry_and_flow with destination geo"""
    log_entry = {
        "destinationIp": "5.6.7.8",
        "destinationPort": 80,
        "@timestamp": "2024-01-01T00:00:00Z",
        "dest_geoip": {
            "city_name": "Dest City",
            "country_name": "Dest Country",
            "latitude": 50.0,
            "longitude": -80.0
        }
    }
    
    result = build_suricata_from_log_entry_and_flow(log_entry, None)
    
    assert result["destination"]["geolocation"]["city_name"] == "Dest City"
    assert result["destination"]["geolocation"]["location"]["latitude"] == 50.0


def test_build_raw_alert_document_with_multiple_source_ips():
    """Test build_raw_alert_document with multiple source IPs"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {}
        }
    }
    
    logs_data = [
        {
            "alert_id": "alert123",
            "logs": [
                {"sourceIp": "1.2.3.4", "@timestamp": "2024-01-01T00:00:00Z"},
                {"sourceIp": "5.6.7.8", "@timestamp": "2024-01-01T00:00:00Z"}
            ]
        }
    ]
    
    flows_data = []
    
    result = build_raw_alert_document(threat_data, logs_data, flows_data, "alert123", "test-index")
    
    assert result is not None
    # Should create separate alert_info entries for each source IP
    assert len(result["_source"]["alert_info"]) == 2


def test_build_raw_alert_document_logs_not_list():
    """Test build_raw_alert_document with logs that are not a list"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {}
        }
    }
    
    logs_data = [
        {
            "alert_id": "alert123",
            "logs": "not a list"  # Invalid format
        }
    ]
    
    result = build_raw_alert_document(threat_data, logs_data, [], "alert123", "test-index")
    
    assert result is not None
    assert result["_source"]["alert_info"] == []


def test_build_raw_alert_document_log_entry_not_dict():
    """Test build_raw_alert_document with log entry that is not a dict"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {}
        }
    }
    
    logs_data = [
        {
            "alert_id": "alert123",
            "logs": ["not a dict"]  # Invalid format
        }
    ]
    
    result = build_raw_alert_document(threat_data, logs_data, [], "alert123", "test-index")
    
    assert result is not None
    assert result["_source"]["alert_info"] == []


def test_build_raw_alert_document_alert_id_from_alert():
    """Test build_raw_alert_document gets alert_id from alert.id"""
    threat_data = {
        "alert": {
            "id": "alert123",  # alert_id comes from here
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {}
        }
    }
    
    result = build_raw_alert_document(threat_data, [], [], "test-id", "test-index")
    
    assert result is not None
    assert result["_id"] == "alert123"


def test_build_raw_alert_document_message_from_msg():
    """Test build_raw_alert_document uses msg field for message"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "msg": "Alert message",
            "start": "2024-01-01T00:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {}
        }
    }
    
    result = build_raw_alert_document(threat_data, [], [], "alert123", "test-index")
    
    assert result is not None
    assert result["_source"]["message"] == "Alert message"


def test_build_raw_alert_document_end_time_from_time():
    """Test build_raw_alert_document uses time field for end_time"""
    threat_data = {
        "alert_id": "alert123",
        "alert": {
            "id": "alert123",
            "type": "threat",
            "start": "2024-01-01T00:00:00Z",
            "time": "2024-01-01T01:00:00Z",
            "entityIds": {"ips": ["1.2.3.4"]},
            "metadata": {}
        }
    }
    
    result = build_raw_alert_document(threat_data, [], [], "alert123", "test-index")
    
    assert result is not None
    assert result["_source"]["end_time"] == "2024-01-01T01:00:00Z"

