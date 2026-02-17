"""AI-powered price analysis and deal scoring engine.

This module implements the core value proposition of DealHawk: analyzing
price history to automatically detect and score good deals. The PriceAnalyzer
computes a multi-component AI score (0-100) based on historical price trends,
statistical anomalies, and discount depth.

When price history is LIMITED (< 5 records), an alternative lightweight scoring
path is used that extracts signal from: the listed discount rate, deal keywords
in the product title, the price relative to the category median, deal freshness,
and the shop's reputation tier.  When history IS sufficient (>= 5 records) the
original history-based algorithm runs unchanged.
"""

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_history import PriceHistory
from app.models.deal import Deal

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Deal tier thresholds
# ---------------------------------------------------------------------------
DEAL_THRESHOLD = Decimal("35.0")       # Minimum score to qualify as a deal
HOT_DEAL_THRESHOLD = Decimal("70.0")   # Hot deal threshold
SUPER_DEAL_THRESHOLD = Decimal("85.0") # Super deal / featured threshold

# Category-specific thresholds (some categories have different deal definitions)
CATEGORY_THRESHOLDS = {
    "pc-hardware": Decimal("30.0"),     # PC parts often have smaller margins
    "games-software": Decimal("40.0"),  # Games have steeper sales
    "gift-cards": Decimal("20.0"),      # Gift cards rarely discount deeply
    "electronics-tv": Decimal("35.0"),
    "laptop-mobile": Decimal("35.0"),
    "living-food": Decimal("25.0"),     # Food/grocery has frequent but smaller sales
}

# ---------------------------------------------------------------------------
# Statistical analysis parameters (used in the full history path)
# ---------------------------------------------------------------------------
MIN_HISTORY_FOR_FULL_SCORING = 5   # Records needed to use the full algorithm
MIN_HISTORY_FOR_STATS = 3          # Minimum points for any statistical analysis
HISTORY_WINDOW_DAYS = 90           # Look back 90 days for historical average
RECENT_WINDOW_DAYS = 7             # Look back 7 days for recent average

# ---------------------------------------------------------------------------
# Korean deal keywords used in the lightweight scoring path
# ---------------------------------------------------------------------------
# Maps keyword pattern -> bonus points (cumulative, capped later)
DEAL_KEYWORDS: dict[str, float] = {
    # High-signal keywords (very explicit deal language)
    "초특가": 8.0,
    "반값": 8.0,
    "최저가": 7.0,
    "역대최저": 7.0,
    "최저": 5.0,
    "땡처리": 6.0,
    "한정특가": 6.0,
    "특가": 5.0,
    "슈퍼특가": 8.0,
    "핫딜": 6.0,
    "타임특가": 6.0,
    "신년특가": 5.0,
    "오늘만특가": 7.0,
    "오늘도특가": 5.0,
    # Medium-signal keywords
    "할인": 4.0,
    "세일": 4.0,
    "대폭할인": 6.0,
    "한시적": 3.0,
    "이벤트": 3.0,
    "혜택": 2.0,
    # Low-signal keywords
    "단독": 2.0,
    "한정": 2.0,
    "추천": 1.0,
}

# Shop reliability tiers: slug -> bonus points (out of 10)
SHOP_RELIABILITY: dict[str, float] = {
    "naver": 7.0,    # Naver Shopping – aggregator with large seller base
    "coupang": 9.0,  # Coupang – highly trusted Korean mega-mall
    "11st": 8.0,     # 11번가 – established Korean platform
    "steam": 8.0,    # Steam – authoritative for games pricing
    "gmarket": 7.0,
    "auction": 7.0,
    "ssg": 8.0,
    "lotteon": 7.0,
    "interpark": 7.0,
    "musinsa": 7.0,
    "ssf": 6.0,
    "himart": 8.0,
    "amazon": 8.0,
    "aliexpress": 5.0,
    "ebay": 6.0,
}


@dataclass
class DealScore:
    """Result of AI deal scoring analysis.

    Attributes:
        score: Overall deal quality score (0-100)
        is_deal: Whether this qualifies as a deal based on threshold
        deal_tier: Classification tier ("none", "deal", "hot_deal", "super_deal")
        reasoning: Human-readable Korean explanation of the score
        components: Breakdown of individual scoring components
    """

    score: Decimal
    is_deal: bool
    deal_tier: str
    reasoning: str
    components: dict


class PriceAnalyzer:
    """AI-powered price analysis engine.

    Analyzes price history to compute deal quality scores and detect
    significant price drops.

    Full history path (>= 5 price records):
        - Component A (0-30): Discount from historical average
        - Component B (0-20): Sudden drop from recent average
        - Component C (0-25): Proximity to all-time low
        - Component D (0-15): Listed discount percentage
        - Component E (0-10): Statistical anomaly bonus

    Lightweight path (< 5 price records):
        - Component F (0-40): Listed discount rate
        - Component G (0-20): Korean deal keyword boost
        - Component H (0-20): Price relative to category median
        - Component I (0-10): Freshness bonus
        - Component J (0-10): Shop reliability bonus

    Total score ranges from 0-100, with higher scores indicating better deals.
    """

    def __init__(self, db: AsyncSession):
        """Initialize price analyzer.

        Args:
            db: Async database session
        """
        self.db = db
        self.logger = logger.bind(service="price_analyzer")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compute_deal_score(
        self,
        product_id: UUID,
        current_price: Decimal,
        original_price: Optional[Decimal] = None,
        category_slug: Optional[str] = None,
        title: Optional[str] = None,
        shop_slug: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> DealScore:
        """Compute AI deal score (0-100) based on price history analysis.

        Automatically selects between the full history-based algorithm (when
        >= 5 price records exist) and the lightweight signal-based algorithm
        (when fewer records are available).

        Args:
            product_id: UUID of the product to analyze
            current_price: Current price to evaluate
            original_price: Optional original/MSRP price (for listed discount)
            category_slug: Optional category slug for category-specific logic
            title: Optional product title for keyword analysis
            shop_slug: Optional shop slug for reliability scoring
            created_at: Optional deal creation time for freshness scoring

        Returns:
            DealScore object with score, tier, reasoning, and component breakdown
        """
        self.logger.info(
            "computing_deal_score",
            product_id=str(product_id),
            current_price=float(current_price),
            category=category_slug,
        )

        # 1. Fetch price history
        history = await self._get_price_history(product_id, days=HISTORY_WINDOW_DAYS)

        # 2. Route to the appropriate scoring path
        if len(history) >= MIN_HISTORY_FOR_FULL_SCORING:
            return await self._score_with_full_history(
                product_id=product_id,
                current_price=current_price,
                original_price=original_price,
                category_slug=category_slug,
                title=title,
                shop_slug=shop_slug,
                created_at=created_at,
                history=history,
            )
        else:
            return await self._score_with_limited_history(
                product_id=product_id,
                current_price=current_price,
                original_price=original_price,
                category_slug=category_slug,
                title=title,
                shop_slug=shop_slug,
                created_at=created_at,
                history=history,
            )

    # ------------------------------------------------------------------
    # Scoring path 1: Full history (>= 5 records) — original algorithm
    # ------------------------------------------------------------------

    async def _score_with_full_history(
        self,
        product_id: UUID,
        current_price: Decimal,
        original_price: Optional[Decimal],
        category_slug: Optional[str],
        title: Optional[str],
        shop_slug: Optional[str],
        created_at: Optional[datetime],
        history: list,
    ) -> DealScore:
        """Score a deal using full price history analysis.

        Uses historical averages, all-time lows, and statistical outlier
        detection.  This is the high-confidence scoring path.

        Score Components:
            A. Discount from historical average (0-30 points)
            B. Sudden drop from recent average (0-20 points)
            C. All-time low proximity (0-25 points)
            D. Listed discount percentage (0-15 points)
            E. Statistical anomaly bonus (0-10 points)
        """
        prices = [float(h.price) for h in history]
        avg_price = Decimal(str(statistics.mean(prices)))
        min_price = Decimal(str(min(prices)))
        max_price = Decimal(str(max(prices)))
        std_dev = (
            Decimal(str(statistics.stdev(prices))) if len(prices) > 1 else Decimal("0")
        )
        median_price = Decimal(str(statistics.median(prices)))  # noqa: F841

        # Recent average (last 7 days)
        now = datetime.now(timezone.utc)
        recent = [
            h for h in history
            if h.recorded_at > now - timedelta(days=RECENT_WINDOW_DAYS)
        ]
        recent_avg = (
            Decimal(str(statistics.mean([float(h.price) for h in recent])))
            if recent
            else avg_price
        )

        self.logger.debug(
            "full_history_stats",
            avg=float(avg_price),
            min=float(min_price),
            max=float(max_price),
            std_dev=float(std_dev),
            recent_avg=float(recent_avg),
            history_count=len(history),
        )

        # Component A: Discount from historical average (0-30)
        if avg_price > 0:
            pct_below_avg = float((avg_price - current_price) / avg_price * 100)
        else:
            pct_below_avg = 0.0
        score_a = min(30.0, max(0.0, pct_below_avg * 1.5))

        # Component B: Recent price drop (0-20)
        if recent_avg > 0:
            pct_below_recent = float(
                (recent_avg - current_price) / recent_avg * 100
            )
        else:
            pct_below_recent = 0.0
        score_b = min(20.0, max(0.0, pct_below_recent * 2.0))

        # Component C: All-time low proximity (0-25)
        if max_price > min_price:
            position = float((max_price - current_price) / (max_price - min_price))
            score_c = position * 25.0
        else:
            score_c = 12.5  # Neutral if no price range

        # Component D: Listed discount (0-15)
        listed_discount = 0.0
        if original_price and original_price > current_price:
            listed_discount = float(
                (original_price - current_price) / original_price * 100
            )
        score_d = min(15.0, listed_discount * 0.3)

        # Component E: Statistical anomaly (0-10)
        if std_dev > 0:
            z_score = float((avg_price - current_price) / std_dev)
            score_e = min(10.0, max(0.0, (z_score - 1.0) * 5.0))
        else:
            score_e = 0.0

        total = Decimal(
            str(round(min(100.0, max(0.0, score_a + score_b + score_c + score_d + score_e)), 2))
        )

        self.logger.debug(
            "full_history_score_components",
            total=float(total),
            vs_avg=score_a,
            vs_recent=score_b,
            atl_proximity=score_c,
            listed_disc=score_d,
            anomaly=score_e,
        )

        threshold = CATEGORY_THRESHOLDS.get(category_slug, DEAL_THRESHOLD)
        tier = self._classify_tier(total, threshold)
        is_deal = tier != "none"

        reasoning = self._generate_reasoning_full(
            total=total,
            pct_below_avg=pct_below_avg,
            pct_below_recent=pct_below_recent,
            is_all_time_low=(current_price <= min_price),
            listed_discount=listed_discount,
            tier=tier,
            history_count=len(history),
        )

        self.logger.info(
            "deal_score_computed",
            product_id=str(product_id),
            score=float(total),
            tier=tier,
            path="full_history",
        )

        return DealScore(
            score=total,
            is_deal=is_deal,
            deal_tier=tier,
            reasoning=reasoning,
            components={
                "vs_average": round(score_a, 2),
                "vs_recent": round(score_b, 2),
                "all_time_low": round(score_c, 2),
                "listed_discount": round(score_d, 2),
                "anomaly_bonus": round(score_e, 2),
                "scoring_path": "full_history",
                "history_points": len(history),
            },
        )

    # ------------------------------------------------------------------
    # Scoring path 2: Limited history (< 5 records) — lightweight scoring
    # ------------------------------------------------------------------

    async def _score_with_limited_history(
        self,
        product_id: UUID,
        current_price: Decimal,
        original_price: Optional[Decimal],
        category_slug: Optional[str],
        title: Optional[str],
        shop_slug: Optional[str],
        created_at: Optional[datetime],
        history: list,
    ) -> DealScore:
        """Score a deal when price history is limited (< 5 records).

        Extracts deal quality signal from:
            F. Listed discount rate (0-40 points)  — most reliable signal
            G. Korean deal keywords in title (0-20 points)
            H. Price relative to category median (0-20 points)
            I. Freshness bonus (0-10 points)
            J. Shop reliability bonus (0-10 points)

        Args:
            product_id: Product UUID being scored
            current_price: Current deal price
            original_price: Optional MSRP / original price
            category_slug: Category slug for threshold and category comparisons
            title: Product/deal title for keyword analysis
            shop_slug: Shop slug for reliability scoring
            created_at: When the deal was created (for freshness)
            history: Existing (possibly empty) price history records

        Returns:
            DealScore for this deal
        """
        self.logger.warning(
            "limited_history_scoring",
            product_id=str(product_id),
            history_count=len(history),
        )

        # ------------------------------------------------------------------
        # Component F: Listed discount rate (0-40 points)
        # ------------------------------------------------------------------
        listed_discount_pct = 0.0
        if original_price and original_price > 0 and current_price < original_price:
            listed_discount_pct = float(
                (original_price - current_price) / original_price * 100
            )

        score_f = self._score_listed_discount_limited(listed_discount_pct)

        # ------------------------------------------------------------------
        # Component G: Korean deal keyword analysis (0-20 points)
        # ------------------------------------------------------------------
        keyword_hits: list[str] = []
        score_g = 0.0
        if title:
            score_g, keyword_hits = self._score_title_keywords(title)

        # ------------------------------------------------------------------
        # Component H: Price relative to category median (0-20 points)
        # ------------------------------------------------------------------
        score_h = 0.0
        pct_below_category = 0.0
        if category_slug:
            score_h, pct_below_category = await self._score_category_relative_price(
                current_price=current_price,
                category_slug=category_slug,
                exclude_product_id=product_id,
            )

        # ------------------------------------------------------------------
        # Component I: Freshness bonus (0-10 points)
        # ------------------------------------------------------------------
        score_i = self._score_freshness(created_at)

        # ------------------------------------------------------------------
        # Component J: Shop reliability bonus (0-10 points)
        # ------------------------------------------------------------------
        score_j = self._score_shop_reliability(shop_slug)

        total_raw = score_f + score_g + score_h + score_i + score_j
        total = Decimal(str(round(min(100.0, max(0.0, total_raw)), 2)))

        self.logger.debug(
            "limited_history_score_components",
            total=float(total),
            listed_discount=score_f,
            keyword_boost=score_g,
            category_relative=score_h,
            freshness=score_i,
            shop_reliability=score_j,
            keywords_found=keyword_hits,
        )

        threshold = CATEGORY_THRESHOLDS.get(category_slug, DEAL_THRESHOLD)
        tier = self._classify_tier(total, threshold)
        is_deal = tier != "none"

        reasoning = self._generate_reasoning_limited(
            total=total,
            listed_discount_pct=listed_discount_pct,
            keyword_hits=keyword_hits,
            pct_below_category=pct_below_category,
            score_f=score_f,
            score_g=score_g,
            score_h=score_h,
            score_i=score_i,
            score_j=score_j,
            tier=tier,
        )

        self.logger.info(
            "deal_score_computed",
            product_id=str(product_id),
            score=float(total),
            tier=tier,
            path="limited_history",
        )

        return DealScore(
            score=total,
            is_deal=is_deal,
            deal_tier=tier,
            reasoning=reasoning,
            components={
                "listed_discount": round(score_f, 2),
                "keyword_boost": round(score_g, 2),
                "category_relative": round(score_h, 2),
                "freshness": round(score_i, 2),
                "shop_reliability": round(score_j, 2),
                "scoring_path": "limited_history",
                "history_points": len(history),
                "keywords_found": keyword_hits,
            },
        )

    # ------------------------------------------------------------------
    # Sub-scorers for the lightweight path
    # ------------------------------------------------------------------

    def _score_listed_discount_limited(self, discount_pct: float) -> float:
        """Convert listed discount percentage to a 0-40 score.

        Scoring curve:
            0%   ->  0 pts   (no discount listed)
            10%  ->  8 pts
            20%  -> 16 pts
            30%  -> 22 pts
            50%  -> 30 pts
            70%  -> 36 pts
            80%+ -> 40 pts

        Uses a soft curve so small discounts still earn some points but
        very large discounts are required to reach the cap.

        Args:
            discount_pct: Discount as a percentage (0-100)

        Returns:
            Score from 0.0 to 40.0
        """
        if discount_pct <= 0:
            return 0.0
        # Piecewise linear scaling; steep at first, then flattens
        if discount_pct >= 80:
            return 40.0
        if discount_pct >= 50:
            # 50% -> 30, 80% -> 40  =>  0.333 per %
            return 30.0 + (discount_pct - 50) * (10.0 / 30.0)
        if discount_pct >= 20:
            # 20% -> 16, 50% -> 30  =>  0.467 per %
            return 16.0 + (discount_pct - 20) * (14.0 / 30.0)
        # 0% -> 0, 20% -> 16  =>  0.8 per %
        return discount_pct * 0.8

    def _score_title_keywords(self, title: str) -> tuple[float, list[str]]:
        """Scan product title for Korean deal keywords and return a score.

        Searches the title (case-insensitive) for each keyword.  Points are
        cumulative but capped at 20.  Returns both the score and the list of
        matched keywords (for reasoning).

        Args:
            title: Product or deal title string

        Returns:
            Tuple of (score 0-20, list of matched keyword strings)
        """
        title_lower = title.lower()
        total_bonus = 0.0
        hits: list[str] = []

        for keyword, points in DEAL_KEYWORDS.items():
            if keyword in title_lower:
                total_bonus += points
                hits.append(keyword)

        return min(20.0, total_bonus), hits

    async def _score_category_relative_price(
        self,
        current_price: Decimal,
        category_slug: str,
        exclude_product_id: UUID,
    ) -> tuple[float, float]:
        """Score based on how current_price compares to the category median.

        Fetches the median deal price for all active deals in the same
        category (excluding the current product to avoid self-comparison).
        Products priced well below the category median score higher.

        Scoring:
            price >= category median       ->  0 pts
            price 10% below median         ->  4 pts
            price 20% below median         ->  8 pts
            price 35% below median         -> 14 pts
            price 50%+ below median        -> 20 pts

        Args:
            current_price: Current deal price
            category_slug: Category slug to look up peers
            exclude_product_id: Product to exclude from the peer set

        Returns:
            Tuple of (score 0-20, pct_below_category_median as float)
        """
        try:
            # Import here to avoid circular import at module load time
            from app.models.category import Category

            # Resolve category id from slug
            cat_result = await self.db.execute(
                select(Category.id).where(Category.slug == category_slug)
            )
            cat_row = cat_result.scalar_one_or_none()
            if cat_row is None:
                return 0.0, 0.0

            category_id = cat_row

            # Compute median deal_price across all active deals in category
            # SQLite doesn't have a native PERCENTILE_CONT so we fetch all
            # prices and compute in Python.
            peers_result = await self.db.execute(
                select(Deal.deal_price)
                .where(
                    and_(
                        Deal.category_id == category_id,
                        Deal.is_active == True,  # noqa: E712
                        Deal.product_id != exclude_product_id,
                    )
                )
            )
            peer_prices = [float(row) for row in peers_result.scalars().all() if row and float(row) > 0]

            if len(peer_prices) < 3:
                # Too few peers — no meaningful comparison
                return 0.0, 0.0

            category_median = statistics.median(peer_prices)
            if category_median <= 0:
                return 0.0, 0.0

            pct_below = float((Decimal(str(category_median)) - current_price) / Decimal(str(category_median)) * 100)

            # Piecewise linear: 50%+ below median -> 20 pts
            if pct_below <= 0:
                score = 0.0
            elif pct_below >= 50:
                score = 20.0
            elif pct_below >= 35:
                score = 14.0 + (pct_below - 35) * (6.0 / 15.0)
            elif pct_below >= 20:
                score = 8.0 + (pct_below - 20) * (6.0 / 15.0)
            elif pct_below >= 10:
                score = 4.0 + (pct_below - 10) * (4.0 / 10.0)
            else:
                score = pct_below * 0.4

            return round(score, 2), round(pct_below, 1)

        except Exception as exc:
            self.logger.warning(
                "category_relative_price_failed",
                error=str(exc),
            )
            return 0.0, 0.0

    def _score_freshness(self, created_at: Optional[datetime]) -> float:
        """Award points for recency of the deal.

        Newer deals are more likely to reflect real-time pricing events
        (flash sales, limited-time promotions).

        Scoring:
            Deal created within last 1 hour   -> 10 pts
            Deal created within last 6 hours  ->  8 pts
            Deal created within last 24 hours ->  6 pts
            Deal created within last 3 days   ->  4 pts
            Deal created within last 7 days   ->  2 pts
            Older or unknown                  ->  0 pts

        Args:
            created_at: Timezone-aware datetime when the deal was created

        Returns:
            Score from 0.0 to 10.0
        """
        if created_at is None:
            return 3.0  # Neutral default when timestamp is unavailable

        now = datetime.now(timezone.utc)
        # Ensure created_at is timezone-aware for comparison
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        age = now - created_at

        if age <= timedelta(hours=1):
            return 10.0
        if age <= timedelta(hours=6):
            return 8.0
        if age <= timedelta(hours=24):
            return 6.0
        if age <= timedelta(days=3):
            return 4.0
        if age <= timedelta(days=7):
            return 2.0
        return 0.0

    def _score_shop_reliability(self, shop_slug: Optional[str]) -> float:
        """Return a reliability bonus for well-known shopping platforms.

        Well-established shops are more likely to have accurate pricing
        and honor advertised discounts.

        Args:
            shop_slug: Shop identifier slug (e.g. "naver", "coupang")

        Returns:
            Score from 0.0 to 10.0
        """
        if shop_slug is None:
            return 3.0  # Neutral default for unknown shop
        return SHOP_RELIABILITY.get(shop_slug.lower(), 3.0)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _classify_tier(self, score: Decimal, threshold: Decimal) -> str:
        """Classify a score into a deal tier string.

        Args:
            score: Computed deal score (0-100)
            threshold: Minimum score for 'deal' tier (category-specific)

        Returns:
            One of "super_deal", "hot_deal", "deal", or "none"
        """
        if score >= SUPER_DEAL_THRESHOLD:
            return "super_deal"
        if score >= HOT_DEAL_THRESHOLD:
            return "hot_deal"
        if score >= threshold:
            return "deal"
        return "none"

    async def _get_price_history(
        self, product_id: UUID, days: int = 90
    ) -> List[PriceHistory]:
        """Fetch price history for a product within a time window.

        Args:
            product_id: Product UUID
            days: Number of days to look back (default: 90)

        Returns:
            List of PriceHistory records, ordered by recorded_at desc
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(PriceHistory)
            .where(
                and_(
                    PriceHistory.product_id == product_id,
                    PriceHistory.recorded_at >= cutoff,
                )
            )
            .order_by(PriceHistory.recorded_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Reasoning generators
    # ------------------------------------------------------------------

    def _generate_reasoning_full(
        self,
        total: Decimal,
        pct_below_avg: float,
        pct_below_recent: float,
        is_all_time_low: bool,
        listed_discount: float,
        tier: str,
        history_count: int,
    ) -> str:
        """Generate Korean reasoning text for the full-history scoring path.

        Args:
            total: Final deal score
            pct_below_avg: Percentage below 90-day average price
            pct_below_recent: Percentage below 7-day recent average
            is_all_time_low: Whether this is an all-time low price
            listed_discount: Advertised discount percentage
            tier: Deal tier classification
            history_count: Number of price history records used

        Returns:
            Korean explanation string
        """
        parts: list[str] = []

        if pct_below_avg > 5:
            parts.append(f"평균가 대비 {pct_below_avg:.1f}% 저렴")

        if pct_below_recent > 10:
            parts.append(f"최근 7일 대비 {pct_below_recent:.1f}% 급락")

        if is_all_time_low:
            parts.append("역대 최저가")

        if listed_discount > 10:
            parts.append(f"표시 할인율 {listed_discount:.0f}%")

        parts.append(f"가격 이력 {history_count}건 분석")

        tier_labels = {
            "super_deal": "슈퍼특가",
            "hot_deal": "핫딜",
            "deal": "특가",
            "none": "",
        }

        prefix = tier_labels.get(tier, "")
        detail = ", ".join(parts) if parts else "할인 정보 분석 중"

        if prefix:
            return f"{prefix} - {detail} (점수: {float(total):.0f}점)"
        return f"{detail} (점수: {float(total):.0f}점)"

    def _generate_reasoning_limited(
        self,
        total: Decimal,
        listed_discount_pct: float,
        keyword_hits: list[str],
        pct_below_category: float,
        score_f: float,
        score_g: float,
        score_h: float,
        score_i: float,
        score_j: float,
        tier: str,
    ) -> str:
        """Generate Korean reasoning text for the limited-history scoring path.

        Args:
            total: Final deal score
            listed_discount_pct: Advertised discount percentage
            keyword_hits: List of Korean deal keywords found in the title
            pct_below_category: How far below the category median price this is
            score_f: Listed discount component score
            score_g: Keyword boost component score
            score_h: Category-relative price component score
            score_i: Freshness component score
            score_j: Shop reliability component score
            tier: Deal tier classification

        Returns:
            Korean explanation string
        """
        parts: list[str] = []

        if listed_discount_pct > 0:
            parts.append(f"표시 할인율 {listed_discount_pct:.0f}%")

        if keyword_hits:
            kw_str = "·".join(keyword_hits[:3])
            parts.append(f"딜 키워드: {kw_str}")

        if pct_below_category > 5:
            parts.append(f"카테고리 평균 대비 {pct_below_category:.0f}% 저렴")

        if score_i >= 6:
            parts.append("신규 등록 딜")
        elif score_i >= 4:
            parts.append("최근 등록")

        # Always note that this used limited-history path so users understand
        parts.append("초기 가격 데이터 기반 분석")

        tier_labels = {
            "super_deal": "슈퍼특가",
            "hot_deal": "핫딜",
            "deal": "특가",
            "none": "",
        }

        prefix = tier_labels.get(tier, "")
        detail = ", ".join(parts) if parts else "신규 상품, 가격 데이터 수집 중"

        if prefix:
            return f"{prefix} - {detail} (점수: {float(total):.0f}점)"
        return f"{detail} (점수: {float(total):.0f}점)"

    # ------------------------------------------------------------------
    # Legacy public method kept for backward compatibility
    # ------------------------------------------------------------------

    def _generate_reasoning(
        self,
        score: Decimal,
        pct_below_avg: float,
        pct_below_recent: float,
        is_all_time_low: bool,
        listed_discount: float,
        tier: str,
    ) -> str:
        """Generate human-readable Korean reasoning (legacy signature).

        This method is retained for backward compatibility with any callers
        that invoke it directly.  New code should use
        _generate_reasoning_full() or _generate_reasoning_limited().

        Args:
            score: Overall deal score
            pct_below_avg: Percentage below average price
            pct_below_recent: Percentage below recent average
            is_all_time_low: Whether at all-time low price
            listed_discount: Listed discount percentage
            tier: Deal tier classification

        Returns:
            Korean string explaining why this is (or isn't) a deal
        """
        return self._generate_reasoning_full(
            total=score,
            pct_below_avg=pct_below_avg,
            pct_below_recent=pct_below_recent,
            is_all_time_low=is_all_time_low,
            listed_discount=listed_discount,
            tier=tier,
            history_count=0,
        )
