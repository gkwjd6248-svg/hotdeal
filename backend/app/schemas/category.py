"""Category Pydantic schemas for request/response validation."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    """Category response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    name_en: str
    slug: str
    icon: Optional[str] = None
    sort_order: int
    parent_id: Optional[UUID] = None
    deal_count: int = 0  # Computed field


class CategoryTreeResponse(CategoryResponse):
    """Category response with nested children for tree structure."""

    children: list["CategoryTreeResponse"] = []
