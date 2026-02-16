"""Product service for managing product catalog and price history.

Handles product CRUD operations, upserting scraped products,
and tracking price history for AI analysis.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.price_history import PriceHistory
from app.models.shop import Shop
from app.models.category import Category
from app.scrapers.base import NormalizedProduct

logger = structlog.get_logger(__name__)


class ProductService:
    """Service for managing products and price history.

    Handles product catalog management, upserting products from scrapers,
    recording price history, and querying price trends.
    """

    def __init__(self, db: AsyncSession):
        """Initialize product service.

        Args:
            db: Async database session
        """
        self.db = db
        self.logger = logger.bind(service="product_service")

    async def upsert_product(
        self,
        shop_id: UUID,
        normalized: NormalizedProduct,
        category_id: Optional[UUID] = None,
    ) -> Product:
        """Insert or update a product based on external_id + shop_id.

        This is the main entry point for scrapers to add/update products.
        Uses the unique constraint (external_id, shop_id) to determine
        if this is a new product or an update.

        Also records a price history entry for every upsert.

        Args:
            shop_id: Shop UUID
            normalized: NormalizedProduct from scraper
            category_id: Optional category UUID

        Returns:
            Created or updated Product object
        """
        self.logger.info(
            "upserting_product",
            shop_id=str(shop_id),
            external_id=normalized.external_id,
            title=normalized.title[:50],
        )

        # Check for existing product
        existing = await self.db.execute(
            select(Product).where(and_(
                Product.external_id == normalized.external_id,
                Product.shop_id == shop_id,
            ))
        )
        product = existing.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if product:
            # Update existing product
            self.logger.info("updating_existing_product", product_id=str(product.id))

            product.title = normalized.title
            product.current_price = normalized.current_price
            product.original_price = normalized.original_price
            product.image_url = normalized.image_url
            product.product_url = normalized.product_url
            product.brand = normalized.brand
            product.last_scraped_at = now
            product.is_active = True  # Reactivate if it was inactive

            if category_id:
                product.category_id = category_id

            # Update metadata (merge with existing)
            if normalized.metadata:
                product.metadata_ = {**product.metadata_, **normalized.metadata}

        else:
            # Create new product
            self.logger.info("creating_new_product", external_id=normalized.external_id)

            product = Product(
                external_id=normalized.external_id,
                shop_id=shop_id,
                title=normalized.title,
                original_price=normalized.original_price,
                current_price=normalized.current_price,
                currency=normalized.currency,
                image_url=normalized.image_url,
                product_url=normalized.product_url,
                brand=normalized.brand,
                category_id=category_id,
                last_scraped_at=now,
                is_active=True,
                metadata_=normalized.metadata,
            )
            self.db.add(product)

        # Flush to get product.id for price history
        await self.db.flush()

        # Record price history
        # Only record if price has changed or it's been more than 1 hour
        should_record = await self._should_record_price(
            product.id,
            normalized.current_price,
        )

        if should_record:
            price_record = PriceHistory(
                product_id=product.id,
                price=normalized.current_price,
                currency=normalized.currency,
                source="scraper",
            )
            self.db.add(price_record)
            self.logger.debug(
                "price_history_recorded",
                product_id=str(product.id),
                price=float(normalized.current_price),
            )

        await self.db.commit()
        await self.db.refresh(product)

        self.logger.info(
            "product_upserted",
            product_id=str(product.id),
            external_id=normalized.external_id,
            is_new=product.created_at == product.updated_at,
        )

        return product

    async def _should_record_price(
        self,
        product_id: UUID,
        new_price: Decimal,
        min_interval_hours: int = 1,
    ) -> bool:
        """Determine if a new price history entry should be recorded.

        Only records if:
        1. Price has changed from the last recorded price, OR
        2. It's been more than min_interval_hours since last record

        Args:
            product_id: Product UUID
            new_price: New price to potentially record
            min_interval_hours: Minimum hours between records (default: 1)

        Returns:
            True if should record, False otherwise
        """
        # Get most recent price history entry
        result = await self.db.execute(
            select(PriceHistory)
            .where(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.recorded_at.desc())
            .limit(1)
        )
        last_entry = result.scalar_one_or_none()

        if not last_entry:
            # No history yet, always record
            return True

        # Check if price changed
        if last_entry.price != new_price:
            return True

        # Check if enough time has passed
        time_since_last = datetime.now(timezone.utc) - last_entry.recorded_at
        if time_since_last > timedelta(hours=min_interval_hours):
            return True

        return False

    async def get_product_by_id(self, product_id: UUID) -> Optional[Product]:
        """Get product by ID with relationships loaded.

        Args:
            product_id: Product UUID

        Returns:
            Product object or None if not found
        """
        query = (
            select(Product)
            .options(
                selectinload(Product.shop),
                selectinload(Product.category),
            )
            .where(Product.id == product_id)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_products(
        self,
        page: int = 1,
        limit: int = 50,
        shop_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        is_active: bool = True,
    ) -> Tuple[List[Product], int]:
        """Get paginated products with filters.

        Args:
            page: Page number (1-indexed)
            limit: Results per page
            shop_id: Optional shop filter
            category_id: Optional category filter
            is_active: Filter by active status

        Returns:
            Tuple of (products list, total count)
        """
        query = (
            select(Product)
            .options(
                selectinload(Product.shop),
                selectinload(Product.category),
            )
            .where(Product.is_active == is_active)
        )
        count_q = select(func.count(Product.id)).where(Product.is_active == is_active)

        if shop_id:
            query = query.where(Product.shop_id == shop_id)
            count_q = count_q.where(Product.shop_id == shop_id)

        if category_id:
            query = query.where(Product.category_id == category_id)
            count_q = count_q.where(Product.category_id == category_id)

        # Order by most recently scraped
        query = query.order_by(Product.last_scraped_at.desc().nullslast())

        # Pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        # Execute
        result = await self.db.execute(query)
        products = list(result.scalars().all())

        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        return products, total

    async def get_price_history(
        self,
        product_id: UUID,
        days: int = 30,
    ) -> List[PriceHistory]:
        """Get price history for a product within a time window.

        Args:
            product_id: Product UUID
            days: Number of days to look back (default: 30)

        Returns:
            List of PriceHistory records, ordered chronologically
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(PriceHistory)
            .where(and_(
                PriceHistory.product_id == product_id,
                PriceHistory.recorded_at >= cutoff,
            ))
            .order_by(PriceHistory.recorded_at.asc())
        )

        history = list(result.scalars().all())

        self.logger.info(
            "price_history_fetched",
            product_id=str(product_id),
            days=days,
            count=len(history),
        )

        return history

    async def get_price_statistics(
        self,
        product_id: UUID,
        days: int = 90,
    ) -> Optional[dict]:
        """Get price statistics for a product.

        Computes min, max, average, and current price from price history.

        Args:
            product_id: Product UUID
            days: Number of days to analyze (default: 90)

        Returns:
            Dict with statistics or None if insufficient data
        """
        history = await self.get_price_history(product_id, days)

        if len(history) < 2:
            return None

        prices = [float(h.price) for h in history]

        stats = {
            "product_id": str(product_id),
            "days_analyzed": days,
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices),
            "current_price": prices[-1],  # Most recent
            "data_points": len(prices),
            "first_recorded": history[0].recorded_at.isoformat(),
            "last_recorded": history[-1].recorded_at.isoformat(),
        }

        self.logger.info(
            "price_statistics_computed",
            product_id=str(product_id),
            **{k: v for k, v in stats.items() if k not in ["product_id", "first_recorded", "last_recorded"]},
        )

        return stats

    async def deactivate_stale_products(self, days: int = 30) -> int:
        """Deactivate products that haven't been scraped recently.

        This helps clean up products that are no longer available
        on the shop (e.g., discontinued items).

        Args:
            days: Number of days since last scrape to consider stale

        Returns:
            Number of products deactivated
        """
        self.logger.info("deactivating_stale_products", days=days)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(Product).where(and_(
                Product.is_active == True,
                Product.last_scraped_at < cutoff,
            ))
        )
        stale_products = list(result.scalars().all())

        for product in stale_products:
            product.is_active = False

        await self.db.commit()

        count = len(stale_products)

        self.logger.info(
            "stale_products_deactivated",
            count=count,
        )

        return count
