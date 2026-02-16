"""Category model for product classification."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.deal import Deal


class Category(UUIDPrimaryKeyMixin, Base):
    """Product category with hierarchical support.

    Categories can be nested (parent/child relationship) to create
    a category tree (e.g., 'Electronics' > 'PC/Hardware' > 'Graphics Cards').
    """

    __tablename__ = "categories"

    # Basic info
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="Korean category name")
    name_en: Mapped[str] = mapped_column(String(50), nullable=False, comment="English category name")
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="URL-friendly identifier")
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Icon identifier (e.g., 'laptop', 'cpu')")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Display order")

    # Hierarchical support
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent category ID for nested categories"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Self-referential relationship
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        cascade="all, delete-orphan"
    )

    # Related entities
    products: Mapped[list["Product"]] = relationship(back_populates="category")
    deals: Mapped[list["Deal"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, slug='{self.slug}', name='{self.name}')>"
