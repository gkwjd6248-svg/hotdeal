"""Search keyword tracking for analytics."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class SearchKeyword(UUIDPrimaryKeyMixin, Base):
    """Tracks user search keywords for analytics and trending topics.

    Records search frequency and last search time to identify
    popular products and trending searches.
    """

    __tablename__ = "search_keywords"

    # Keyword
    keyword: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        index=True,
        nullable=False,
        comment="Search keyword (normalized)"
    )

    # Analytics
    search_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="How many times this keyword was searched"
    )

    # Timestamps
    last_searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Last time this keyword was searched"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="First time this keyword was searched"
    )

    def __repr__(self) -> str:
        return f"<SearchKeyword(id={self.id}, keyword='{self.keyword}', search_count={self.search_count})>"
