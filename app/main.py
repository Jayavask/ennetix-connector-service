from fastapi import FastAPI, HTTPException
from typing import List

from .schemas import Threat, ThreatInBulk, IngestResponse


app = FastAPI(title="Ennetix Connector Service", version="0.1.0")

# In-memory storage just for demo / PoC.
# In a real implementation, back this with a database or message queue.
_THREAT_STORE: List[Threat] = []


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/threats/bulk",
    response_model=IngestResponse,
    summary="Ingest a batch of threats from Ennetix",
)
async def ingest_threats_bulk(payload: ThreatInBulk) -> IngestResponse:
    if not payload.threats:
        raise HTTPException(status_code=400, detail="No threats provided")

    _THREAT_STORE.extend(payload.threats)

    return IngestResponse(
        count=len(payload.threats),
        message=f"Ingested {len(payload.threats)} threats",
    )


@app.get("/threats", response_model=List[Threat], summary="List all ingested threats")
async def list_threats() -> List[Threat]:
    # In a real service you would add pagination and filtering here.
    return _THREAT_STORE
