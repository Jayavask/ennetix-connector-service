"""
/health endpoint
"""
from fastapi import APIRouter, status
from typing import Dict
from app.clients.ennetix_es import ennetix_client
from app.clients.cygeniq_es import CygeniqESClient
from app.logging import setup_logging

logger = setup_logging()
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint
    
    Returns:
        Health status of the service
    """
    return {
        "status": "healthy",
        "service": "ennetix-connector-service"
    }


@router.get("/health/ready")
async def readiness_check() -> Dict[str, any]:
    """
    Readiness check endpoint - verifies connections to Elasticsearch clusters
    
    Returns:
        Readiness status with connection details
    """
    status_code = status.HTTP_200_OK
    checks = {
        "ennetix_es": False,
        "cygeniq_es": False,
    }
    
    # Check Ennetix ES connection
    try:
        await ennetix_client.connect()
        if ennetix_client.client:
            await ennetix_client.client.ping()
            checks["ennetix_es"] = True
    except Exception as e:
        logger.error(f"Ennetix ES health check failed: {str(e)}")
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Check Cygeniq ES connection
    try:
        cygeniq_client = CygeniqESClient()
        await cygeniq_client.connect()
        if cygeniq_client.client:
            await cygeniq_client.client.ping()
            checks["cygeniq_es"] = True
        await cygeniq_client.disconnect()
    except Exception as e:
        logger.error(f"Cygeniq ES health check failed: {str(e)}")
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    all_healthy = all(checks.values())
    
    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks
    }


@router.get("/health/live")
async def liveness_check() -> Dict[str, str]:
    """
    Liveness check endpoint
    
    Returns:
        Liveness status
    """
    return {
        "status": "alive",
        "service": "ennetix-connector-service"
    }

