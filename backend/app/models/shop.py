"""Shop model representing e-commerce platforms."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Integer, Boolean
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.deal import Deal
    from app.models.scraper_job import ScraperJob


class Shop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """E-commerce platform/shop model.

    Represents shopping platforms like Coupang, 11st, Naver Shopping, etc.
    Each shop can have its own scraping configuration and API adapter type.
    """

    __tablename__ = "shops"

    # Basic info
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Korean name (e.g., '쿠팡')")
    name_en: Mapped[str] = mapped_column(String(100), nullable=False, comment="English name (e.g., 'Coupang')")
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="URL-friendly identifier")
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="Shop's base URL")

    # Scraping configuration
    adapter_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="scraper",
        comment="Type of data adapter: 'api', 'scraper', or 'hybrid'"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="Whether scraping is enabled")
    scrape_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        comment="How often to scrape this shop (in minutes)"
    )

    # Localization
    country: Mapped[str] = mapped_column(String(10), nullable=False, default="KR", comment="ISO country code")
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="KRW", comment="ISO currency code")

    # Metadata for adapter-specific config (selectors, API endpoints, etc.)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON metadata for scraper config, selectors, etc."
    )

    # Relationships
    products: Mapped[list["Product"]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    deals: Mapped[list["Deal"]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    scraper_jobs: Mapped[list["ScraperJob"]] = relationship(back_populates="shop", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Shop(id={self.id}, slug='{self.slug}', name='{self.name}')>"
