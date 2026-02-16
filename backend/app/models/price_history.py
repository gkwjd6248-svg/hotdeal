"""Price history tracking for products."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Numeric, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product


class PriceHistory(UUIDPrimaryKeyMixin, Base):
    """Historical price tracking for products.

    Records price changes over time to enable price drop detection,
    price trend analysis, and historical charts.
    """

    __tablename__ = "price_history"

    # Product reference
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Price data
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="Price at this point in time")
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="KRW")

    # Source tracking
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="scraper",
        comment="Source of price data: 'scraper', 'api', 'manual'"
    )

    # Timestamp
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this price was recorded"
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_price_history_product_recorded", "product_id", "recorded_at"),
        Index("idx_price_history_recorded_desc", "recorded_at", postgresql_using="btree"),
    )

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="price_history")

    def __repr__(self) -> str:
        return f"<PriceHistory(id={self.id}, product_id={self.product_id}, price={self.price}, recorded_at={self.recorded_at})>"
