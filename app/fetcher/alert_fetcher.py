"""
Scroll/search_after logic for fetching alerts from Ennetix
"""
from typing import Dict, Any, List, Optional, AsyncIterator
from app.clients.ennetix_es import ennetix_client
from app.config import settings
from app.logging import setup_logging

logger = setup_logging()


class AlertFetcher:
    """Fetches alerts from Ennetix using scroll or search_after"""
    
    def __init__(self, index_pattern: str = None):
        self.index_pattern = index_pattern or settings.ENNETIX_INDEX_PATTERN
        self.scroll_size = settings.SCROLL_SIZE
        self.scroll_timeout = settings.SCROLL_TIMEOUT
    
    async def fetch_with_scroll(
        self,
        query: Dict[str, Any],
        size: Optional[int] = None
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """
        Fetch documents using scroll API
        
        Args:
            query: Elasticsearch query
            size: Number of documents per batch (defaults to scroll_size)
        
        Yields:
            Batches of documents
        """
        size = size or self.scroll_size
        
        # Initial search with scroll
        response = await ennetix_client.search(
            index=self.index_pattern,
            body={
                "query": query,
                "size": size
            },
            scroll=self.scroll_timeout
        )
        
        scroll_id = response.get("_scroll_id")
        hits = response.get("hits", {}).get("hits", [])
        
        while hits:
            logger.info(f"Fetched batch of {len(hits)} documents")
            yield hits
            
            # Continue scrolling
            if scroll_id:
                response = await ennetix_client.scroll(
                    scroll_id=scroll_id,
                    scroll=self.scroll_timeout
                )
                scroll_id = response.get("_scroll_id")
                hits = response.get("hits", {}).get("hits", [])
            else:
                break
    
    async def fetch_with_search_after(
        self,
        query: Dict[str, Any],
        sort_field: str = "@timestamp",
        size: Optional[int] = None
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """
        Fetch documents using search_after API (preferred for large datasets)
        
        Args:
            query: Elasticsearch query
            sort_field: Field to sort by for pagination
            size: Number of documents per batch
        
        Yields:
            Batches of documents
        """
        size = size or self.scroll_size
        search_after = None
        
        while True:
            body = {
                "query": query,
                "size": size,
                "sort": [{sort_field: "asc"}]
            }
            
            if search_after:
                body["search_after"] = search_after
            
            response = await ennetix_client.search(
                index=self.index_pattern,
                body=body
            )
            
            hits = response.get("hits", {}).get("hits", [])
            
            if not hits:
                break
            
            logger.info(f"Fetched batch of {len(hits)} documents")
            yield hits
            
            # Get sort values from last document
            last_hit = hits[-1]
            search_after = last_hit.get("sort")
            
            if not search_after:
                break

