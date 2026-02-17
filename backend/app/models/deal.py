"""Deal model representing good deals detected by the system."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Text, ForeignKey, Boolean, Numeric, DateTime, Integer, Index, text
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.shop import Shop
    from app.models.category import Category
    from app.models.comment import Comment
    from app.models.user_vote import UserVote


class Deal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A good deal detected by the system.

    Deals are created when significant price drops are detected or when
    products meet certain quality/price thresholds. AI scoring helps rank deals.
    """

    __tablename__ = "deals"

    # References
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Pricing
    deal_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Current deal price"
    )
    original_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Original/regular price"
    )
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Discount as percentage (0-100)"
    )
    discount_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Absolute discount amount"
    )

    # Deal metadata
    deal_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="price_drop",
        comment="Type: 'price_drop', 'flash_sale', 'coupon', 'bundle', etc."
    )

    # AI scoring
    ai_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="AI-generated deal quality score (0-100)"
    )
    ai_reasoning: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI explanation for the score"
    )

    # Content (denormalized from product for performance)
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="Deal title")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    deal_url: Mapped[str] = mapped_column(String(2000), nullable=False, comment="Link to deal")

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether deal is currently active"
    )
    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether deal has expired"
    )

    # Time bounds
    starts_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When deal becomes active"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When deal expires"
    )

    # Engagement metrics
    vote_up: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Number of upvotes")
    vote_down: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Number of downvotes")
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Number of views")
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Number of comments")

    # Additional metadata
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON metadata for extra deal info"
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_deals_active_created", "is_active", "created_at"),
        Index(
            "idx_deals_ai_score_active",
            "ai_score",
            postgresql_where=text("is_active = true")
        ),
        Index(
            "idx_deals_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"}
        ),
        Index("idx_deals_expires_at", "expires_at"),
        Index("idx_deals_vote_up_desc", "vote_up", postgresql_using="btree"),
    )

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="deals")
    shop: Mapped["Shop"] = relationship(back_populates="deals")
    category: Mapped[Optional["Category"]] = relationship(back_populates="deals")
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan"
    )
    votes: Mapped[list["UserVote"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Deal(id={self.id}, title='{self.title[:50]}...', deal_price={self.deal_price}, ai_score={self.ai_score})>"
