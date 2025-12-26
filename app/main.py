"""
App entrypoint for ENNETIX Connector Microservice
"""
import asyncio
from fastapi import FastAPI
from app.config import settings
from app.logging import setup_logging
from app.health import router as health_router
from app.router.group_router import router as group_router
from app.router.p1_router import router as p1_router
from app.router.p2_router import router as p2_router

# Setup logging
logger = setup_logging()

# Initialize FastAPI app
app = FastAPI(
    title="ENNETIX Connector Service",
    description="Microservice to pull Ennetix data to Cygeniq Elasticsearch",
    version="1.0.0"
)

# Register routers
app.include_router(health_router)
app.include_router(group_router)
app.include_router(p1_router)
app.include_router(p2_router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting ENNETIX Connector Service")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down ENNETIX Connector Service")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

