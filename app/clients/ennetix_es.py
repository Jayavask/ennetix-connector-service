"""
Ennetix Elasticsearch client
"""
from typing import Optional, Dict, Any
from elasticsearch import AsyncElasticsearch
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()


class EnnetixESClient:
    """Client for connecting to Ennetix Elasticsearch"""
    
    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
    
    async def connect(self):
        """Initialize Elasticsearch client connection"""
        http_auth = None
        if settings.ENNETIX_ELASTICSEARCH_USERNAME and settings.ENNETIX_ELASTICSEARCH_PASSWORD:
            http_auth = (settings.ENNETIX_ELASTICSEARCH_USERNAME, settings.ENNETIX_ELASTICSEARCH_PASSWORD)
        
        # Parse verify_certs from string to boolean
        verify_certs = settings.ENNETIX_ELASTICSEARCH_VERIFY_CERTS.lower() == "true"
        
        # Extract hosts (can be comma-separated or single URL)
        hosts = [host.strip() for host in settings.ENNETIX_ELASTICSEARCH_HOSTS.split(",")]
        
        self.client = AsyncElasticsearch(
            hosts,
            http_auth=http_auth,
            verify_certs=verify_certs,
            request_timeout=settings.ENNETIX_ELASTICSEARCH_REQUEST_TIMEOUT,
        )
        logger.info("Connected to Ennetix Elasticsearch")
    
    async def disconnect(self):
        """Close Elasticsearch client connection"""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Ennetix Elasticsearch")
    
    async def search(self, index: str, body: Dict[str, Any], **kwargs):
        """Execute search query"""
        if not self.client:
            await self.connect()
        return await self.client.search(index=index, body=body, **kwargs)
    
    async def scroll(self, scroll_id: str, scroll: str = "5m"):
        """Continue scroll operation"""
        if not self.client:
            await self.connect()
        return await self.client.scroll(scroll_id=scroll_id, scroll=scroll)


# Global client instance
ennetix_client = EnnetixESClient()

