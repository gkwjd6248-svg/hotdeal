"""Comment Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.schemas.auth import UserBrief


class CommentCreateRequest(BaseModel):
    """Request to create a new comment."""
    content: str = Field(min_length=1, max_length=2000)
    parent_id: Optional[UUID] = None


class CommentUpdateRequest(BaseModel):
    """Request to update an existing comment."""
    content: str = Field(min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    """Single comment response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    user: UserBrief
    parent_id: Optional[UUID] = None
    content: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    replies: List["CommentResponse"] = []
