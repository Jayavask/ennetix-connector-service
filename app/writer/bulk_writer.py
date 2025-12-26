"""
Bulk indexing to Cygeniq Elasticsearch
"""
from typing import List, Dict, Any
from app.clients.cygeniq_es import CygeniqESClient
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()


class BulkWriter:
    """Handles bulk indexing of documents to Cygeniq Elasticsearch"""
    
    def __init__(self):
        self.client = CygeniqESClient()
        self.batch_size = settings.BATCH_SIZE
    
    async def write_bulk(
        self,
        group_type: str,
        documents: List[Dict[str, Any]],
        index_suffix: str = None
    ):
        """
        Write documents in bulk to Cygeniq Elasticsearch
        
        Args:
            group_type: Type of group (endpoint, network, application)
            documents: List of documents to index
            index_suffix: Optional suffix for index name
        """
        if not documents:
            logger.warning("No documents to write")
            return
        
        # Construct index name
        index_name = f"{settings.CYGENIQ_INDEX_PREFIX}{group_type}"
        if index_suffix:
            index_name = f"{index_name}-{index_suffix}"
        
        try:
            # Ensure client is connected
            await self.client.connect()
            
            # Check if index exists, create if not
            if not await self.client.index_exists(index_name):
                logger.info(f"Index {index_name} does not exist, will be created on first write")
            
            # Write in batches
            for i in range(0, len(documents), self.batch_size):
                batch = documents[i:i + self.batch_size]
                success, failed = await self.client.bulk_index(index_name, batch)
                
                if failed:
                    logger.error(f"Failed to index {len(failed)} documents in batch")
                else:
                    logger.info(f"Successfully indexed batch of {len(batch)} documents")
        
        except Exception as e:
            logger.error(f"Error writing bulk documents: {str(e)}", exc_info=True)
            raise

