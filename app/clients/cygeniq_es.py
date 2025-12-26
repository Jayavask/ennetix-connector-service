"""
Cygeniq Elasticsearch client
"""
from typing import Optional, Dict, Any, List
from elasticsearch import AsyncElasticsearch
import urllib3
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()

# Disable SSL warnings if verify_certs is False
if settings.ELASTICSEARCH_CYGENIQ_VERIFY_CERTS.lower() != "true":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
    
    async def ensure_index_exists(self, index_name: str) -> None:
        """Ensure index exists in Cygeniq ES, create if it doesn't."""
        if not self.client:
            await self.connect()
        
        try:
            if not await self.client.indices.exists(index=index_name):
                logger.info(f"Creating index {index_name} in Cygeniq...")
                await self.client.indices.create(
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
    
    async def bulk_index_with_ids(
        self,
        index: str,
        documents: List[Dict[str, Any]],
        chunk_size: int = 500,
    ) -> tuple:
        """
        Bulk index documents with custom _id field
        
        Args:
            index: Index name
            documents: List of documents with _id and _source fields
            chunk_size: Batch size for bulk operations
        
        Returns:
            Tuple of (success_count, error_count)
        """
        if not self.client:
            await self.connect()
        
        if not documents:
            return 0, 0
        
        await self.ensure_index_exists(index)
        
        try:
            actions = []
            for doc in documents:
                action = {
                    "_index": index,
                    "_source": doc.get("_source", {}),
                }
                if "_id" in doc:
                    action["_id"] = doc["_id"]
                actions.append(action)
            
            from elasticsearch.helpers import async_bulk
            success, errors = await async_bulk(
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

