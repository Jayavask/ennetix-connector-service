import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, scan
import urllib3

# Load variables from .env
load_dotenv()

# ---------------------------------------------------------------------------
# Cygeniq Elasticsearch Configuration
# ---------------------------------------------------------------------------
CYGENIQ_ES_HOSTS_ENV = os.getenv("CONNECTOR_SERVICE_URL", "")
CYGENIQ_ES_HOSTS: List[str] = (
    [h.strip() for h in CYGENIQ_ES_HOSTS_ENV.split(",") if h.strip()]
    if CYGENIQ_ES_HOSTS_ENV
    else []
)
CYGENIQ_ES_USERNAME = os.getenv("CYGENIQ_ELASTICSEARCH_USERNAME") or os.getenv("ELASTICSEARCH_CYGENIQ_USERNAME", "")
CYGENIQ_ES_PASSWORD = os.getenv("CYGENIQ_ELASTICSEARCH_PASSWORD") or os.getenv("ELASTICSEARCH_CYGENIQ_PASSWORD", "")
CYGENIQ_ES_CA_CERTS = os.getenv("CYGENIQ_ELASTICSEARCH_CA_CERTS") or os.getenv("ELASTICSEARCH_CYGENIQ_CA_CERTS", "")
CYGENIQ_ES_TIMEOUT = int(
    os.getenv("CYGENIQ_ELASTICSEARCH_REQUEST_TIMEOUT") 
    or os.getenv("ELASTICSEARCH_CYGENIQ_REQUEST_TIMEOUT", "100")
)
CYGENIQ_ES_MAX_RETRIES = int(
    os.getenv("CYGENIQ_ELASTICSEARCH_MAX_RETRIES") 
    or os.getenv("ELASTICSEARCH_CYGENIQ_MAX_RETRIES", "10")
)
CYGENIQ_ES_VERIFY_CERTS_ENV = (
    os.getenv("CYGENIQ_ELASTICSEARCH_VERIFY_CERTS") 
    or os.getenv("ELASTICSEARCH_CYGENIQ_VERIFY_CERTS", "false")
)
CYGENIQ_ES_VERIFY_CERTS = CYGENIQ_ES_VERIFY_CERTS_ENV.lower() == "true"

# Disable SSL warnings if verify_certs is False
if not CYGENIQ_ES_VERIFY_CERTS:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Index names
THREATS_INDEX = "ennetix-threats"  # CS1 - Index 1
LOGS_INDEX = "ennetix-logs"        # CS1 - Index 2
FLOWS_INDEX = "ennetix-flows"      # CS1 - Index 3
RAW_ALERT_INDEX = "c-ecs-raw-alert"      # CS2 - Output index

# Batch size for bulk operations
BATCH_SIZE = 500

# Processing batch size (process and store in batches)
PROCESSING_BATCH_SIZE = int(os.getenv("RAW_ALERT_PROCESSING_BATCH_SIZE", "100"))


def create_cygeniq_client() -> Optional[Elasticsearch]:
    """Create Elasticsearch client for Cygeniq ECS."""
    if not CYGENIQ_ES_HOSTS:
        print("⚠️  CONNECTOR_SERVICE_URL is not configured, skipping Cygeniq storage.")
        return None

    if not CYGENIQ_ES_USERNAME or not CYGENIQ_ES_PASSWORD:
        print("⚠️  Warning: Cygeniq Elasticsearch credentials not found!")
        print("   Attempting connection without authentication (may fail)...")

    client_config: Dict[str, Any] = {
        "hosts": CYGENIQ_ES_HOSTS,
        "request_timeout": CYGENIQ_ES_TIMEOUT,
        "max_retries": CYGENIQ_ES_MAX_RETRIES,
        "retry_on_timeout": True,
    }

    if CYGENIQ_ES_USERNAME and CYGENIQ_ES_PASSWORD:
        client_config["basic_auth"] = (CYGENIQ_ES_USERNAME, CYGENIQ_ES_PASSWORD)

    if CYGENIQ_ES_VERIFY_CERTS:
        client_config["verify_certs"] = True
        if CYGENIQ_ES_CA_CERTS:
            client_config["ca_certs"] = CYGENIQ_ES_CA_CERTS
    else:
        client_config["verify_certs"] = False
        client_config["ssl_show_warn"] = False

    try:
        client = Elasticsearch(**client_config)
        info = client.info()
        print(f"✅ Connected to Cygeniq Elasticsearch (version: {info['version']['number']})")
        return client
    except Exception as exc:
        print(f"❌ Failed to connect to Cygeniq Elasticsearch: {exc}")
        return None


def ensure_index_exists(client: Elasticsearch, index_name: str) -> None:
    """Ensure index exists in Cygeniq ES, create if it doesn't."""
    try:
        if not client.indices.exists(index=index_name):
            print(f"📝 Creating index {index_name} in Cygeniq...")
            client.indices.create(
                index=index_name,
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    }
                },
            )
            print(f"✅ Created index {index_name}")
    except Exception as exc:
        print(f"⚠️  Could not create index {index_name}: {exc}")


def fetch_all_threats(client: Elasticsearch) -> Dict[str, Dict[str, Any]]:
    """Fetch all threats from Index 1 (ennetix-threats) and index by alert_id."""
    print(f"\n🔍 Fetching all threats from {THREATS_INDEX}...")
    threats_by_alert_id = {}
    
    try:
        query = {
            "query": {"match_all": {}},
            "size": 10000  # Adjust if needed
        }
        
        response = scan(
            client,
            query=query,
            index=THREATS_INDEX,
            scroll="2m",
            size=1000,
        )
        
        count = 0
        for hit in response:
            source = hit.get("_source", {})
            alert_id = source.get("alert_id")
            if alert_id:
                threats_by_alert_id[alert_id] = source
                count += 1
        
        print(f"✅ Fetched {count} threats")
        return threats_by_alert_id
    except Exception as exc:
        print(f"❌ Error fetching threats: {exc}")
        return {}


def fetch_all_logs(client: Elasticsearch) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch all logs from Index 2 (ennetix-logs) and group by alert_id."""
    print(f"\n🔍 Fetching all logs from {LOGS_INDEX}...")
    logs_by_alert_id = {}
    
    try:
        query = {
            "query": {"match_all": {}},
            "size": 10000
        }
        
        response = scan(
            client,
            query=query,
            index=LOGS_INDEX,
            scroll="2m",
            size=1000,
        )
        
        count = 0
        for hit in response:
            source = hit.get("_source", {})
            alert_id = source.get("alert_id")
            if alert_id:
                if alert_id not in logs_by_alert_id:
                    logs_by_alert_id[alert_id] = []
                logs_by_alert_id[alert_id].append(source)
                count += 1
        
        print(f"✅ Fetched {count} log documents for {len(logs_by_alert_id)} unique alert_ids")
        return logs_by_alert_id
    except Exception as exc:
        print(f"❌ Error fetching logs: {exc}")
        return {}


def fetch_all_flows(client: Elasticsearch) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch all flows from Index 3 (ennetix-flows) and group by alert_id."""
    print(f"\n🔍 Fetching all flows from {FLOWS_INDEX}...")
    flows_by_alert_id = {}
    
    try:
        query = {
            "query": {"match_all": {}},
            "size": 10000
        }
        
        response = scan(
            client,
            query=query,
            index=FLOWS_INDEX,
            scroll="2m",
            size=1000,
        )
        
        count = 0
        for hit in response:
            source = hit.get("_source", {})
            alert_id = source.get("alert_id")
            if alert_id:
                if alert_id not in flows_by_alert_id:
                    flows_by_alert_id[alert_id] = []
                flows_by_alert_id[alert_id].append(source)
                count += 1
        
        print(f"✅ Fetched {count} flow documents for {len(flows_by_alert_id)} unique alert_ids")
        return flows_by_alert_id
    except Exception as exc:
        print(f"❌ Error fetching flows: {exc}")
        return {}


def fetch_logs_by_alert_id(client: Elasticsearch, alert_id: str) -> List[Dict[str, Any]]:
    """Fetch logs from Index 2 (ennetix-logs) for a specific alert_id."""
    try:
        query = {
            "query": {
                "term": {"alert_id": alert_id}
            }
        }
        
        response = client.search(
            index=LOGS_INDEX,
            body=query,
            size=1000
        )
        
        logs = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            logs.append(source)
        
        return logs
    except Exception as exc:
        print(f"   ⚠️  Error fetching logs for alert {alert_id}: {exc}")
        return []


def fetch_flows_by_criteria(
    client: Elasticsearch,
    alert_id: Optional[str],
    timestamp: Optional[str],
    source_ip: Optional[str],
    ip: Optional[str]
) -> List[Dict[str, Any]]:
    """Fetch flows from Index 3 (ennetix-flows) matching criteria.
    
    Uses:
    - timestamp from Index 2 (target_timestamp field)
    - source_ip from Index 2 (or entityIds.ips from Index 1 as fallback)
    - alert_id if stored in Index 3
    """
    try:
        # Build query with multiple criteria
        must_clauses = []
        
        # Use alert_id if available in Index 3
        if alert_id:
            must_clauses.append({"term": {"alert_id": alert_id}})
        
        # Use timestamp from Index 2
        if timestamp:
            must_clauses.append({"term": {"target_timestamp": timestamp}})
        
        # Use source_ip from Index 2, or fallback to ip from Index 1 (entityIds.ips)
        ip_to_search = source_ip or ip
        if ip_to_search:
            must_clauses.append({"term": {"ip": ip_to_search}})
        
        if not must_clauses:
            return []
        
        query = {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            }
        }
        
        response = client.search(
            index=FLOWS_INDEX,
            body=query,
            size=100
        )
        
        flows = []
        for hit in response.get("hits", {}).get("hits", []):
            flows.append(hit.get("_source", {}))
        
        return flows
    except Exception as exc:
        print(f"   ⚠️  Error fetching flows: {exc}")
        return []


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
    alert_id: str
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
        "_index": RAW_ALERT_INDEX,
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


def index_documents(
    es_client: Elasticsearch,
    documents: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """Bulk index documents into Elasticsearch."""
    if not documents:
        return 0, 0

    ensure_index_exists(es_client, RAW_ALERT_INDEX)

    try:
        actions = []
        for doc in documents:
            actions.append({
                "_index": doc.get("_index"),
                "_id": doc.get("_id"),
                "_source": doc.get("_source", {}),
            })

        success, errors = bulk(
            es_client,
            actions,
            chunk_size=BATCH_SIZE,
            request_timeout=60,
            raise_on_error=False,
        )

        if errors:
            print(f"   ⚠️  {len(errors)} documents failed to index (showing first 3):")
            for err in errors[:3]:
                print(f"      {err}")

        return success, len(errors) if errors else 0

    except Exception as exc:
        print(f"   ❌ Error during bulk indexing: {exc}")
        return 0, len(documents)


def main() -> None:
    """Main execution function."""
    print("=" * 80)
    print("🚀 Phase 2: Create Raw Alerts from Cygeniq ECS")
    print("=" * 80)
    print("CS1 (API Output Data) -> P2 (Create Raw Alert) -> CS2 (Raw Alert)")
    
    # Create Cygeniq Elasticsearch client
    client = create_cygeniq_client()
    if not client:
        print("\n⚠️  Cygeniq Elasticsearch client not available. Exiting.")
        return
    
    # Step 1: Fetch all data from all 3 indexes
    print("\n" + "=" * 80)
    print("STEP 1: Fetching data from all 3 indexes")
    print("=" * 80)
    
    # Fetch from Index 1 (threats)
    print(f"\n📋 Index 1: {THREATS_INDEX}")
    threats_by_alert_id = fetch_all_threats(client)
    
    # Fetch from Index 2 (logs)
    print(f"\n📋 Index 2: {LOGS_INDEX}")
    logs_by_alert_id = fetch_all_logs(client)
    
    # Fetch from Index 3 (flows)
    print(f"\n📋 Index 3: {FLOWS_INDEX}")
    flows_by_alert_id = fetch_all_flows(client)
    
    if not threats_by_alert_id:
        print("\n⚠️  No threats found. Exiting.")
        return
    
    print(f"\n✅ Data fetched from all 3 indexes:")
    print(f"   - Threats: {len(threats_by_alert_id)} unique alert_ids")
    print(f"   - Logs: {len(logs_by_alert_id)} unique alert_ids")
    print(f"   - Flows: {len(flows_by_alert_id)} unique alert_ids")
    
    # Step 2: Process threats in batches and store immediately
    print("\n" + "=" * 80)
    print("STEP 2: Processing threats and building raw alerts (batch-wise)")
    print("=" * 80)
    print(f"📦 Processing batch size: {PROCESSING_BATCH_SIZE}")
    
    total_threats = len(threats_by_alert_id)
    threats_list = list(threats_by_alert_id.items())
    total_batches = (total_threats + PROCESSING_BATCH_SIZE - 1) // PROCESSING_BATCH_SIZE
    
    total_indexed = 0
    total_errors = 0
    
    # Process in batches
    for batch_num in range(total_batches):
        batch_start = batch_num * PROCESSING_BATCH_SIZE
        batch_end = min(batch_start + PROCESSING_BATCH_SIZE, total_threats)
        batch = threats_list[batch_start:batch_end]
        
        print(f"\n📦 Processing batch {batch_num + 1}/{total_batches} (alerts {batch_start + 1}-{batch_end})...")
        
        raw_alert_docs = []
        
        for alert_id, threat_data in batch:
            # Get logs from Index 2 (already fetched, just lookup)
            logs_data = logs_by_alert_id.get(alert_id, [])
            
            # Get flows from Index 3 (already fetched, just lookup)
            flows_data = flows_by_alert_id.get(alert_id, [])
            
            # Build raw alert document
            raw_alert = build_raw_alert_document(threat_data, logs_data, flows_data, alert_id)
            if raw_alert:
                raw_alert_docs.append(raw_alert)
        
        # Store batch immediately
        if raw_alert_docs:
            print(f"   📤 Indexing {len(raw_alert_docs)} raw alert documents from batch {batch_num + 1}...")
            success, errors = index_documents(client, raw_alert_docs)
            total_indexed += success
            total_errors += errors
            print(f"   ✅ Batch {batch_num + 1} indexed: {success} documents, {errors} errors")
        else:
            print(f"   ⚠️  Batch {batch_num + 1} produced no raw alert documents")
    
    print(f"\n✅ Built and indexed {total_indexed} raw alert documents in {total_batches} batches")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Summary")
    print("=" * 80)
    print(f"  Threats processed: {total_threats}")
    print(f"  Batches processed: {total_batches}")
    print(f"  Raw alerts indexed: {total_indexed}")
    print(f"  Errors: {total_errors}")
    print("=" * 80)
    print("✨ Phase 2 completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()

