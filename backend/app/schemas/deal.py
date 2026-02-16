"""Deal Pydantic schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ShopBrief(BaseModel):
    """Brief shop information for deal responses."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    logo_url: Optional[str] = None
    country: str


class CategoryBrief(BaseModel):
    """Brief category information for deal responses."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str


class DealResponse(BaseModel):
    """Standard deal response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    deal_price: Decimal
    original_price: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    ai_score: Optional[Decimal] = None
    ai_reasoning: Optional[str] = None
    deal_type: str
    deal_url: str
    image_url: Optional[str] = None
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    view_count: int
    vote_up: int
    comment_count: int
    shop: ShopBrief
    category: Optional[CategoryBrief] = None


class PriceHistoryItem(BaseModel):
    """Price history data point for deal detail."""
    price: float
    recorded_at: str


class DealDetailResponse(DealResponse):
    """Detailed deal response with additional fields."""

    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    vote_down: int = 0
    price_history: List[PriceHistoryItem] = []


class VoteRequest(BaseModel):
    """Request schema for voting on a deal."""

    vote_type: str  # "up" or "down"
