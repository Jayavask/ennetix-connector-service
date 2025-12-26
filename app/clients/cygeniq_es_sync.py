"""
Synchronous Cygeniq Elasticsearch client for P2 operations
"""
from typing import Optional, Dict, Any, List
from elasticsearch import Elasticsearch
import urllib3
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()

# Disable SSL warnings if verify_certs is False
if settings.ELASTICSEARCH_CYGENIQ_VERIFY_CERTS.lower() != "true":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CygeniqESSyncClient:
    """Synchronous client for connecting to Cygeniq Elasticsearch (for P2)"""
    
    def __init__(self):
        self.client: Optional[Elasticsearch] = None
    
    def connect(self):
        """Initialize Elasticsearch client connection"""
        if not settings.CONNECTOR_SERVICE_URL:
            logger.warning("CONNECTOR_SERVICE_URL is not configured")
            return None
        
        http_auth = None
        if settings.ELASTICSEARCH_CYGENIQ_USERNAME and settings.ELASTICSEARCH_CYGENIQ_PASSWORD:
            http_auth = (settings.ELASTICSEARCH_CYGENIQ_USERNAME, settings.ELASTICSEARCH_CYGENIQ_PASSWORD)
        
        # Parse verify_certs from string to boolean
        verify_certs = settings.ELASTICSEARCH_CYGENIQ_VERIFY_CERTS.lower() == "true"
        
        # Remove trailing slash from URL if present
        url = settings.CONNECTOR_SERVICE_URL.rstrip("/")
        
        client_config: Dict[str, Any] = {
            "hosts": [url],
            "request_timeout": settings.ELASTICSEARCH_CYGENIQ_REQUEST_TIMEOUT,
            "max_retries": settings.ELASTICSEARCH_CYGENIQ_MAX_RETRIES,
            "retry_on_timeout": True,
        }
        
        if http_auth:
            client_config["basic_auth"] = http_auth
        
        if verify_certs:
            client_config["verify_certs"] = True
        else:
            client_config["verify_certs"] = False
            client_config["ssl_show_warn"] = False
        
        try:
            self.client = Elasticsearch(**client_config)
            info = self.client.info()
            logger.info(f"Connected to Cygeniq Elasticsearch (version: {info['version']['number']})")
            return self.client
        except Exception as exc:
            logger.error(f"Failed to connect to Cygeniq Elasticsearch: {exc}")
            return None
    
    def ensure_index_exists(self, index_name: str) -> None:
        """Ensure index exists in Cygeniq ES, create if it doesn't."""
        if not self.client:
            self.connect()
        
        if not self.client:
            return
        
        try:
            if not self.client.indices.exists(index=index_name):
                logger.info(f"Creating index {index_name} in Cygeniq...")
                self.client.indices.create(
                    index=index_name,
                    body={
                        "settings": {
                            "number_of_shards": 1,
                            "number_of_replicas": 0,
                        }
                    },
                )
                logger.info(f"Created index {index_name}")
        except Exception as exc:
            logger.warning(f"Could not create index {index_name}: {exc}")
    
    def scan(self, index: str, query: Dict[str, Any], scroll: str = "2m", size: int = 1000):
        """Scan index with query"""
        if not self.client:
            self.connect()
        
        if not self.client:
            return []
        
        from elasticsearch.helpers import scan
        return scan(
            self.client,
            query=query,
            index=index,
            scroll=scroll,
            size=size,
        )
    
    def search(self, index: str, body: Dict[str, Any], size: int = 1000):
        """Search index"""
        if not self.client:
            self.connect()
        
        if not self.client:
            return {"hits": {"hits": []}}
        
        return self.client.search(
            index=index,
            body=body,
            size=size
        )
    
    def bulk_index(self, documents: List[Dict[str, Any]], chunk_size: int = 500) -> tuple:
        """Bulk index documents"""
        if not self.client:
            self.connect()
        
        if not self.client or not documents:
            return 0, 0
        
        index_name = documents[0].get("_index") if documents else None
        if index_name:
            self.ensure_index_exists(index_name)
        
        try:
            actions = []
            for doc in documents:
                action = {
                    "_index": doc.get("_index"),
                    "_id": doc.get("_id"),
                    "_source": doc.get("_source", {}),
                }
                actions.append(action)
            
            from elasticsearch.helpers import bulk
            success, errors = bulk(
                self.client,
                actions,
                chunk_size=chunk_size,
                request_timeout=60,
                raise_on_error=False,
            )
            
            if errors:
                logger.warning(f"{len(errors)} documents failed to index (showing first 3):")
                for err in errors[:3]:
                    logger.warning(f"  {err}")
            
            return success, len(errors) if errors else 0
        
        except Exception as exc:
            logger.error(f"Error during bulk indexing: {exc}")
            return 0, len(documents)

