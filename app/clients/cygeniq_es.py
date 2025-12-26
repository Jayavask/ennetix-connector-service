"""
Cygeniq Elasticsearch client
"""
from typing import Optional, Dict, Any, List
from elasticsearch import AsyncElasticsearch
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()


class CygeniqESClient:
    """Client for connecting to Cygeniq Elasticsearch"""
    
    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
    
    async def connect(self):
        """Initialize Elasticsearch client connection"""
        http_auth = None
        if settings.ELASTICSEARCH_CYGENIQ_USERNAME and settings.ELASTICSEARCH_CYGENIQ_PASSWORD:
            http_auth = (settings.ELASTICSEARCH_CYGENIQ_USERNAME, settings.ELASTICSEARCH_CYGENIQ_PASSWORD)
        
        # Parse verify_certs from string to boolean
        verify_certs = settings.ELASTICSEARCH_CYGENIQ_VERIFY_CERTS.lower() == "true"
        
        # Remove trailing slash from URL if present
        url = settings.CONNECTOR_SERVICE_URL.rstrip("/")
        
        self.client = AsyncElasticsearch(
            [url],
            http_auth=http_auth,
            verify_certs=verify_certs,
            request_timeout=settings.ELASTICSEARCH_CYGENIQ_REQUEST_TIMEOUT,
            max_retries=settings.ELASTICSEARCH_CYGENIQ_MAX_RETRIES,
        )
        logger.info("Connected to Cygeniq Elasticsearch")
    
    async def disconnect(self):
        """Close Elasticsearch client connection"""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Cygeniq Elasticsearch")
    
    async def bulk_index(self, index: str, documents: List[Dict[str, Any]]):
        """Bulk index documents"""
        if not self.client:
            await self.connect()
        
        actions = []
        for doc in documents:
            actions.append({
                "_index": index,
                "_source": doc
            })
        
        from elasticsearch.helpers import async_bulk
        success, failed = await async_bulk(self.client, actions)
        logger.info(f"Bulk indexed {success} documents, {len(failed)} failed")
        return success, failed
    
    async def index_exists(self, index: str) -> bool:
        """Check if index exists"""
        if not self.client:
            await self.connect()
        return await self.client.indices.exists(index=index)

