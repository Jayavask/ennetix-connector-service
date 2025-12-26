"""
P1: Fetch data from Ennetix API and store as API output data (CS1)
"""
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta, timezone
import asyncio
import httpx
from app.clients.ennetix_api import EnnetixAPIClient
from app.clients.cygeniq_es import CygeniqESClient
from app.processor.alert_processor import AlertProcessor
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()


class EnnetixAPIFetcher:
    """P1: Fetches data from Ennetix API and stores in Cygeniq Elasticsearch (CS1)"""
    
    def __init__(self):
        self.api_client = EnnetixAPIClient()
        self.processor = AlertProcessor()
        self.cygeniq_client = CygeniqESClient()
        self.api_batch_size = settings.ENNETIX_API_BATCH_SIZE
        self.api3_batch_size = settings.ENNETIX_API3_BATCH_SIZE
        self.batch_size = settings.BATCH_SIZE
        self.date_range_days = settings.P1_DATE_RANGE_DAYS
    
    async def fetch_and_store(
        self,
        start_date: str = None,
        end_date: str = None,
    ) -> Dict[str, Any]:
        """
        Main execution function for P1
        
        Args:
            start_date: Start date in ISO format (optional, defaults to date_range_days ago)
            end_date: End date in ISO format (optional, defaults to now)
        
        Returns:
            Summary dictionary with counts
        """
        logger.info("=" * 80)
        logger.info("🚀 Ennetix API -> Cygeniq ECS Data Puller (P1)")
        logger.info("=" * 80)
        
        # Calculate date range
        if end_date is None:
            end_date_dt = datetime.now(timezone.utc)
            end_date = end_date_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        else:
            end_date_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        
        if start_date is None:
            start_date_dt = end_date_dt - timedelta(days=self.date_range_days)
            start_date = start_date_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        logger.info(f"📅 Date range: {start_date} to {end_date}")
        logger.info(f"⚡ Concurrent API batch size: {self.api_batch_size}")

        # Check authentication
        if settings.ENNETIX_XAUTH:
            logger.info("🔐 Ennetix authentication: Using xauth token")
        elif settings.ENNETIX_ELASTICSEARCH_USERNAME and settings.ENNETIX_ELASTICSEARCH_PASSWORD:
            logger.info("🔐 Ennetix authentication: Using username/password")
        else:
            logger.warning("WARNING: No Ennetix authentication credentials found!")
            logger.warning("Please set ENNETIX_XAUTH or ENNETIX_USERNAME/ENNETIX_PASSWORD in .env")

        # Connect to Cygeniq
        await self.cygeniq_client.connect()
        if not self.cygeniq_client.client:
            logger.error("Cygeniq Elasticsearch client not available. Exiting.")
            return {
                "status": "error",
                "message": "Cygeniq Elasticsearch client not available"
            }

        # Cumulative counters for summary
        total_threats_indexed = 0
        total_threats_errors = 0
        total_logs_indexed = 0
        total_logs_errors = 0
        total_flows_indexed = 0
        total_flows_errors = 0
        threats = []
        all_alerts = []

        async with httpx.AsyncClient(follow_redirects=False) as http_client:
            # Step 1: Fetch threats (API 1)
            logger.info("=" * 80)
            logger.info("STEP 1: Fetching threats from Ennetix API (API 1)")
            logger.info("=" * 80)
            threats = await self.api_client.fetch_threats(http_client, start_date, end_date)

            if not threats:
                logger.warning("No threats found. Exiting.")
                return {
                    "status": "completed",
                    "threats_processed": 0,
                    "alerts_processed": 0,
                    "threats_indexed": 0,
                    "logs_indexed": 0,
                    "flows_indexed": 0,
                }

            # Step 2: Process each threat and its alerts
            logger.info(f"📋 Processing {len(threats)} threat entries...")
            logger.info("=" * 80)

            semaphore = asyncio.Semaphore(self.api_batch_size)
            api3_semaphore = asyncio.Semaphore(self.api3_batch_size)  # Separate semaphore for API 3
            
            # Collect all alerts from all threats
            for threat in threats:
                threat_ip = threat.get("ip") or threat.get("id", "")
                alerts = threat.get("alerts", [])
                for alert in alerts:
                    all_alerts.append((alert, threat_ip))
            
            logger.info(f"📋 Total alerts to process: {len(all_alerts)}")
            logger.info(f"⚡ API 1 & 2 concurrency: {self.api_batch_size}")
            logger.info(f"⚡ API 3 (flows) concurrency: {self.api3_batch_size}")
            logger.info(f"🔄 Max retries for 500 errors: {settings.ENNETIX_MAX_RETRIES}")
            
            # Step 3: Process alerts in batches and push to ES after each batch
            logger.info("=" * 80)
            logger.info("STEP 2 & 3: Processing alerts and storing in Cygeniq Elasticsearch (CS1)")
            logger.info("=" * 80)
            
            # Process alerts in batches
            for batch_start in range(0, len(all_alerts), self.api_batch_size):
                batch_end = min(batch_start + self.api_batch_size, len(all_alerts))
                batch = all_alerts[batch_start:batch_end]
                batch_num = (batch_start // self.api_batch_size) + 1
                total_batches = (len(all_alerts) + self.api_batch_size - 1) // self.api_batch_size
                
                logger.info(f"📦 Processing batch {batch_num}/{total_batches} (alerts {batch_start+1}-{batch_end})...")

                tasks = [
                    self.processor.process_alert(http_client, alert, threat_ip, semaphore, api3_semaphore)
                    for alert, threat_ip in batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Collect documents from this batch
                batch_threats_docs: List[Dict[str, Any]] = []
                batch_logs_docs: List[Dict[str, Any]] = []
                batch_flows_docs: List[Dict[str, Any]] = []

                for idx, result in enumerate(results):
                    if isinstance(result, Exception):
                        alert_id = batch[idx][0].get("id", "unknown")
                        logger.warning(f"Error processing alert {alert_id}: {result}")
                        continue

                    threat_doc, alert_logs, alert_flows = result
                    if threat_doc:
                        batch_threats_docs.append(threat_doc)
                    if alert_logs:
                        batch_logs_docs.extend(alert_logs)
                    if alert_flows:
                        batch_flows_docs.extend(alert_flows)

                logger.info(f"✅ Batch {batch_num} processing completed")

                # Immediately push this batch's data to Elasticsearch
                logger.info(f"📤 Pushing batch {batch_num} data to Cygeniq Elasticsearch...")

                # Store threats from this batch
                if batch_threats_docs:
                    threats_success, threats_errors = await self.cygeniq_client.bulk_index_with_ids(
                        settings.THREATS_INDEX,
                        batch_threats_docs,
                        chunk_size=self.batch_size,
                    )
                    total_threats_indexed += threats_success
                    total_threats_errors += threats_errors
                    logger.info(f"  ✅ Threats: {threats_success} indexed, {threats_errors} errors (Total: {total_threats_indexed})")

                # Store logs from this batch
                if batch_logs_docs:
                    logs_success, logs_errors = await self.cygeniq_client.bulk_index_with_ids(
                        settings.LOGS_INDEX,
                        batch_logs_docs,
                        chunk_size=self.batch_size,
                    )
                    total_logs_indexed += logs_success
                    total_logs_errors += logs_errors
                    logger.info(f"  ✅ Logs: {logs_success} indexed, {logs_errors} errors (Total: {total_logs_indexed})")

                # Store flows from this batch
                if batch_flows_docs:
                    flows_success, flows_errors = await self.cygeniq_client.bulk_index_with_ids(
                        settings.FLOWS_INDEX,
                        batch_flows_docs,
                        chunk_size=self.batch_size,
                    )
                    total_flows_indexed += flows_success
                    total_flows_errors += flows_errors
                    logger.info(f"  ✅ Flows: {flows_success} indexed, {flows_errors} errors (Total: {total_flows_indexed})")

                logger.info(f"✅ Batch {batch_num}/{total_batches} completed and pushed to ES")

            logger.info(f"✅ All {len(all_alerts)} alerts processed and indexed")

        # Summary
        summary = {
            "status": "completed",
            "threats_processed": len(threats),
            "alerts_processed": len(all_alerts),
            "threats_indexed": total_threats_indexed,
            "threats_errors": total_threats_errors,
            "logs_indexed": total_logs_indexed,
            "logs_errors": total_logs_errors,
            "flows_indexed": total_flows_indexed,
            "flows_errors": total_flows_errors,
        }
        
        logger.info("=" * 80)
        logger.info("📊 Final Summary")
        logger.info("=" * 80)
        logger.info(f"  Threats processed: {len(threats)}")
        logger.info(f"  Alerts processed: {len(all_alerts)}")
        logger.info(f"  Threats indexed: {total_threats_indexed} (errors: {total_threats_errors})")
        logger.info(f"  Logs indexed: {total_logs_indexed} (errors: {total_logs_errors})")
        logger.info(f"  Flows indexed: {total_flows_indexed} (errors: {total_flows_errors})")
        logger.info("=" * 80)
        logger.info("✨ P1 Script completed!")
        logger.info("=" * 80)
        
        return summary

