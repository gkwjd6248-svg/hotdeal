"""SQLAlchemy models for DealHawk.

All models are imported here so Alembic can discover them for migrations.
"""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.shop import Shop
from app.models.category import Category
from app.models.product import Product
from app.models.price_history import PriceHistory
from app.models.deal import Deal
from app.models.scraper_job import ScraperJob
from app.models.search_keyword import SearchKeyword
from app.models.user import User
from app.models.comment import Comment
from app.models.user_vote import UserVote
from app.models.price_alert import PriceAlert

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "Shop",
    "Category",
    "Product",
    "PriceHistory",
    "Deal",
    "ScraperJob",
    "SearchKeyword",
    "User",
    "Comment",
    "UserVote",
    "PriceAlert",
]
