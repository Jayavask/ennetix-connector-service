"""
P2 Router - Create Raw Alert from CS1 data
"""
from fastapi import APIRouter, BackgroundTasks
from app.fetcher.raw_alert_fetcher import RawAlertFetcher
from app.logging import setup_logging

logger = setup_logging()
router = APIRouter(prefix="/api/v1/p2", tags=["p2"])


@router.post("/sync")
async def sync_p2(background_tasks: BackgroundTasks):
    """
    P2: Create Raw Alert from CS1 (API Output Data) and store in CS2 (Raw Alert)
    
    This endpoint triggers the P2 process:
    - Reads from CS1 indices (threats1, logs1, flows1)
    - Builds raw alert documents
    - Stores in CS2 index (c-ecs-raw-alert)
    """
    fetcher = RawAlertFetcher()
    
    # Start background sync task
    background_tasks.add_task(_p2_sync_task, fetcher)
    
    return {
        "status": "accepted",
        "message": "P2 sync started - creating raw alerts from CS1 data",
        "process": "P2 - Create Raw Alert"
    }


def _p2_sync_task(fetcher):
    """Background task to execute P2 sync"""
    try:
        logger.info("Starting P2 sync task")
        result = fetcher.process_and_store()
        logger.info(f"P2 sync completed: {result}")
    except Exception as e:
        logger.error(f"Error in P2 sync task: {str(e)}", exc_info=True)

