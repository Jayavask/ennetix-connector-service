"""
P1 Router - Pull data using Ennetix API
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional
from pydantic import BaseModel
from app.fetcher.ennetix_api_fetcher import EnnetixAPIFetcher
from app.logging import setup_logging

logger = setup_logging()
router = APIRouter(prefix="/api/v1/p1", tags=["p1"])


class P1Request(BaseModel):
    """Request model for P1 sync operations"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/sync")
async def sync_p1(
    background_tasks: BackgroundTasks,
    request: Optional[P1Request] = None
):
    """
    P1: Pull data from Ennetix API and store as API output data (CS1)
    
    This endpoint triggers the P1 process:
    - Fetches threats from Ennetix API
    - Fetches logs and flows for each alert
    - Stores raw API output data in Cygeniq Elasticsearch (CS1)
    """
    fetcher = EnnetixAPIFetcher()
    
    start_date = request.start_date if request else None
    end_date = request.end_date if request else None
    
    # Start background sync task
    background_tasks.add_task(
        _p1_sync_task,
        fetcher,
        start_date,
        end_date
    )
    
    return {
        "status": "accepted",
        "message": "P1 sync started - pulling data from Ennetix API",
        "process": "P1 - Populate using Ennetix API"
    }


async def _p1_sync_task(fetcher, start_date, end_date):
    """Background task to execute P1 sync"""
    try:
        logger.info("Starting P1 sync task")
        result = await fetcher.fetch_and_store(start_date, end_date)
        logger.info(f"P1 sync completed: {result}")
    except Exception as e:
        logger.error(f"Error in P1 sync task: {str(e)}", exc_info=True)

