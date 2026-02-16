"""Scraper job tracking and monitoring."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, ForeignKey, Integer, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.shop import Shop


class ScraperJob(UUIDPrimaryKeyMixin, Base):
    """Tracks execution of scraping jobs.

    Each scraper run creates a ScraperJob record to track status,
    performance metrics, errors, and results.
    """

    __tablename__ = "scraper_jobs"

    # Shop reference
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Job status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Status: 'pending', 'running', 'completed', 'failed', 'cancelled'"
    )

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When job started executing"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When job finished (success or failure)"
    )
    duration_seconds: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Total execution time in seconds"
    )

    # Metrics
    items_found: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total products found during scrape"
    )
    items_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="New products created"
    )
    items_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Existing products updated"
    )
    deals_detected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of deals detected"
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if job failed"
    )
    error_traceback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full error traceback for debugging"
    )

    # Additional metadata (config used, proxy used, etc.)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON metadata for job config, proxy info, etc."
    )

    # Created timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    shop: Mapped["Shop"] = relationship(back_populates="scraper_jobs")

    def __repr__(self) -> str:
        return f"<ScraperJob(id={self.id}, shop_id={self.shop_id}, status='{self.status}', created_at={self.created_at})>"
