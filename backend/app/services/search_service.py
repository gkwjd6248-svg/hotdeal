"""Search service for full-text deal search and trending keywords.

Uses PostgreSQL's pg_trgm extension for fuzzy Korean text search
with trigram similarity matching.
"""

from datetime import datetime, timezone
from typing import List, Tuple, Optional

import structlog
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deal import Deal
from app.models.search_keyword import SearchKeyword
from app.models.shop import Shop
from app.models.category import Category

logger = structlog.get_logger(__name__)


class SearchService:
    """Service for searching deals and tracking search analytics.

    Provides full-text search with fuzzy matching using PostgreSQL's
    trigram indexes, and tracks popular search keywords for analytics.
    """

    def __init__(self, db: AsyncSession):
        """Initialize search service.

        Args:
            db: Async database session
        """
        self.db = db
        self.logger = logger.bind(service="search_service")

    async def search_deals(
        self,
        query: str,
        page: int = 1,
        limit: int = 20,
        category_slug: Optional[str] = None,
        shop_slug: Optional[str] = None,
        sort_by: str = "relevance",
    ) -> Tuple[List[Deal], int]:
        """Full-text search deals using pg_trgm similarity.

        Searches deal titles using case-insensitive ILIKE pattern matching.
        The trigram indexes enable fast fuzzy matching for Korean text.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            limit: Results per page
            category_slug: Optional category filter
            shop_slug: Optional shop filter
            sort_by: Sort method ("relevance", "score", "newest")

        Returns:
            Tuple of (matching deals list, total count)
        """
        self.logger.info(
            "searching_deals",
            query=query,
            page=page,
            limit=limit,
            category=category_slug,
            shop=shop_slug,
        )

        # Normalize query for pattern matching
        normalized_query = query.strip()
        if not normalized_query:
            self.logger.warning("empty_search_query")
            return [], 0

        # Build search query with trigram similarity
        search_query = (
            select(Deal)
            .options(
                selectinload(Deal.shop),
                selectinload(Deal.category),
            )
            .where(and_(
                Deal.is_active == True,
                Deal.title.ilike(f"%{normalized_query}%"),
            ))
        )

        # Count query
        count_q = select(func.count(Deal.id)).where(and_(
            Deal.is_active == True,
            Deal.title.ilike(f"%{normalized_query}%"),
        ))

        # Apply filters
        if category_slug:
            search_query = search_query.join(Category).where(Category.slug == category_slug)
            count_q = count_q.join(Category).where(Category.slug == category_slug)

        if shop_slug:
            search_query = search_query.join(Deal.shop).where(Shop.slug == shop_slug)
            count_q = count_q.join(Deal.shop).where(Shop.slug == shop_slug)

        # Sorting
        # Note: For true trigram similarity ranking, you would use:
        # .order_by(func.similarity(Deal.title, normalized_query).desc())
        # But this requires similarity() function which needs pg_trgm enabled
        # For now, we'll sort by AI score as a proxy for relevance
        if sort_by == "relevance":
            search_query = search_query.order_by(Deal.ai_score.desc().nullslast())
        elif sort_by == "score":
            search_query = search_query.order_by(Deal.ai_score.desc().nullslast())
        elif sort_by == "newest":
            search_query = search_query.order_by(Deal.created_at.desc())
        else:
            search_query = search_query.order_by(Deal.ai_score.desc().nullslast())

        # Pagination
        offset = (page - 1) * limit
        search_query = search_query.offset(offset).limit(limit)

        # Execute queries
        result = await self.db.execute(search_query)
        deals = list(result.scalars().all())

        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        self.logger.info(
            "search_completed",
            query=query,
            results=len(deals),
            total=total,
            page=page,
        )

        # Track keyword asynchronously (don't block search response)
        await self._track_keyword(normalized_query)

        return deals, total

    async def search_deals_advanced(
        self,
        query: str,
        page: int = 1,
        limit: int = 20,
        min_score: Optional[float] = None,
        max_price: Optional[float] = None,
        category_slug: Optional[str] = None,
        shop_slug: Optional[str] = None,
    ) -> Tuple[List[Deal], int]:
        """Advanced search with additional filters.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            limit: Results per page
            min_score: Minimum AI score filter
            max_price: Maximum price filter
            category_slug: Optional category filter
            shop_slug: Optional shop filter

        Returns:
            Tuple of (matching deals list, total count)
        """
        self.logger.info(
            "advanced_search",
            query=query,
            min_score=min_score,
            max_price=max_price,
        )

        normalized_query = query.strip()
        if not normalized_query:
            return [], 0

        # Build search query
        search_query = (
            select(Deal)
            .options(
                selectinload(Deal.shop),
                selectinload(Deal.category),
            )
            .where(and_(
                Deal.is_active == True,
                Deal.title.ilike(f"%{normalized_query}%"),
            ))
        )

        count_q = select(func.count(Deal.id)).where(and_(
            Deal.is_active == True,
            Deal.title.ilike(f"%{normalized_query}%"),
        ))

        # Apply advanced filters
        if min_score is not None:
            search_query = search_query.where(Deal.ai_score >= min_score)
            count_q = count_q.where(Deal.ai_score >= min_score)

        if max_price is not None:
            search_query = search_query.where(Deal.deal_price <= max_price)
            count_q = count_q.where(Deal.deal_price <= max_price)

        if category_slug:
            search_query = search_query.join(Category).where(Category.slug == category_slug)
            count_q = count_q.join(Category).where(Category.slug == category_slug)

        if shop_slug:
            search_query = search_query.join(Deal.shop).where(Shop.slug == shop_slug)
            count_q = count_q.join(Deal.shop).where(Shop.slug == shop_slug)

        # Sort by AI score
        search_query = search_query.order_by(Deal.ai_score.desc().nullslast())

        # Pagination
        offset = (page - 1) * limit
        search_query = search_query.offset(offset).limit(limit)

        # Execute
        result = await self.db.execute(search_query)
        deals = list(result.scalars().all())

        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        # Track keyword
        await self._track_keyword(normalized_query)

        return deals, total

    async def get_trending_keywords(self, limit: int = 10) -> List[dict]:
        """Get trending search keywords.

        Returns the most frequently searched keywords, useful for
        displaying popular searches or trending topics.

        Args:
            limit: Maximum number of keywords to return

        Returns:
            List of dicts with 'keyword' and 'count' keys
        """
        self.logger.info("fetching_trending_keywords", limit=limit)

        result = await self.db.execute(
            select(SearchKeyword)
            .order_by(SearchKeyword.search_count.desc())
            .limit(limit)
        )
        keywords = result.scalars().all()

        trending = [
            {"keyword": k.keyword, "count": k.search_count}
            for k in keywords
        ]

        self.logger.info(
            "trending_keywords_fetched",
            count=len(trending),
        )

        return trending

    async def get_recent_keywords(self, limit: int = 10) -> List[dict]:
        """Get recently searched keywords.

        Args:
            limit: Maximum number of keywords to return

        Returns:
            List of dicts with 'keyword' and 'last_searched_at' keys
        """
        result = await self.db.execute(
            select(SearchKeyword)
            .order_by(SearchKeyword.last_searched_at.desc())
            .limit(limit)
        )
        keywords = result.scalars().all()

        recent = [
            {
                "keyword": k.keyword,
                "last_searched_at": k.last_searched_at.isoformat(),
                "count": k.search_count,
            }
            for k in keywords
        ]

        return recent

    async def _track_keyword(self, keyword: str) -> None:
        """Track a search keyword for analytics.

        Creates or updates a SearchKeyword record to track search frequency.
        Filters out very short queries (< 2 chars).

        Args:
            keyword: Search keyword to track
        """
        normalized = keyword.strip().lower()

        # Filter out very short queries
        if not normalized or len(normalized) < 2:
            return

        try:
            # Check if keyword exists
            existing = await self.db.execute(
                select(SearchKeyword).where(SearchKeyword.keyword == normalized)
            )
            kw = existing.scalar_one_or_none()

            if kw:
                # Update existing
                kw.search_count += 1
                kw.last_searched_at = datetime.now(timezone.utc)
                self.logger.debug(
                    "keyword_updated",
                    keyword=normalized,
                    count=kw.search_count,
                )
            else:
                # Create new
                kw = SearchKeyword(
                    keyword=normalized,
                    search_count=1,
                )
                self.db.add(kw)
                self.logger.debug(
                    "keyword_created",
                    keyword=normalized,
                )

            await self.db.commit()

        except Exception as e:
            # Don't let keyword tracking errors break search
            self.logger.error(
                "keyword_tracking_failed",
                keyword=normalized,
                error=str(e),
            )
            await self.db.rollback()
