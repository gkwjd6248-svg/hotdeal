"""User model for authentication and community features."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Boolean, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.user_vote import UserVote
    from app.models.price_alert import PriceAlert


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Application user for community features.

    Supports email/password authentication with bcrypt hashing.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True,
        comment="User email address (unique)"
    )
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        comment="Display name"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="bcrypt hashed password"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Whether user account is active"
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Whether user has admin privileges"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Last login timestamp"
    )

    # Relationships
    comments: Mapped[List["Comment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    votes: Mapped[List["UserVote"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    price_alerts: Mapped[List["PriceAlert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
