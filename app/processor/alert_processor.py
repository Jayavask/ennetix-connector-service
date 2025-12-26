"""
Alert processor for P1 - processes alerts and creates documents for threats, logs, and flows
"""
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
import asyncio
import httpx
from app.clients.ennetix_api import EnnetixAPIClient
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()

# Service and role combinations for API 3
SERVICES = ["dns", "ssh", "http", "https", "other"]
ROLES = ["client", "server"]


class AlertProcessor:
    """Processes alerts and fetches related logs and flows"""
    
    def __init__(self):
        self.api_client = EnnetixAPIClient()
        self.api_batch_size = settings.ENNETIX_API_BATCH_SIZE
        self.api3_batch_size = settings.ENNETIX_API3_BATCH_SIZE
        self.api3_delay = getattr(settings, 'ENNETIX_API3_DELAY', 0.1)
    
    def get_earliest_signature_ids(self, suricata_logs: List[Dict[str, Any]]) -> List[str]:
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
        self,
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
        self,
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
                logger.warning("Alert missing ID, skipping...")
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
                signature_ids = self.get_earliest_signature_ids(suricata_logs)
                
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
                    logs_data = await self.api_client.fetch_logs(
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
                                        flows_data = await self.api_client.fetch_flows(
                                            http_client,
                                            flow_ip,
                                            start_time,
                                            end_time,
                                            service,
                                            role,
                                        )
                                        
                                        if flows_data:
                                            # Find matching flow by timestamp
                                            matching_flow = self.find_matching_flow(flows_data, target_timestamp)
                                            
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
                                        await asyncio.sleep(self.api3_delay)
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
                                flows_data = await self.api_client.fetch_flows(
                                    http_client,
                                    ip,
                                    start_time,
                                    end_time,
                                    service,
                                    role,
                                )
                                
                                if flows_data:
                                    matching_flow = self.find_matching_flow(flows_data, target_timestamp)
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

