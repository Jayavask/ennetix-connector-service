"""
ENDPOINT/NETWORK/APPLICATION group router
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
from pydantic import BaseModel
from app.logging import setup_logging
from app.mappers.endpoint_mapper import EndpointMapper
from app.mappers.network_mapper import NetworkMapper
from app.mappers.application_mapper import ApplicationMapper
from app.fetcher.alert_fetcher import AlertFetcher
from app.writer.bulk_writer import BulkWriter

logger = setup_logging()
router = APIRouter(prefix="/api/v1", tags=["groups"])


class SyncRequest(BaseModel):
    """Request model for sync operations"""
    group_type: str  # ENDPOINT, NETWORK, or APPLICATION
    index_pattern: Optional[str] = None
    query: Optional[dict] = None


@router.post("/sync/{group_type}")
async def sync_group(
    group_type: str,
    background_tasks: BackgroundTasks,
    request: Optional[SyncRequest] = None
):
    """
    Sync alerts for a specific group type (ENDPOINT, NETWORK, APPLICATION)
    """
    group_type = group_type.upper()
    
    if group_type not in ["ENDPOINT", "NETWORK", "APPLICATION"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_type. Must be one of: ENDPOINT, NETWORK, APPLICATION"
        )
    
    # Select appropriate mapper
    mapper_map = {
        "ENDPOINT": EndpointMapper(),
        "NETWORK": NetworkMapper(),
        "APPLICATION": ApplicationMapper(),
    }
    
    mapper = mapper_map[group_type]
    fetcher = AlertFetcher()
    writer = BulkWriter()
    
    # Start background sync task
    background_tasks.add_task(
        _sync_group_task,
        mapper,
        fetcher,
        writer,
        group_type,
        request.query if request else None
    )
    
    return {
        "status": "accepted",
        "message": f"Sync started for {group_type} group",
        "group_type": group_type
    }


async def _sync_group_task(mapper, fetcher, writer, group_type, query):
    """Background task to sync group data"""
    try:
        logger.info(f"Starting sync for {group_type} group")
        
        # Default query if none provided
        if not query:
            query = {"match_all": {}}
        
        # Fetch and process in batches
        async for batch in fetcher.fetch_with_search_after(query):
            # Map documents
            mapped_docs = [mapper.map(doc["_source"]) for doc in batch]
            
            # Validate and write
            validated_docs = [doc for doc in mapped_docs if doc is not None]
            if validated_docs:
                await writer.write_bulk(group_type.lower(), validated_docs)
        
        logger.info(f"Completed sync for {group_type} group")
    except Exception as e:
        logger.error(f"Error syncing {group_type} group: {str(e)}", exc_info=True)

