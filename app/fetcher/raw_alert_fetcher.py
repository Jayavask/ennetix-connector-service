"""
P2: Create Raw Alert from CS1 (API Output Data) and store in CS2 (Raw Alert)
"""
from typing import Dict, Any, List
from app.clients.cygeniq_es_sync import CygeniqESSyncClient
from app.processor.raw_alert_processor import build_raw_alert_document
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()


class RawAlertFetcher:
    """P2: Fetches data from CS1 indices and creates raw alerts in CS2"""
    
    def __init__(self):
        self.client = CygeniqESSyncClient()
        self.processing_batch_size = settings.RAW_ALERT_PROCESSING_BATCH_SIZE
        self.batch_size = settings.BATCH_SIZE
    
    def fetch_all_threats(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all threats from Index 1 (ennetix-threats) and index by alert_id."""
        logger.info(f"Fetching all threats from {settings.THREATS_INDEX}...")
        threats_by_alert_id = {}
        
        try:
            query = {
                "query": {"match_all": {}},
                "size": 10000
            }
            
            response = self.client.scan(
                settings.THREATS_INDEX,
                query=query,
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
            
            logger.info(f"Fetched {count} threats")
            return threats_by_alert_id
        except Exception as exc:
            logger.error(f"Error fetching threats: {exc}")
            return {}
    
    def fetch_all_logs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch all logs from Index 2 (ennetix-logs) and group by alert_id."""
        logger.info(f"Fetching all logs from {settings.LOGS_INDEX}...")
        logs_by_alert_id = {}
        
        try:
            query = {
                "query": {"match_all": {}},
                "size": 10000
            }
            
            response = self.client.scan(
                settings.LOGS_INDEX,
                query=query,
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
            
            logger.info(f"Fetched {count} log documents for {len(logs_by_alert_id)} unique alert_ids")
            return logs_by_alert_id
        except Exception as exc:
            logger.error(f"Error fetching logs: {exc}")
            return {}
    
    def fetch_all_flows(self) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch all flows from Index 3 (ennetix-flows) and group by alert_id."""
        logger.info(f"Fetching all flows from {settings.FLOWS_INDEX}...")
        flows_by_alert_id = {}
        
        try:
            query = {
                "query": {"match_all": {}},
                "size": 10000
            }
            
            response = self.client.scan(
                settings.FLOWS_INDEX,
                query=query,
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
            
            logger.info(f"Fetched {count} flow documents for {len(flows_by_alert_id)} unique alert_ids")
            return flows_by_alert_id
        except Exception as exc:
            logger.error(f"Error fetching flows: {exc}")
            return {}
    
    def process_and_store(self) -> Dict[str, Any]:
        """
        Main execution function for P2
        
        Returns:
            Summary dictionary with counts
        """
        logger.info("=" * 80)
        logger.info("🚀 Phase 2: Create Raw Alerts from Cygeniq ECS")
        logger.info("=" * 80)
        logger.info("CS1 (API Output Data) -> P2 (Create Raw Alert) -> CS2 (Raw Alert)")
        
        # Connect to Cygeniq
        client = self.client.connect()
        if not client:
            logger.error("Cygeniq Elasticsearch client not available. Exiting.")
            return {
                "status": "error",
                "message": "Cygeniq Elasticsearch client not available"
            }
        
        # Step 1: Fetch all data from all 3 indexes
        logger.info("=" * 80)
        logger.info("STEP 1: Fetching data from all 3 indexes")
        logger.info("=" * 80)
        
        # Fetch from Index 1 (threats)
        logger.info(f"📋 Index 1: {settings.THREATS_INDEX}")
        threats_by_alert_id = self.fetch_all_threats()
        
        # Fetch from Index 2 (logs)
        logger.info(f"📋 Index 2: {settings.LOGS_INDEX}")
        logs_by_alert_id = self.fetch_all_logs()
        
        # Fetch from Index 3 (flows)
        logger.info(f"📋 Index 3: {settings.FLOWS_INDEX}")
        flows_by_alert_id = self.fetch_all_flows()
        
        if not threats_by_alert_id:
            logger.warning("No threats found. Exiting.")
            return {
                "status": "completed",
                "threats_processed": 0,
                "raw_alerts_indexed": 0,
                "errors": 0,
            }
        
        logger.info(f"✅ Data fetched from all 3 indexes:")
        logger.info(f"   - Threats: {len(threats_by_alert_id)} unique alert_ids")
        logger.info(f"   - Logs: {len(logs_by_alert_id)} unique alert_ids")
        logger.info(f"   - Flows: {len(flows_by_alert_id)} unique alert_ids")
        
        # Step 2: Process threats in batches and store immediately
        logger.info("=" * 80)
        logger.info("STEP 2: Processing threats and building raw alerts (batch-wise)")
        logger.info("=" * 80)
        logger.info(f"📦 Processing batch size: {self.processing_batch_size}")
        
        total_threats = len(threats_by_alert_id)
        threats_list = list(threats_by_alert_id.items())
        total_batches = (total_threats + self.processing_batch_size - 1) // self.processing_batch_size
        
        total_indexed = 0
        total_errors = 0
        
        # Process in batches
        for batch_num in range(total_batches):
            batch_start = batch_num * self.processing_batch_size
            batch_end = min(batch_start + self.processing_batch_size, total_threats)
            batch = threats_list[batch_start:batch_end]
            
            logger.info(f"📦 Processing batch {batch_num + 1}/{total_batches} (alerts {batch_start + 1}-{batch_end})...")
            
            raw_alert_docs = []
            
            for alert_id, threat_data in batch:
                # Get logs from Index 2 (already fetched, just lookup)
                logs_data = logs_by_alert_id.get(alert_id, [])
                
                # Get flows from Index 3 (already fetched, just lookup)
                flows_data = flows_by_alert_id.get(alert_id, [])
                
                # Build raw alert document
                raw_alert = build_raw_alert_document(
                    threat_data,
                    logs_data,
                    flows_data,
                    alert_id,
                    settings.RAW_ALERT_INDEX
                )
                if raw_alert:
                    raw_alert_docs.append(raw_alert)
            
            # Store batch immediately
            if raw_alert_docs:
                logger.info(f"📤 Indexing {len(raw_alert_docs)} raw alert documents from batch {batch_num + 1}...")
                success, errors = self.client.bulk_index(raw_alert_docs, chunk_size=self.batch_size)
                total_indexed += success
                total_errors += errors
                logger.info(f"✅ Batch {batch_num + 1} indexed: {success} documents, {errors} errors (Total: {total_indexed})")
            else:
                logger.warning(f"Batch {batch_num + 1} produced no raw alert documents")
        
        logger.info(f"✅ Built and indexed {total_indexed} raw alert documents in {total_batches} batches")
        
        # Summary
        summary = {
            "status": "completed",
            "threats_processed": total_threats,
            "batches_processed": total_batches,
            "raw_alerts_indexed": total_indexed,
            "errors": total_errors,
        }
        
        logger.info("=" * 80)
        logger.info("📊 Summary")
        logger.info("=" * 80)
        logger.info(f"  Threats processed: {total_threats}")
        logger.info(f"  Batches processed: {total_batches}")
        logger.info(f"  Raw alerts indexed: {total_indexed}")
        logger.info(f"  Errors: {total_errors}")
        logger.info("=" * 80)
        logger.info("✨ Phase 2 completed!")
        logger.info("=" * 80)
        
        return summary

