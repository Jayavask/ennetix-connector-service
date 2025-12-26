"""
Raw alert processor for P2 - builds raw alert documents from CS1 data
"""
from typing import Dict, Any, List, Optional


def build_suricata_from_log_entry_and_flow(
    log_entry: Dict[str, Any],
    flow_data: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build suricata structure from a single log entry (Index 2) and flow (Index 3)."""
    if not log_entry or not isinstance(log_entry, dict):
        return {}
    
    # Extract flow data if available
    flow = flow_data.get("flow", {}) if flow_data else {}
    
    # Extract geo data from Index 3 (flows) - check multiple possible locations
    flow_geo = {}
    flow_location = {}
    flow_client_as = {}
    
    if flow:
        # Check multiple possible locations for geo data
        # 1. flow.geo (top level in flow)
        if "geo" in flow:
            flow_geo = flow.get("geo", {})
            flow_location = flow_geo.get("location", {})
        # 2. flow.client.geo (geo in client object - for source IP)
        elif "client" in flow:
            client_obj = flow.get("client", {})
            if isinstance(client_obj, dict):
                if "geo" in client_obj:
                    flow_geo = client_obj.get("geo", {})
                    flow_location = flow_geo.get("location", {})
        # 3. flow.source.geo (geo in source object)
        elif "source" in flow:
            source_obj = flow.get("source", {})
            if isinstance(source_obj, dict) and "geo" in source_obj:
                flow_geo = source_obj.get("geo", {})
                flow_location = flow_geo.get("location", {})
        # 4. Check if geo is at top level of flow_data (outside flow object)
        if not flow_geo and flow_data and "geo" in flow_data:
            flow_geo = flow_data.get("geo", {})
            flow_location = flow_geo.get("location", {})
        
        # Always check for AS information from flow.client.as (separate from geo)
        if "client" in flow:
            client_obj = flow.get("client", {})
            if isinstance(client_obj, dict) and "as" in client_obj:
                flow_client_as = client_obj.get("as", {})
    
    # Build source
    source_ip = log_entry.get("sourceIp") or log_entry.get("source_ip")
    source_port = log_entry.get("sourcePort") or log_entry.get("source_port")
    source_geo = log_entry.get("src_geoip") or log_entry.get("source_geo") or {}
    
    # Merge geolocation: prefer Index 3 (flow) data, fallback to Index 2 (log) data
    source_city = flow_geo.get("city_name") or source_geo.get("city_name") or source_geo.get("city")
    source_country = flow_geo.get("country_name") or source_geo.get("country_name") or source_geo.get("country")
    source_lat = flow_location.get("lat") or flow_location.get("latitude") or source_geo.get("latitude")
    source_lon = flow_location.get("lon") or flow_location.get("longitude") or source_geo.get("longitude")
    
    # Get AS number and organization from Index 3 (flow.client.as)
    source_as_number = flow_client_as.get("number") if flow_client_as else None
    if source_as_number is None:
        source_as_number = source_geo.get("as_number")
    
    source_as_org = None
    if flow_client_as:
        org_obj = flow_client_as.get("organization", {})
        if isinstance(org_obj, dict):
            source_as_org = org_obj.get("name")
    if source_as_org is None:
        source_as_org = source_geo.get("as_organization")
    
    source = {
        "ip": source_ip or "",
        "port": source_port,
        "nodal_degree": None,
        "bytes_sent": log_entry.get("numBytesClntToSrvr") or log_entry.get("bytes_sent"),
        "packets_sent": log_entry.get("numPktsClntToSrvr") or log_entry.get("packets_sent"),
        "geolocation": {
            "as_number": source_as_number,
            "as_organization": source_as_org,
            "city_name": source_city,
            "country_name": source_country,
            "region_iso_code": source_geo.get("region_iso_code"),
            "region_name": source_geo.get("region_name"),
            "location": {
                "latitude": source_lat,
                "longitude": source_lon,
            } if source_lat or source_lon else None,
        }
    }
    
    # Build destination
    dest_ip = log_entry.get("destinationIp") or log_entry.get("destination_ip")
    dest_port = log_entry.get("destinationPort") or log_entry.get("destination_port")
    dest_geo = log_entry.get("dest_geoip") or log_entry.get("destination_geo") or {}
    
    # For destination, check if flow has destination geo data
    # (flow geo might be for source, so we still use log data for destination)
    dest_city = dest_geo.get("city_name") or dest_geo.get("city")
    dest_country = dest_geo.get("country_name") or dest_geo.get("country")
    dest_lat = dest_geo.get("latitude")
    dest_lon = dest_geo.get("longitude")
    
    # Get bytes_sent and packets_sent from Index 2 (log_entry)
    # For destination, use numBytesSrvrToClnt and numPktsSrvrToClnt
    dest_bytes_sent = log_entry.get("numBytesSrvrToClnt")
    if dest_bytes_sent is None:
        dest_bytes_sent = log_entry.get("bytes_sent")
    
    dest_packets_sent = log_entry.get("numPktsSrvrToClnt")
    if dest_packets_sent is None:
        dest_packets_sent = log_entry.get("packets_sent")
    
    destination = {
        "ip": dest_ip or "",
        "port": dest_port,
        "nodal_degree": None,
        "bytes_sent": dest_bytes_sent,
        "packets_sent": dest_packets_sent,
        "geolocation": {
            "as_number": dest_geo.get("as_number"),
            "as_organization": dest_geo.get("as_organization"),
            "city_name": dest_city,
            "country_name": dest_country,
            "region_iso_code": dest_geo.get("region_iso_code"),
            "region_name": dest_geo.get("region_name"),
            "location": {
                "latitude": dest_lat,
                "longitude": dest_lon,
            } if dest_lat or dest_lon else None,
        }
    }
    
    # Extract network info from flow if available
    network = flow.get("network", {}) if flow else {}
    
    suricata = {
        "suricata_alert_id": log_entry.get("_id") or log_entry.get("id"),
        "timestamp": log_entry.get("@timestamp"),
        "event_type": log_entry.get("event_type") or "alert",
        "direction": log_entry.get("direction"),
        "hostname": log_entry.get("hostName") or log_entry.get("hostname"),
        "flow_ids": flow.get("flow_ids") or [],
        "network_community_id": network.get("community_id") or log_entry.get("communityId") or log_entry.get("community_id"),
        "network_transport": (network.get("transport") or log_entry.get("proto") or "").upper(),
        "source": source,
        "destination": destination,
        "suricata": [],  # Nested suricata array
        "alert_severity": log_entry.get("alertSeverity") or log_entry.get("severity"),
        "alert_category": log_entry.get("alertCategory") or log_entry.get("category"),
        "alert_signature": log_entry.get("signature"),
        "protocol": log_entry.get("proto"),
    }
    
    return suricata


def build_raw_alert_document(
    threat_data: Dict[str, Any],
    logs_data: List[Dict[str, Any]],
    flows_data: List[Dict[str, Any]],
    alert_id: str,
    raw_alert_index: str
) -> Optional[Dict[str, Any]]:
    """Build raw alert document from threat, logs, and flows data."""
    alert = threat_data.get("alert", {})
    alert_id = threat_data.get("alert_id") or alert.get("id")
    
    if not alert_id:
        return None
    
    # Extract entity_ids from alert
    entity_ids_data = alert.get("entityIds", {})
    ips = entity_ids_data.get("ips", [])
    
    # Build metadata from alert
    metadata = alert.get("metadata", {})
    suricata_logs = metadata.get("suricataLogs", [])
    
    # Build mitre_info from metadata
    mitre_infos = metadata.get("mitreInfos", [])
    mitre_info = []
    for mi in mitre_infos:
        if isinstance(mi, dict):
            mitre_info.append({
                "name": mi.get("name"),
                "mitre_ids": {
                    "tactic_id": mi.get("tacticId") or mi.get("tactic_id"),
                    "technique_id": mi.get("techniqueId") or mi.get("technique_id"),
                }
            })
    
    # Build suricata_logs for metadata
    metadata_suricata_logs = []
    for log in suricata_logs:
        if isinstance(log, dict):
            mitre_ids_list = []
            mitre_ids_field = log.get("mitreIds")
            if isinstance(mitre_ids_field, dict):
                mitre_ids_list.append({
                    "tactic_id": mitre_ids_field.get("tacticId") or mitre_ids_field.get("tactic_id"),
                    "technique_id": mitre_ids_field.get("techniqueId") or mitre_ids_field.get("technique_id"),
                })
            
            metadata_suricata_logs.append({
                "log_id": log.get("log_id"),
                "category": log.get("category"),
                "severity": log.get("severity"),
                "signature": log.get("signature"),
                "signature_id": log.get("signatureId") or log.get("signature_id"),
                "mitre_ids": mitre_ids_list,
            })
    
    # Build alert_info with suricata from logs and flows
    # Group by source IP from Index 2, create one alert_info entry per source IP
    alert_info = []
    
    if not logs_data:
        # No logs data, alert_info will be empty
        pass
    else:
        # Group all log entries by source IP
        source_ip_to_logs = {}  # source_ip -> list of (log_entry, matching_flow)
        
        # Process all log entries from Index 2
        for log_data in logs_data:
            logs = log_data.get("logs", [])
            if not logs or not isinstance(logs, list):
                continue
            
            # Process each log entry (each has a signature_id)
            for log_entry in logs:
                if not log_entry or not isinstance(log_entry, dict):
                    continue
                
                # Get source IP from log entry
                source_ip = log_entry.get("sourceIp") or log_entry.get("source_ip")
                if not source_ip:
                    # Fallback to entityIds.ips from Index 1
                    source_ip = ips[0] if ips else None
                
                if not source_ip:
                    continue
                
                # Get timestamp for flow matching
                log_timestamp = log_entry.get("@timestamp")
                
                # Find matching flow from Index 3
                matching_flow = None
                for flow_data in flows_data:
                    flow_timestamp = flow_data.get("target_timestamp")
                    flow_alert_id = flow_data.get("alert_id")
                    
                    # Match by timestamp and alert_id
                    if (flow_timestamp == log_timestamp and 
                        flow_alert_id == alert_id):
                        matching_flow = flow_data
                        break
                
                # Group by source IP
                if source_ip not in source_ip_to_logs:
                    source_ip_to_logs[source_ip] = []
                source_ip_to_logs[source_ip].append((log_entry, matching_flow))
        
        # Build alert_info entries - one per source IP
        for source_ip, log_entries_with_flows in source_ip_to_logs.items():
            suricata_list = []
            
            # Create one suricata entry per log entry (signature ID)
            for log_entry, matching_flow in log_entries_with_flows:
                suricata = build_suricata_from_log_entry_and_flow(log_entry, matching_flow)
                if suricata:
                    suricata_list.append(suricata)
            
            # Create NetworkAlert entry for this source IP
            if suricata_list:
                alert_info.append({
                    "id": source_ip,  # id refers to source.ip
                    "suricata": suricata_list
                })
    
    # Build entity_ids
    entity_ids = {
        "app_ids": None,
        "app_user_ids": None,
        "cmpt_ids": None,
        "dns_servers": None,
        "hostnames": None,
        "iface_ids": None,
        "ip": None,
        "ips": ips,
        "ne_ids": None,
        "probe_ids": None,
        "sigma_rule_ids": None,
        "snmp_indexes": None,
        "ssids": None,
        "xome_ids": None,
        "xome_target_ids": None,
        "xtend_ids": None,
        "zone_ids": None,
    }
    
    # Build metadata
    # Get behaviours from metadata.behaviors in Index 1
    behaviours = metadata.get("behaviors") or metadata.get("behaviours")
    
    # Get threat from metadata.threat in Index 1
    threat = metadata.get("threat") or []
    
    metadata_obj = {
        "anomaly_sentences": None,
        "baseline": None,
        "behaviours": behaviours,
        "entity_name": None,
        "metric": None,
        "mitre_info": mitre_info,
        "sigma_alerts": None,
        "suricata_logs": metadata_suricata_logs,
        "threat": threat,
        "unauthorized_dns_servers": None,
        "unauthorized_domains": None,
        "unauthorized_ssids": None,
    }
    
    # Build root_cause
    root_cause = {
        "alert_id": alert_id,
        "strong_events": None,
        "weak_events": None,
    }
    
    # Build final document
    raw_alert = {
        "_index": raw_alert_index,
        "_id": alert_id,
        "_source": {
            "group": "NETWORK",
            "type": alert.get("type"),
            "message": alert.get("msg") or alert.get("message"),
            "start_time": alert.get("start") or alert.get("start_time"),
            "end_time": alert.get("time") or alert.get("end_time"),
            "severity": alert.get("severity"),
            "entity_ids": entity_ids,
            "id": alert_id,
            "source_index": None,
            "events": None,
            "metadata": metadata_obj,
            "alert_info": alert_info,
            "root_cause": root_cause,
        }
    }
    
    return raw_alert

