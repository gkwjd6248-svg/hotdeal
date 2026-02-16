"""Health check schemas."""

from typing import Dict, Optional

from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    """Health check response schema."""

    status: str
    database: str
    redis: Optional[str] = None
    services: Dict[str, str] = {}
