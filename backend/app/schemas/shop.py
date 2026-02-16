"""Shop Pydantic schemas for request/response validation."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ShopResponse(BaseModel):
    """Shop response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    name_en: str
    slug: str
    logo_url: Optional[str] = None
    base_url: str
    adapter_type: str
    is_active: bool
    country: str
    currency: str
    deal_count: int = 0  # Computed field
