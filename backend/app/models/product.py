"""Product model representing items from e-commerce platforms."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, ForeignKey, Boolean, Numeric, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.shop import Shop
    from app.models.category import Category
    from app.models.price_history import PriceHistory
    from app.models.deal import Deal


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Product scraped from an e-commerce platform.

    Each product is uniquely identified by (external_id, shop_id) pair.
    Tracks current price, original price, and maintains price history.
    """

    __tablename__ = "products"

    # External identifiers
    external_id: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True,
        comment="Product ID from the source shop"
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Product info
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="Product title/name")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)

    # Pricing
    original_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Original/MSRP price before discounts"
    )
    current_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Current price (after discounts)"
    )
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="KRW")

    # Media and links
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    product_url: Mapped[str] = mapped_column(String(2000), nullable=False, comment="Link to product on shop")

    # Categorization
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="Whether product is available")
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time this product was scraped"
    )

    # Additional metadata (specs, attributes, etc.)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON metadata for specs, attributes, raw data"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("external_id", "shop_id", name="uq_product_external_shop"),
        Index(
            "idx_products_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"}
        ),
        Index("idx_products_active_scraped", "is_active", "last_scraped_at"),
    )

    # Relationships
    shop: Mapped["Shop"] = relationship(back_populates="products")
    category: Mapped[Optional["Category"]] = relationship(back_populates="products")
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="PriceHistory.recorded_at.desc()"
    )
    deals: Mapped[list["Deal"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, title='{self.title[:50]}...', shop_id={self.shop_id})>"
