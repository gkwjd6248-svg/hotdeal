"""PriceAlert model for user price notifications."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Numeric, Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.product import Product


class PriceAlert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User's price alert subscription for a product."""

    __tablename__ = "price_alerts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    target_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Alert when price drops to or below this"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Whether alert is still active"
    )
    is_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Whether alert has been triggered"
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="price_alerts")
    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<PriceAlert(user={self.user_id}, product={self.product_id}, target={self.target_price})>"
