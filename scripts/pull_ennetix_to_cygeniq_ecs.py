import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta, timezone
import asyncio

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import urllib3

# Load variables from .env
load_dotenv()

# ---------------------------------------------------------------------------
# Ennetix API Configuration (from .env lines 1-8)
# ---------------------------------------------------------------------------
ENNETIX_API_BASE_URL = os.getenv("ENNETIX_API_BASE_URL", "https://demo.xvisor.ai")
ENNETIX_XAUTH = os.getenv("ENNETIX_XAUTH")
ENNETIX_USERNAME = os.getenv("ENNETIX_ELASTICSEARCH_USERNAME") or os.getenv("ENNETIX_USERNAME")
ENNETIX_PASSWORD = os.getenv("ENNETIX_ELASTICSEARCH_PASSWORD") or os.getenv("ENNETIX_PASSWORD")

# ---------------------------------------------------------------------------
# Cygeniq Elasticsearch Configuration (from .env lines 9-15)
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

# Index names in Cygeniq Elasticsearch
THREATS_INDEX = "ennetix-threats"
LOGS_INDEX = "ennetix-logs"
FLOWS_INDEX = "ennetix-flows"

# Batch size for bulk operations
BATCH_SIZE = 500

# Concurrent batch size for API calls (API 1 & API 2)
API_BATCH_SIZE = int(os.getenv("ENNETIX_API_BATCH_SIZE", "100"))  # For threats and logs APIs

# Separate concurrency limit for API 3 (flows) - more restrictive due to server load
API3_BATCH_SIZE = int(os.getenv("ENNETIX_API3_BATCH_SIZE", "10"))  # Limit concurrent flow API calls

# Retry configuration
MAX_RETRIES = int(os.getenv("ENNETIX_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("ENNETIX_RETRY_DELAY", "1.0"))  # Initial delay in seconds

# Service and role combinations for API 3
SERVICES = ["dns", "ssh", "http", "https", "other"]
ROLES = ["client", "server"]


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


async def fetch_ennetix_api(
    client: httpx.AsyncClient,
    url: str,
    params: Dict[str, Any] = None,
    retry_count: int = 0,
) -> Optional[Any]:
    """Fetch data from Ennetix API with authentication and retry logic."""
    if params is None:
        params = {}

    headers: Dict[str, str] = {}
    auth = None

    if ENNETIX_XAUTH:
        headers["xauth"] = ENNETIX_XAUTH
    elif ENNETIX_USERNAME and ENNETIX_PASSWORD:
        auth = (ENNETIX_USERNAME, ENNETIX_PASSWORD)

    try:
        resp = await client.get(
            url,
            params=params,
            headers=headers,
            auth=auth,
            timeout=60,
            follow_redirects=False,
        )

        # If redirected and have xauth, try using it as a cookie
        if resp.status_code == 302 and ENNETIX_XAUTH:
            cookies = {"xauth": ENNETIX_XAUTH}
            resp = await client.get(
                url,
                params=params,
                cookies=cookies,
                timeout=60,
                follow_redirects=False,
            )

        if resp.status_code == 302:
            redirect_location = resp.headers.get("Location", "")
            if '/login' in redirect_location.lower():
                print(f"   ❌ Authentication failed: API redirected to login page")
                return None

        # Handle 500 errors with retry logic
        if resp.status_code == 500:
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** retry_count)  # Exponential backoff
                print(f"   ⚠️  HTTP 500 error, retrying in {delay:.1f}s (attempt {retry_count + 1}/{MAX_RETRIES})...")
                await asyncio.sleep(delay)
                return await fetch_ennetix_api(client, url, params, retry_count + 1)
            else:
                print(f"   ❌ HTTP 500 error after {MAX_RETRIES} retries: {url}")
                return None

        resp.raise_for_status()

        # Check if response is HTML (login page) instead of JSON
        content_type = resp.headers.get("content-type", "").lower()
        text_content = resp.text

        if "text/html" in content_type or text_content.strip().startswith("<!DOCTYPE html"):
            if ENNETIX_XAUTH:
                cookies = {"xauth": ENNETIX_XAUTH}
                resp = await client.get(
                    url,
                    params=params,
                    cookies=cookies,
                    timeout=60,
                    follow_redirects=False,
                )
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "").lower()
                text_content = resp.text
                if "text/html" in content_type or text_content.strip().startswith("<!DOCTYPE html"):
                    print(f"   ❌ Response is HTML (likely login page), not JSON")
                    return None
            else:
                print(f"   ❌ Response is HTML (likely login page), not JSON")
                return None

        data = resp.json()
        return data

    except httpx.HTTPStatusError as e:
        # Retry on 500 errors
        if e.response.status_code == 500 and retry_count < MAX_RETRIES:
            delay = RETRY_DELAY * (2 ** retry_count)
            print(f"   ⚠️  HTTP 500 error, retrying in {delay:.1f}s (attempt {retry_count + 1}/{MAX_RETRIES})...")
            await asyncio.sleep(delay)
            return await fetch_ennetix_api(client, url, params, retry_count + 1)
        print(f"   ❌ HTTP error {e.response.status_code}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"   ❌ Failed to parse JSON: {e}")
        return None
    except Exception as e:
        print(f"   ❌ Error fetching API: {e}")
        return None


async def fetch_api1_threats(
    client: httpx.AsyncClient,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """API 1: Fetch threats from /alerts/ip/threats.json"""
    url = f"{ENNETIX_API_BASE_URL}/alerts/ip/threats.json"
    params = {
        "start": start_date,
        "end": end_date,
    }

    print(f"\n🔍 Fetching threats from: {url}")
    print(f"   Date range: {start_date} to {end_date}")

    data = await fetch_ennetix_api(client, url, params)

    if data is None:
        return []

    if isinstance(data, list):
        threats = data
    elif isinstance(data, dict):
        threats = data.get("threats") or data.get("data") or data.get("results") or []
    else:
        threats = []

    print(f"✅ Fetched {len(threats)} threat entries")
    return threats


async def fetch_api2_logs(
    client: httpx.AsyncClient,
    ip: str,
    signature_id: str,
    start_date: str,
    end_date: str,
) -> Optional[List[Dict[str, Any]]]:
    """API 2: Fetch logs from /alerts/{ip}/{signatureId}/logs.json"""
    url = f"{ENNETIX_API_BASE_URL}/alerts/{ip}/{signature_id}/logs.json"
    params = {
        "start": start_date,
        "end": end_date,
    }

    data = await fetch_ennetix_api(client, url, params)
    
    if data is None:
        return None
    
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return data.get("logs") or data.get("data") or []
    else:
        return []


async def fetch_api3_flows(
    client: httpx.AsyncClient,
    ip: str,
    start_date: str,
    end_date: str,
    service: str,
    role: str,
) -> Optional[List[Dict[str, Any]]]:
    """API 3: Fetch flows from /security/{ip}/flows.json"""
    url = f"{ENNETIX_API_BASE_URL}/security/{ip}/flows.json"
    params = {
        "start": start_date,
        "end": end_date,
        "service": service,
        "role": role,
    }

    data = await fetch_ennetix_api(client, url, params)
    
    if data is None:
        return None
    
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return data.get("flows") or data.get("data") or []
    else:
        return []


def get_earliest_signature_ids(suricata_logs: List[Dict[str, Any]]) -> List[str]:
    """Get all signatureIds from earliest timestamp documents in suricataLogs."""
    if not suricata_logs:
        return []
    
    # Find earliest timestamp
    earliest_timestamp = None
    for log in suricata_logs:
        timestamp_str = log.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if earliest_timestamp is None or timestamp < earliest_timestamp:
                    earliest_timestamp = timestamp
            except (ValueError, AttributeError):
                continue
    
    if earliest_timestamp is None:
        return []
    
    # Collect all signatureIds with earliest timestamp
    signature_ids = []
    for log in suricata_logs:
        timestamp_str = log.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if timestamp == earliest_timestamp:
                    sig_id = log.get("signatureId")
                    if sig_id is not None:
                        signature_ids.append(str(sig_id))
            except (ValueError, AttributeError):
                continue
    
    # Remove duplicates while preserving order
    seen = set()
    unique_ids = []
    for sig_id in signature_ids:
        if sig_id not in seen:
            seen.add(sig_id)
            unique_ids.append(sig_id)
    
    return unique_ids


def find_matching_flow(
    flows_list: List[Dict[str, Any]],
    target_timestamp: str
) -> Optional[Dict[str, Any]]:
    """Find flow document with @timestamp matching target_timestamp."""
    for flow in flows_list:
        flow_timestamp = flow.get("@timestamp")
        if flow_timestamp == target_timestamp:
            return flow
    return None


async def process_alert(
    http_client: httpx.AsyncClient,
    alert: Dict[str, Any],
    threat_ip: str,
    semaphore: asyncio.Semaphore,
    api3_semaphore: asyncio.Semaphore,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process a single alert and return documents for all 3 indexes."""
    async with semaphore:
        # Extract alert information
        alert_id = alert.get("id", "")
        
        # Validate alert_id is present (critical for cross-index linking)
        if not alert_id:
            print(f"   ⚠️  Warning: Alert missing ID, skipping...")
            return None, [], []
        
        start_time = alert.get("start", "")
        end_time = alert.get("time", "") or alert.get("end", start_time)
        entity_ids = alert.get("entityIds", {})
        ips = entity_ids.get("ips", [])
        
        # Use threat_ip if no IPs in entityIds
        if not ips:
            ips = [threat_ip] if threat_ip else []
        
        if not ips:
            return None, [], []
        
        ip = ips[0]  # Use first IP
        
        # Extract suricataLogs
        metadata = alert.get("metadata", {})
        suricata_logs = metadata.get("suricataLogs", [])
        
        # Prepare documents
        threat_doc = {
            "_id": f"{alert_id}",
            "_source": {
                "@timestamp": start_time,
                "alert_id": alert_id,
                "ip": ip,
                "threat_ip": threat_ip,
                "start_time": start_time,
                "end_time": end_time,
                "alert": alert,
            },
        }
        
        logs_docs = []
        flows_docs = []
        
        # API 2: Fetch logs for each signatureId
        if suricata_logs:
            # Get earliest signatureIds
            signature_ids = get_earliest_signature_ids(suricata_logs)
            
            # Get earliest timestamp for API 3 matching
            earliest_timestamp = None
            for log in suricata_logs:
                timestamp_str = log.get("timestamp")
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if earliest_timestamp is None or timestamp < earliest_timestamp:
                            earliest_timestamp = timestamp
                    except (ValueError, AttributeError):
                        continue
            
            earliest_timestamp_str = earliest_timestamp.isoformat().replace("+00:00", "Z") if earliest_timestamp else None
            
            # Fetch logs for each signatureId
            # Note: Using alert's start/end time. Alternative: use earliest suricataLogs timestamp as both start & end
            for sig_id in signature_ids:
                logs_data = await fetch_api2_logs(
                    http_client,
                    ip,
                    sig_id,
                    start_time,
                    end_time,
                )
                
                if logs_data:
                    # Extract sourceIp from logs (use first log's sourceIp)
                    source_ip = None
                    api2_timestamp = None
                    for log_entry in logs_data:
                        if isinstance(log_entry, dict):
                            source_ip = log_entry.get("sourceIp") or source_ip
                            api2_timestamp = log_entry.get("@timestamp") or api2_timestamp
                            if source_ip and api2_timestamp:
                                break
                    
                    # Use sourceIp from API 2, or fallback to IP from API 1
                    flow_ip = source_ip if source_ip else ip
                    
                    # Use API 2 timestamp or earliest suricataLogs timestamp
                    target_timestamp = api2_timestamp or earliest_timestamp_str
                    
                    logs_docs.append({
                        "_id": f"{alert_id}:{sig_id}",
                        "_source": {
                            "@timestamp": start_time,
                            "alert_id": alert_id,
                            "ip": ip,
                            "signature_id": sig_id,
                            "source_ip": source_ip,
                            "logs": logs_data,
                        },
                    })
                    
                    # API 3: Fetch flows for all service/role combinations
                    # Find the matching flow (should be only one document with matching timestamp)
                    # Use separate semaphore to limit concurrent API 3 calls
                    if flow_ip and target_timestamp:
                        matching_flow_found = False
                        for service in SERVICES:
                            if matching_flow_found:
                                break
                            for role in ROLES:
                                async with api3_semaphore:  # Limit concurrent API 3 calls
                                    flows_data = await fetch_api3_flows(
                                        http_client,
                                        flow_ip,
                                        start_time,
                                        end_time,
                                        service,
                                        role,
                                    )
                                    
                                    if flows_data:
                                        # Find matching flow by timestamp
                                        matching_flow = find_matching_flow(flows_data, target_timestamp)
                                        
                                        if matching_flow:
                                            flows_docs.append({
                                                "_id": f"{alert_id}:{sig_id}:{service}:{role}",
                                                "_source": {
                                                    "@timestamp": start_time,
                                                    "alert_id": alert_id,
                                                    "ip": flow_ip,
                                                    "signature_id": sig_id,
                                                    "service": service,
                                                    "role": role,
                                                    "target_timestamp": target_timestamp,
                                                    "flow": matching_flow,
                                                },
                                            })
                                            # Only one matching flow should exist, stop searching
                                            matching_flow_found = True
                                            break
                                    
                                    # Small delay between API 3 calls to reduce server load
                                    await asyncio.sleep(0.1)
        else:
            # No suricataLogs - alert_info will be empty list
            # Optionally create a placeholder log document with alert_id for consistency
            # (Currently skipped per requirements, but can be added if needed)
            
            # Still try to fetch flows using IP from entityIds
            # Note: Without suricataLogs, we don't have a specific timestamp to match,
            # so we use the alert's start time as a fallback
            if ip:
                target_timestamp = start_time  # Use alert start time as fallback
                matching_flow_found = False
                for service in SERVICES:
                    if matching_flow_found:
                        break
                    for role in ROLES:
                        async with api3_semaphore:  # Limit concurrent API 3 calls
                            flows_data = await fetch_api3_flows(
                                http_client,
                                ip,
                                start_time,
                                end_time,
                                service,
                                role,
                            )
                            
                            if flows_data:
                                matching_flow = find_matching_flow(flows_data, target_timestamp)
                                if matching_flow:
                                    flows_docs.append({
                                        "_id": f"{alert_id}:{service}:{role}",
                                        "_source": {
                                            "@timestamp": start_time,
                                            "alert_id": alert_id,
                                            "ip": ip,
                                            "service": service,
                                            "role": role,
                                            "target_timestamp": target_timestamp,
                                            "flow": matching_flow,
                                        },
                                    })
                                    # Only one matching flow should exist, stop searching
                                    matching_flow_found = True
                                    break
                            
                            # Small delay between API 3 calls to reduce server load
                            await asyncio.sleep(0.1)
        
        return threat_doc, logs_docs, flows_docs


def index_documents(
    es_client: Elasticsearch,
    index_name: str,
    documents: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """Bulk index documents into Elasticsearch."""
    if not documents:
        return 0, 0

    ensure_index_exists(es_client, index_name)

    try:
        actions = []
        for doc in documents:
            actions.append({
                "_index": index_name,
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


async def main() -> None:
    """Main execution function."""
    print("=" * 80)
    print("🚀 Ennetix API -> Cygeniq ECS Data Puller")
    print("=" * 80)
    
    # Calculate date range (30 days from today)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    print(f"\n📅 Date range: {start_date_str} to {end_date_str}")
    print(f"⚡ Concurrent API batch size: {API_BATCH_SIZE}")

    # Check authentication
    if ENNETIX_XAUTH:
        print(f"\n🔐 Ennetix authentication: Using xauth token")
    elif ENNETIX_USERNAME and ENNETIX_PASSWORD:
        print(f"\n🔐 Ennetix authentication: Using username/password")
    else:
        print("\n⚠️  WARNING: No Ennetix authentication credentials found!")
        print("   Please set ENNETIX_XAUTH or ENNETIX_USERNAME/ENNETIX_PASSWORD in .env")

    # Create Cygeniq Elasticsearch client
    cygeniq_client = create_cygeniq_client()
    if not cygeniq_client:
        print("\n⚠️  Cygeniq Elasticsearch client not available. Exiting.")
        return

    # Prepare documents for each index
    threats_docs: List[Dict[str, Any]] = []
    logs_docs: List[Dict[str, Any]] = []
    flows_docs: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(follow_redirects=False) as http_client:
        # Step 1: Fetch threats (API 1)
        print("\n" + "=" * 80)
        print("STEP 1: Fetching threats from Ennetix API (API 1)")
        print("=" * 80)
        threats = await fetch_api1_threats(http_client, start_date_str, end_date_str)

        if not threats:
            print("\n⚠️  No threats found. Exiting.")
            return

        # Step 2: Process each threat and its alerts
        print(f"\n📋 Processing {len(threats)} threat entries...")
        print("=" * 80)

        semaphore = asyncio.Semaphore(API_BATCH_SIZE)
        api3_semaphore = asyncio.Semaphore(API3_BATCH_SIZE)  # Separate semaphore for API 3
        
        # Collect all alerts from all threats
        all_alerts = []
        for threat in threats:
            threat_ip = threat.get("ip") or threat.get("id", "")
            alerts = threat.get("alerts", [])
            for alert in alerts:
                all_alerts.append((alert, threat_ip))
        
        print(f"📋 Total alerts to process: {len(all_alerts)}")
        print(f"⚡ API 1 & 2 concurrency: {API_BATCH_SIZE}")
        print(f"⚡ API 3 (flows) concurrency: {API3_BATCH_SIZE}")
        print(f"🔄 Max retries for 500 errors: {MAX_RETRIES}")
        
        # Process alerts in batches
        for batch_start in range(0, len(all_alerts), API_BATCH_SIZE):
            batch_end = min(batch_start + API_BATCH_SIZE, len(all_alerts))
            batch = all_alerts[batch_start:batch_end]
            batch_num = (batch_start // API_BATCH_SIZE) + 1
            total_batches = (len(all_alerts) + API_BATCH_SIZE - 1) // API_BATCH_SIZE
            
            print(f"\n📦 Processing batch {batch_num}/{total_batches} (alerts {batch_start+1}-{batch_end})...")

            tasks = [
                process_alert(http_client, alert, threat_ip, semaphore, api3_semaphore)
                for alert, threat_ip in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    alert_id = batch[idx][0].get("id", "unknown")
                    print(f"   ⚠️  Error processing alert {alert_id}: {result}")
                    continue

                threat_doc, alert_logs, alert_flows = result
                if threat_doc:
                    threats_docs.append(threat_doc)
                if alert_logs:
                    logs_docs.extend(alert_logs)
                if alert_flows:
                    flows_docs.extend(alert_flows)

            print(f"   ✅ Batch {batch_num} completed")

        print(f"\n✅ All {len(all_alerts)} alerts processed")

        # Step 3: Store all data in Cygeniq Elasticsearch
        print("\n" + "=" * 80)
        print("STEP 3: Storing data in Cygeniq Elasticsearch")
        print("=" * 80)

        # Store threats
        print(f"\n📤 Indexing {len(threats_docs)} threats documents...")
        threats_success, threats_errors = index_documents(cygeniq_client, THREATS_INDEX, threats_docs)
        print(f"   ✅ Indexed {threats_success} documents, {threats_errors} errors")

        # Store logs
        print(f"\n📤 Indexing {len(logs_docs)} logs documents...")
        logs_success, logs_errors = index_documents(cygeniq_client, LOGS_INDEX, logs_docs)
        print(f"   ✅ Indexed {logs_success} documents, {logs_errors} errors")

        # Store flows
        print(f"\n📤 Indexing {len(flows_docs)} flows documents...")
        flows_success, flows_errors = index_documents(cygeniq_client, FLOWS_INDEX, flows_docs)
        print(f"   ✅ Indexed {flows_success} documents, {flows_errors} errors")

    # Summary
    print("\n" + "=" * 80)
    print("📊 Summary")
    print("=" * 80)
    print(f"  Threats processed: {len(threats)}")
    print(f"  Alerts processed: {len(all_alerts)}")
    print(f"  Threats indexed: {threats_success}/{len(threats_docs)}")
    print(f"  Logs indexed: {logs_success}/{len(logs_docs)}")
    print(f"  Flows indexed: {flows_success}/{len(flows_docs)}")
    print("=" * 80)
    print("✨ Script completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

