"""Product Pydantic schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PriceHistoryPoint(BaseModel):
    """Single price history data point."""

    model_config = ConfigDict(from_attributes=True)

    price: Decimal
    recorded_at: datetime


class ProductResponse(BaseModel):
    """Product response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    original_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    currency: str
    image_url: Optional[str] = None
    product_url: str
    brand: Optional[str] = None
    external_id: Optional[str] = None


class ProductDetailResponse(ProductResponse):
    """Detailed product response with additional information."""

    description: Optional[str] = None
    is_active: bool
    last_scraped_at: Optional[datetime] = None
    shop_id: UUID
    category_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
