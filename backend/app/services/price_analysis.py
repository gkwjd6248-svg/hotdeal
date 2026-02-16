"""AI-powered price analysis and deal scoring engine.

This module implements the core value proposition of DealHawk: analyzing
price history to automatically detect and score good deals. The PriceAnalyzer
computes a multi-component AI score (0-100) based on historical price trends,
statistical anomalies, and discount depth.
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

logger = structlog.get_logger(__name__)

# Scoring thresholds
DEAL_THRESHOLD = Decimal("35.0")  # Minimum score to qualify as a deal
HOT_DEAL_THRESHOLD = Decimal("70.0")  # Hot deal threshold
SUPER_DEAL_THRESHOLD = Decimal("85.0")  # Super deal / featured threshold

# Category-specific thresholds (some categories have different deal definitions)
CATEGORY_THRESHOLDS = {
    "pc-hardware": Decimal("30.0"),  # PC parts often have smaller margins
    "games-software": Decimal("40.0"),  # Games have steeper sales
    "gift-cards": Decimal("20.0"),  # Gift cards rarely discount deeply
    "electronics-tv": Decimal("35.0"),
    "laptop-mobile": Decimal("35.0"),
    "living-food": Decimal("25.0"),  # Food/grocery has frequent but smaller sales
}

# Statistical analysis parameters
MIN_HISTORY_FOR_STATS = 3  # Minimum price points needed for statistical analysis
HISTORY_WINDOW_DAYS = 90  # Look back 90 days for historical average
RECENT_WINDOW_DAYS = 7  # Look back 7 days for recent average


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
    significant price drops. Uses multiple scoring components:

    - Component A (0-30): Discount from historical average
    - Component B (0-20): Sudden drop from recent average
    - Component C (0-25): Proximity to all-time low
    - Component D (0-15): Listed discount percentage
    - Component E (0-10): Statistical anomaly bonus

    Total score ranges from 0-100, with higher scores indicating better deals.
    """

    def __init__(self, db: AsyncSession):
        """Initialize price analyzer.

        Args:
            db: Async database session
        """
        self.db = db
        self.logger = logger.bind(service="price_analyzer")

    async def compute_deal_score(
        self,
        product_id: UUID,
        current_price: Decimal,
        original_price: Optional[Decimal] = None,
        category_slug: Optional[str] = None,
    ) -> DealScore:
        """Compute AI deal score (0-100) based on price history analysis.

        This is the core algorithm that powers DealHawk's AI deal detection.
        It analyzes historical price data and computes a multi-component score
        that reflects deal quality from multiple perspectives.

        Args:
            product_id: UUID of the product to analyze
            current_price: Current price to evaluate
            original_price: Optional original/MSRP price (for listed discount calc)
            category_slug: Optional category slug for category-specific thresholds

        Returns:
            DealScore object with score, tier, reasoning, and component breakdown

        Score Components:
            A. Discount from historical average (0-30 points)
               How much cheaper vs 90-day average

            B. Sudden drop from recent average (0-20 points)
               Recent price movement (last 7 days)

            C. All-time low proximity (0-25 points)
               How close to historical minimum price

            D. Listed discount percentage (0-15 points)
               Seller's advertised discount

            E. Statistical anomaly bonus (0-10 points)
               Z-score based outlier detection
        """
        self.logger.info(
            "computing_deal_score",
            product_id=str(product_id),
            current_price=float(current_price),
            category=category_slug,
        )

        # 1. Fetch price history
        history = await self._get_price_history(product_id, days=HISTORY_WINDOW_DAYS)

        # 2. Calculate statistical metrics
        if len(history) >= MIN_HISTORY_FOR_STATS:
            prices = [float(h.price) for h in history]
            avg_price = Decimal(str(statistics.mean(prices)))
            min_price = Decimal(str(min(prices)))
            max_price = Decimal(str(max(prices)))
            std_dev = Decimal(str(statistics.stdev(prices))) if len(prices) > 1 else Decimal("0")
            median_price = Decimal(str(statistics.median(prices)))

            # Recent average (last 7 days)
            now = datetime.now(timezone.utc)
            recent = [h for h in history if h.recorded_at > now - timedelta(days=RECENT_WINDOW_DAYS)]
            recent_avg = Decimal(str(statistics.mean([float(h.price) for h in recent]))) if recent else avg_price

            self.logger.debug(
                "price_statistics",
                avg=float(avg_price),
                min=float(min_price),
                max=float(max_price),
                std_dev=float(std_dev),
                recent_avg=float(recent_avg),
                history_count=len(history),
            )
        else:
            # New product with minimal history - use fallback values
            self.logger.warning(
                "insufficient_history",
                product_id=str(product_id),
                history_count=len(history),
            )
            avg_price = original_price or current_price
            min_price = current_price
            max_price = original_price or current_price
            std_dev = Decimal("0")
            median_price = avg_price
            recent_avg = avg_price

        # 3. Calculate score components

        # Component A: Discount from average (0-30)
        # Higher score if current price is significantly below historical average
        if avg_price > 0:
            pct_below_avg = float((avg_price - current_price) / avg_price * 100)
        else:
            pct_below_avg = 0.0
        score_a = min(30.0, max(0.0, pct_below_avg * 1.5))

        # Component B: Recent drop (0-20)
        # Rewards sudden price drops vs recent pricing
        if recent_avg > 0:
            pct_below_recent = float((recent_avg - current_price) / recent_avg * 100)
        else:
            pct_below_recent = 0.0
        score_b = min(20.0, max(0.0, pct_below_recent * 2.0))

        # Component C: All-time low proximity (0-25)
        # Rewards prices near or at historical minimum
        if max_price > min_price:
            # Position in range: 0 = at max, 1 = at min
            position = float((max_price - current_price) / (max_price - min_price))
            score_c = position * 25.0
        else:
            score_c = 12.5  # Neutral if no price range

        # Component D: Listed discount (0-15)
        # Uses seller's advertised original price vs sale price
        listed_discount = 0.0
        if original_price and original_price > current_price:
            listed_discount = float((original_price - current_price) / original_price * 100)
        score_d = min(15.0, listed_discount * 0.3)

        # Component E: Statistical anomaly (0-10)
        # Detects prices that are statistical outliers (Z-score method)
        if std_dev > 0:
            z_score = float((avg_price - current_price) / std_dev)
            # Reward Z-scores above 1 (1 std dev below mean)
            score_e = min(10.0, max(0.0, (z_score - 1.0) * 5.0))
        else:
            score_e = 0.0

        # Calculate total score (0-100)
        total = Decimal(str(round(min(100.0, max(0.0, score_a + score_b + score_c + score_d + score_e)), 2)))

        self.logger.debug(
            "score_components",
            total=float(total),
            vs_avg=score_a,
            vs_recent=score_b,
            atl_proximity=score_c,
            listed_disc=score_d,
            anomaly=score_e,
        )

        # Determine threshold based on category
        threshold = CATEGORY_THRESHOLDS.get(category_slug, DEAL_THRESHOLD)

        # Determine deal tier
        if total >= SUPER_DEAL_THRESHOLD:
            tier = "super_deal"
        elif total >= HOT_DEAL_THRESHOLD:
            tier = "hot_deal"
        elif total >= threshold:
            tier = "deal"
        else:
            tier = "none"

        # Generate human-readable reasoning in Korean
        reasoning = self._generate_reasoning(
            total, pct_below_avg, pct_below_recent,
            current_price <= min_price, listed_discount, tier
        )

        is_deal = (tier != "none")

        self.logger.info(
            "deal_score_computed",
            product_id=str(product_id),
            score=float(total),
            tier=tier,
            is_deal=is_deal,
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
            }
        )

    async def _get_price_history(self, product_id: UUID, days: int = 90) -> List[PriceHistory]:
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
            .where(and_(
                PriceHistory.product_id == product_id,
                PriceHistory.recorded_at >= cutoff,
            ))
            .order_by(PriceHistory.recorded_at.desc())
        )
        return list(result.scalars().all())

    def _generate_reasoning(
        self,
        score: Decimal,
        pct_below_avg: float,
        pct_below_recent: float,
        is_all_time_low: bool,
        listed_discount: float,
        tier: str,
    ) -> str:
        """Generate human-readable Korean reasoning for the deal score.

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
        parts = []

        if pct_below_avg > 5:
            parts.append(f"평균가 대비 {pct_below_avg:.1f}% 저렴")

        if pct_below_recent > 10:
            parts.append(f"최근 7일 대비 {pct_below_recent:.1f}% 급락")

        if is_all_time_low:
            parts.append("역대 최저가")

        if listed_discount > 10:
            parts.append(f"표시 할인율 {listed_discount:.0f}%")

        # Tier labels with emoji
        tier_labels = {
            "super_deal": "🔥 슈퍼특가",
            "hot_deal": "🔥 핫딜",
            "deal": "💰 특가",
            "none": ""
        }

        prefix = tier_labels.get(tier, "")
        detail = ", ".join(parts) if parts else "할인 정보 분석 중"

        if prefix:
            return f"{prefix} - {detail}"
        else:
            return detail
