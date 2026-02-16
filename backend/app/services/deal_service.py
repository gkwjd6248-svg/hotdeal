"""Deal CRUD service for managing deal lifecycle.

This service handles creating, updating, querying, and expiring deals.
It integrates with the PriceAnalyzer to compute AI scores for all deals.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, func, and_, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deal import Deal
from app.models.product import Product
from app.models.price_history import PriceHistory
from app.models.shop import Shop
from app.models.category import Category
from app.services.price_analysis import PriceAnalyzer, DEAL_THRESHOLD

logger = structlog.get_logger(__name__)


class DealService:
    """Service for managing deals.

    Handles deal CRUD operations, AI scoring integration, filtering,
    pagination, and lifecycle management (expiration).
    """

    def __init__(self, db: AsyncSession):
        """Initialize deal service.

        Args:
            db: Async database session
        """
        self.db = db
        self.price_analyzer = PriceAnalyzer(db)
        self.logger = logger.bind(service="deal_service")

    async def get_deals(
        self,
        page: int = 1,
        limit: int = 20,
        category_slug: Optional[str] = None,
        shop_slug: Optional[str] = None,
        sort_by: str = "newest",
        min_discount: Optional[float] = None,
        deal_type: Optional[str] = None,
    ) -> Tuple[List[Deal], int]:
        """Get paginated deals with filters.

        Args:
            page: Page number (1-indexed)
            limit: Results per page
            category_slug: Filter by category
            shop_slug: Filter by shop
            sort_by: Sort method ("newest", "score", "discount", "views")
            min_discount: Minimum discount percentage filter
            deal_type: Filter by deal type

        Returns:
            Tuple of (deals list, total count)
        """
        self.logger.info(
            "fetching_deals",
            page=page,
            limit=limit,
            category=category_slug,
            shop=shop_slug,
            sort=sort_by,
        )

        # Base query - only active deals with eager loading
        query = (
            select(Deal)
            .options(
                selectinload(Deal.shop),
                selectinload(Deal.category),
            )
            .where(Deal.is_active == True)
        )
        count_query = select(func.count(Deal.id)).where(Deal.is_active == True)

        # Apply filters
        if category_slug:
            query = query.join(Deal.category).where(Category.slug == category_slug)
            count_query = count_query.join(Deal.category).where(Category.slug == category_slug)

        if shop_slug:
            query = query.join(Deal.shop).where(Shop.slug == shop_slug)
            count_query = count_query.join(Deal.shop).where(Shop.slug == shop_slug)

        if min_discount is not None:
            query = query.where(Deal.discount_percentage >= min_discount)
            count_query = count_query.where(Deal.discount_percentage >= min_discount)

        if deal_type:
            query = query.where(Deal.deal_type == deal_type)
            count_query = count_query.where(Deal.deal_type == deal_type)

        # Sorting
        sort_map = {
            "newest": Deal.created_at.desc(),
            "score": Deal.ai_score.desc().nullslast(),
            "discount": Deal.discount_percentage.desc().nullslast(),
            "views": Deal.view_count.desc(),
        }
        order = sort_map.get(sort_by, Deal.created_at.desc())
        query = query.order_by(order)

        # Pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        # Execute queries
        result = await self.db.execute(query)
        deals = list(result.scalars().all())

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        self.logger.info(
            "deals_fetched",
            count=len(deals),
            total=total,
            page=page,
        )

        return deals, total

    async def get_top_deals(
        self,
        limit: int = 20,
        category_slug: Optional[str] = None,
    ) -> List[Deal]:
        """Get top AI-scored deals.

        Args:
            limit: Maximum number of deals to return
            category_slug: Optional category filter

        Returns:
            List of top-scored active deals
        """
        query = (
            select(Deal)
            .options(
                selectinload(Deal.shop),
                selectinload(Deal.category),
            )
            .where(and_(
                Deal.is_active == True,
                Deal.ai_score.isnot(None),
            ))
            .order_by(Deal.ai_score.desc())
            .limit(limit)
        )

        if category_slug:
            query = query.join(Deal.category).where(Category.slug == category_slug)

        result = await self.db.execute(query)
        deals = list(result.scalars().all())

        self.logger.info(
            "top_deals_fetched",
            count=len(deals),
            category=category_slug,
        )

        return deals

    async def get_deal_by_id(self, deal_id: UUID) -> Optional[Deal]:
        """Get single deal with relationships loaded.

        Also increments the view count for the deal.

        Args:
            deal_id: Deal UUID

        Returns:
            Deal object or None if not found
        """
        query = (
            select(Deal)
            .options(
                selectinload(Deal.shop),
                selectinload(Deal.category),
                selectinload(Deal.product),
            )
            .where(Deal.id == deal_id)
        )

        result = await self.db.execute(query)
        deal = result.scalar_one_or_none()

        if deal:
            # Increment view count
            deal.view_count += 1
            await self.db.commit()

            self.logger.info(
                "deal_viewed",
                deal_id=str(deal_id),
                view_count=deal.view_count,
            )

        return deal

    async def create_or_update_deal(
        self,
        product_id: UUID,
        shop_id: UUID,
        category_id: Optional[UUID],
        deal_price: Decimal,
        original_price: Optional[Decimal],
        title: str,
        deal_url: str,
        image_url: Optional[str] = None,
        deal_type: str = "price_drop",
        description: Optional[str] = None,
        starts_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[dict] = None,
    ) -> Deal:
        """Create a new deal or update existing one for the same product+shop.

        This method handles upsert logic: if an active deal already exists
        for this product+shop combination, it updates it; otherwise creates new.

        Also computes AI score using the PriceAnalyzer.

        Args:
            product_id: Product UUID
            shop_id: Shop UUID
            category_id: Optional category UUID
            deal_price: Current deal price
            original_price: Original/MSRP price
            title: Deal title (Korean)
            deal_url: URL to the deal
            image_url: Optional product image URL
            deal_type: Type of deal ("price_drop", "flash_sale", etc.)
            description: Optional deal description
            starts_at: Optional deal start time
            expires_at: Optional deal expiration time
            metadata: Optional additional metadata

        Returns:
            Created or updated Deal object
        """
        self.logger.info(
            "creating_or_updating_deal",
            product_id=str(product_id),
            shop_id=str(shop_id),
            deal_price=float(deal_price),
        )

        # Check for existing active deal for this product+shop
        existing = await self.db.execute(
            select(Deal).where(and_(
                Deal.product_id == product_id,
                Deal.shop_id == shop_id,
                Deal.is_active == True,
            ))
        )
        deal = existing.scalar_one_or_none()

        # Get category slug for AI scoring
        category_slug = None
        if category_id:
            cat_result = await self.db.execute(
                select(Category.slug).where(Category.id == category_id)
            )
            category_slug = cat_result.scalar_one_or_none()

        # Compute AI score
        score_result = await self.price_analyzer.compute_deal_score(
            product_id=product_id,
            current_price=deal_price,
            original_price=original_price,
            category_slug=category_slug,
        )

        self.logger.info(
            "ai_score_computed",
            score=float(score_result.score),
            tier=score_result.deal_tier,
            is_deal=score_result.is_deal,
        )

        # Calculate discount percentage and amount
        discount_pct = None
        discount_amt = None
        if original_price and original_price > deal_price:
            discount_pct = round((original_price - deal_price) / original_price * 100, 2)
            discount_amt = original_price - deal_price

        # Set default expiration if not provided (48 hours)
        if not expires_at:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

        if deal:
            # Update existing deal
            self.logger.info("updating_existing_deal", deal_id=str(deal.id))

            deal.deal_price = deal_price
            deal.original_price = original_price
            deal.discount_percentage = discount_pct
            deal.discount_amount = discount_amt
            deal.ai_score = score_result.score
            deal.ai_reasoning = score_result.reasoning
            deal.title = title
            deal.image_url = image_url
            deal.deal_url = deal_url
            deal.description = description
            deal.expires_at = expires_at
            if metadata:
                deal.metadata_ = metadata
        else:
            # Create new deal
            self.logger.info("creating_new_deal")

            deal = Deal(
                product_id=product_id,
                shop_id=shop_id,
                category_id=category_id,
                deal_price=deal_price,
                original_price=original_price,
                discount_percentage=discount_pct,
                discount_amount=discount_amt,
                deal_type=deal_type,
                ai_score=score_result.score,
                ai_reasoning=score_result.reasoning,
                title=title,
                description=description,
                image_url=image_url,
                deal_url=deal_url,
                starts_at=starts_at,
                expires_at=expires_at,
                metadata_=metadata or {},
            )
            self.db.add(deal)

        await self.db.commit()
        await self.db.refresh(deal)

        self.logger.info(
            "deal_saved",
            deal_id=str(deal.id),
            is_new=deal.created_at == deal.updated_at,
            ai_score=float(deal.ai_score) if deal.ai_score else None,
        )

        return deal

    async def expire_stale_deals(self) -> int:
        """Expire deals past their expiration time.

        This should be run periodically (e.g., via scheduler) to mark
        expired deals as inactive.

        Returns:
            Number of deals that were expired
        """
        self.logger.info("expiring_stale_deals")

        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(Deal)
            .where(and_(
                Deal.is_active == True,
                Deal.expires_at.isnot(None),
                Deal.expires_at < now,
            ))
            .values(is_active=False, is_expired=True)
        )
        await self.db.commit()

        expired_count = result.rowcount

        self.logger.info(
            "deals_expired",
            count=expired_count,
        )

        return expired_count

    async def vote_deal(self, deal_id: UUID, vote_type: str) -> Optional[Deal]:
        """Vote on a deal (upvote or downvote).

        Args:
            deal_id: Deal UUID
            vote_type: Either "up" or "down"

        Returns:
            Updated Deal object or None if not found
        """
        if vote_type not in ["up", "down"]:
            raise ValueError("vote_type must be 'up' or 'down'")

        query = select(Deal).where(Deal.id == deal_id)
        result = await self.db.execute(query)
        deal = result.scalar_one_or_none()

        if not deal:
            return None

        if vote_type == "up":
            deal.vote_up += 1
        else:
            deal.vote_down += 1

        await self.db.commit()
        await self.db.refresh(deal)

        self.logger.info(
            "deal_voted",
            deal_id=str(deal_id),
            vote_type=vote_type,
            vote_up=deal.vote_up,
            vote_down=deal.vote_down,
        )

        return deal
