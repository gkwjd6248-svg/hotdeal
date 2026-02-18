"""Scraper orchestration service.

This service connects the scraper adapter layer with the database services.
It handles the end-to-end flow from fetching deals to storing them in the database.
"""

from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
import structlog

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shop import Shop
from app.models.category import Category
from app.scrapers.base import NormalizedDeal, BaseScraperAdapter
from app.scrapers.factory import get_adapter_factory
from app.scrapers.utils.browser_manager import get_browser_manager
from app.services.product_service import ProductService
from app.services.deal_service import DealService
from app.services.price_analysis import PriceAnalyzer

logger = structlog.get_logger(__name__)


class ScraperService:
    """Service for orchestrating scraper adapters and processing results.

    This service acts as the bridge between scraper adapters and database services.
    It handles the complete flow: fetch deals → upsert products → create deals → log results.
    """

    def __init__(self, db: AsyncSession):
        """Initialize scraper service.

        Args:
            db: Async database session
        """
        self.db = db
        self.product_service = ProductService(db)
        self.deal_service = DealService(db)
        self.price_analyzer = PriceAnalyzer(db)
        self.adapter_factory = get_adapter_factory()
        self.logger = logger.bind(service="scraper_service")

    async def run_adapter(
        self,
        shop_slug: str,
        category: Optional[str] = None,
    ) -> Dict[str, int]:
        """Run a single scraper adapter and process all results.

        This is the main entry point for executing a scraping job.

        Args:
            shop_slug: Shop identifier (e.g., "naver", "coupang")
            category: Optional category filter

        Returns:
            Dict with processing statistics:
                - deals_fetched: Number of deals fetched from adapter
                - products_created: Number of new products created
                - products_updated: Number of existing products updated
                - deals_created: Number of new deals created
                - deals_updated: Number of existing deals updated
                - errors: Number of errors encountered

        Raises:
            ValueError: If shop not found or adapter not registered
        """
        self.logger.info(
            "running_adapter",
            shop_slug=shop_slug,
            category=category,
        )

        # Fetch shop from database
        shop = await self._get_shop(shop_slug)
        if not shop:
            raise ValueError(f"Shop not found: {shop_slug}")

        if not shop.is_active:
            self.logger.warning("shop_inactive", shop_slug=shop_slug)
            raise ValueError(f"Shop is inactive: {shop_slug}")

        # Create adapter instance
        adapter = self.adapter_factory.create_adapter(shop_slug)
        if not adapter:
            raise ValueError(f"No adapter registered for shop: {shop_slug}")

        # Inject browser context for scraper-based adapters
        if isinstance(adapter, BaseScraperAdapter):
            browser_mgr = get_browser_manager()
            adapter.browser_context = await browser_mgr.get_context(shop_slug)

        # Fetch deals from adapter
        try:
            deals = await adapter.fetch_deals(category=category)
            self.logger.info(
                "deals_fetched",
                shop_slug=shop_slug,
                count=len(deals),
                category=category,
            )
        except Exception as e:
            self.logger.error(
                "adapter_fetch_failed",
                shop_slug=shop_slug,
                error=str(e),
                exc_info=True,
            )
            raise

        # Process the deals
        stats = await self.process_deals(deals, shop_slug)

        self.logger.info(
            "adapter_run_complete",
            shop_slug=shop_slug,
            **stats,
        )

        return stats

    async def process_deals(
        self,
        deals: List[NormalizedDeal],
        shop_slug: str,
    ) -> Dict[str, int]:
        """Process a list of normalized deals into the database.

        For each deal:
        1. Upsert the product
        2. Record price history (done by ProductService)
        3. Compute AI score
        4. Create or update deal

        Args:
            deals: List of NormalizedDeal from adapter
            shop_slug: Shop identifier

        Returns:
            Processing statistics dict
        """
        self.logger.info(
            "processing_deals",
            shop_slug=shop_slug,
            count=len(deals),
        )

        stats = {
            "deals_fetched": len(deals),
            "products_created": 0,
            "products_updated": 0,
            "deals_created": 0,
            "deals_updated": 0,
            "deals_skipped": 0,  # Products saved but score < DEAL_THRESHOLD
            "deals_deactivated": 0,  # Existing deals dropped below threshold
            "errors": 0,
        }

        # Get shop
        shop = await self._get_shop(shop_slug)
        if not shop:
            self.logger.error("shop_not_found", shop_slug=shop_slug)
            return stats

        for deal in deals:
            try:
                # Auto-categorize product if category_hint is provided
                category_id = None
                if deal.product.category_hint:
                    category_id = await self._get_or_match_category(deal.product.category_hint)

                # Upsert product
                product_before_count = await self._count_products(shop.id)
                product = await self.product_service.upsert_product(
                    shop_id=shop.id,
                    normalized=deal.product,
                    category_id=category_id,
                )
                product_after_count = await self._count_products(shop.id)

                # Track if product was created or updated
                if product_after_count > product_before_count:
                    stats["products_created"] += 1
                else:
                    stats["products_updated"] += 1

                # Create or update deal (returns None when score < DEAL_THRESHOLD)
                deal_before_count = await self._count_active_deals(product.id, shop.id)

                saved_deal = await self.deal_service.create_or_update_deal(
                    product_id=product.id,
                    shop_id=shop.id,
                    category_id=product.category_id,
                    deal_price=deal.deal_price,
                    original_price=deal.original_price,
                    title=deal.title,
                    deal_url=deal.deal_url,
                    image_url=deal.image_url or deal.product.image_url,
                    deal_type=deal.deal_type,
                    description=deal.description,
                    starts_at=deal.starts_at,
                    expires_at=deal.expires_at,
                    metadata=deal.metadata,
                )

                if saved_deal is None:
                    # Score was below DEAL_THRESHOLD — product/price history still saved
                    deal_after_count = await self._count_active_deals(product.id, shop.id)
                    if deal_after_count < deal_before_count:
                        # An existing deal was deactivated because score fell below threshold
                        stats["deals_deactivated"] += 1
                    else:
                        # New product didn't qualify; no deal record written
                        stats["deals_skipped"] += 1
                    self.logger.debug(
                        "deal_below_threshold",
                        product_id=str(product.id),
                        deal_title=deal.title[:50],
                    )
                else:
                    deal_after_count = await self._count_active_deals(product.id, shop.id)
                    if deal_after_count > deal_before_count:
                        stats["deals_created"] += 1
                    else:
                        stats["deals_updated"] += 1
                    self.logger.debug(
                        "deal_processed",
                        product_id=str(product.id),
                        deal_title=deal.title[:50],
                    )

            except Exception as e:
                stats["errors"] += 1
                self.logger.error(
                    "deal_processing_failed",
                    deal_title=deal.title[:50] if deal.title else "unknown",
                    error=str(e),
                    exc_info=True,
                )
                # Continue processing other deals

        self.logger.info(
            "deals_processed",
            shop_slug=shop_slug,
            **stats,
        )

        return stats

    async def _get_shop(self, shop_slug: str) -> Optional[Shop]:
        """Get shop by slug.

        Args:
            shop_slug: Shop identifier

        Returns:
            Shop object or None
        """
        result = await self.db.execute(
            select(Shop).where(Shop.slug == shop_slug)
        )
        return result.scalar_one_or_none()

    async def _get_or_match_category(self, category_hint: str) -> Optional[UUID]:
        """Get or match a category ID from a category hint.

        Args:
            category_hint: Category hint string (e.g., "pc-hardware", "전자제품")

        Returns:
            Category UUID or None
        """
        # Try exact slug match first
        result = await self.db.execute(
            select(Category.id).where(Category.slug == category_hint)
        )
        category_id = result.scalar_one_or_none()

        if category_id:
            return category_id

        # Try fuzzy name match (Korean or English)
        # This is a simple implementation - could be enhanced with similarity search
        result = await self.db.execute(
            select(Category.id).where(
                (Category.name.ilike(f"%{category_hint}%")) |
                (Category.name_en.ilike(f"%{category_hint}%"))
            ).limit(1)
        )
        category_id = result.scalar_one_or_none()

        return category_id

    async def _count_products(self, shop_id: UUID) -> int:
        """Count total products for a shop.

        Args:
            shop_id: Shop UUID

        Returns:
            Product count
        """
        from sqlalchemy import func, select
        from app.models.product import Product

        result = await self.db.execute(
            select(func.count(Product.id)).where(Product.shop_id == shop_id)
        )
        return result.scalar() or 0

    async def _count_active_deals(self, product_id: UUID, shop_id: UUID) -> int:
        """Count active deals for a product+shop.

        Args:
            product_id: Product UUID
            shop_id: Shop UUID

        Returns:
            Active deal count
        """
        from sqlalchemy import func, select, and_
        from app.models.deal import Deal

        result = await self.db.execute(
            select(func.count(Deal.id)).where(and_(
                Deal.product_id == product_id,
                Deal.shop_id == shop_id,
                Deal.is_active == True,
            ))
        )
        return result.scalar() or 0
