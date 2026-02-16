"""Price alert Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertCreateRequest(BaseModel):
    """Request to create a price alert."""
    product_id: UUID
    target_price: Decimal


class AlertResponse(BaseModel):
    """Price alert response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    target_price: Decimal
    is_active: bool
    is_triggered: bool
    created_at: datetime
