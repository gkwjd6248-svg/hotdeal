"""Comment model for deal discussions."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.deal import Deal


class Comment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A comment on a deal."""

    __tablename__ = "comments"

    deal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True, index=True,
        comment="Parent comment ID for replies"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Comment text content"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Soft delete flag"
    )

    __table_args__ = (
        Index("idx_comments_deal_created", "deal_id", "created_at"),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="comments")
    deal: Mapped["Deal"] = relationship(back_populates="comments")
    replies: Mapped[list["Comment"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    parent: Mapped[Optional["Comment"]] = relationship(
        back_populates="replies",
        remote_side="Comment.id",
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, deal_id={self.deal_id}, user='{self.user_id}')>"
