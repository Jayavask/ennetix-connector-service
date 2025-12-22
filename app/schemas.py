from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Threat(BaseModel):
    """Represents a single threat item coming from Ennetix.

    Adjust the fields to match the real Ennetix schema.
    """

    id: str = Field(..., description="Unique identifier from Ennetix")
    name: str
    severity: str = Field(..., description="e.g. LOW, MEDIUM, HIGH, CRITICAL")
    source: Optional[str] = Field(default="ennetix")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ThreatInBulk(BaseModel):
    """Wrapper for bulk ingestion.

    This lets us evolve the payload later without breaking clients.
    """

    threats: List[Threat]


class IngestResponse(BaseModel):
    count: int
    message: str
