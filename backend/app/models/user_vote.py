"""UserVote model for tracking per-user deal votes."""

import uuid

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.deal import Deal


class UserVote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks which user voted on which deal to prevent duplicates."""

    __tablename__ = "user_votes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    vote_type: Mapped[str] = mapped_column(
        String(4), nullable=False,
        comment="'up' or 'down'"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "deal_id", name="uq_user_deal_vote"),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="votes")
    deal: Mapped["Deal"] = relationship(back_populates="votes")

    def __repr__(self) -> str:
        return f"<UserVote(user={self.user_id}, deal={self.deal_id}, type={self.vote_type})>"
