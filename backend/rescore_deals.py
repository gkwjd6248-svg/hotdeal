"""Batch re-scoring script for all existing deals.

Re-calculates AI scores for every deal in the database using the updated
PriceAnalyzer algorithm that handles limited price history gracefully.

Usage:
    cd backend
    python rescore_deals.py

    # Dry-run (preview scores without writing to DB):
    python rescore_deals.py --dry-run

    # Limit to first N deals (for testing):
    python rescore_deals.py --limit 20

    # Only rescore deals for a specific shop slug:
    python rescore_deals.py --shop naver

    # Verbose output (print score breakdown per deal):
    python rescore_deals.py --verbose
"""

import asyncio
import argparse
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

# ---------------------------------------------------------------------------
# Ensure the backend package is importable when running from the backend dir
# ---------------------------------------------------------------------------
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# App imports (must happen after sys.path setup)
from app.db.session import async_session_factory
from app.models.deal import Deal
from app.models.shop import Shop
from app.models.category import Category
from app.services.price_analysis import PriceAnalyzer, DEAL_THRESHOLD, HOT_DEAL_THRESHOLD, SUPER_DEAL_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tier_label(score: Decimal) -> str:
    """Return a human-readable tier label for a score."""
    if score >= SUPER_DEAL_THRESHOLD:
        return "SUPER DEAL"
    if score >= HOT_DEAL_THRESHOLD:
        return "HOT DEAL"
    if score >= DEAL_THRESHOLD:
        return "DEAL"
    return "none"


def _tier_emoji(score: Decimal) -> str:
    if score >= SUPER_DEAL_THRESHOLD:
        return "[***]"
    if score >= HOT_DEAL_THRESHOLD:
        return "[**]"
    if score >= DEAL_THRESHOLD:
        return "[*]"
    return "[ ]"


# ---------------------------------------------------------------------------
# Core rescoring logic
# ---------------------------------------------------------------------------

async def rescore_all(
    dry_run: bool = False,
    limit: Optional[int] = None,
    shop_slug: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Re-score all qualifying deals in the database.

    Iterates over all active deals (optionally filtered by shop slug),
    calls PriceAnalyzer.compute_deal_score() for each, and writes the
    updated ai_score and ai_reasoning back to the database in batches.

    Args:
        dry_run: If True, compute scores but do not write to the database.
        limit: Maximum number of deals to process (None = all).
        shop_slug: If provided, only rescore deals from this shop.
        verbose: If True, print per-deal score breakdowns.
    """
    print("=" * 70)
    print("DealHawk - AI Score Re-calculation")
    print(f"Mode       : {'DRY RUN (no DB writes)' if dry_run else 'LIVE (writing to DB)'}")
    print(f"Shop filter: {shop_slug or 'all shops'}")
    print(f"Limit      : {limit or 'all deals'}")
    print("=" * 70)

    async with async_session_factory() as session:
        # ------------------------------------------------------------------
        # Fetch deals with their related shop and category
        # ------------------------------------------------------------------
        query = (
            select(Deal)
            .options(
                selectinload(Deal.shop),
                selectinload(Deal.category),
            )
            .where(Deal.is_active == True)  # noqa: E712
            .order_by(Deal.created_at.desc())
        )

        if shop_slug:
            query = query.join(Deal.shop).where(Shop.slug == shop_slug)

        if limit:
            query = query.limit(limit)

        result = await session.execute(query)
        deals = list(result.scalars().all())

    print(f"Found {len(deals)} deal(s) to process.\n")

    if not deals:
        print("Nothing to do.")
        return

    # ------------------------------------------------------------------
    # Score distribution tracking
    # ------------------------------------------------------------------
    stats = {
        "total": len(deals),
        "scored": 0,
        "errors": 0,
        "tiers": {"super_deal": 0, "hot_deal": 0, "deal": 0, "none": 0},
        "score_sum": 0.0,
        "score_min": 999.0,
        "score_max": 0.0,
        "old_score_sum": 0.0,
    }

    # Process deals in batches (to avoid holding a long-lived session)
    BATCH_SIZE = 50
    start_time = time.monotonic()

    for batch_start in range(0, len(deals), BATCH_SIZE):
        batch = deals[batch_start : batch_start + BATCH_SIZE]

        async with async_session_factory() as session:
            analyzer = PriceAnalyzer(session)
            updates: list[dict] = []

            for deal in batch:
                try:
                    # Gather context for the new scorer
                    shop_slug_val: Optional[str] = deal.shop.slug if deal.shop else None
                    category_slug_val: Optional[str] = deal.category.slug if deal.category else None

                    old_score = float(deal.ai_score) if deal.ai_score is not None else 0.0
                    stats["old_score_sum"] += old_score

                    # UUID handling — the DB stores UUIDs as strings in SQLite
                    product_id: UUID
                    if isinstance(deal.product_id, str):
                        product_id = UUID(deal.product_id)
                    else:
                        product_id = deal.product_id

                    # created_at may be a naive datetime from SQLite
                    created_at: Optional[datetime] = deal.created_at
                    if created_at is not None and created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)

                    deal_score = await analyzer.compute_deal_score(
                        product_id=product_id,
                        current_price=deal.deal_price,
                        original_price=deal.original_price,
                        category_slug=category_slug_val,
                        title=deal.title,
                        shop_slug=shop_slug_val,
                        created_at=created_at,
                    )

                    new_score = float(deal_score.score)
                    updates.append({
                        "id": deal.id,
                        "ai_score": deal_score.score,
                        "ai_reasoning": deal_score.reasoning,
                    })

                    # Accumulate stats
                    stats["scored"] += 1
                    stats["tiers"][deal_score.deal_tier] = stats["tiers"].get(deal_score.deal_tier, 0) + 1
                    stats["score_sum"] += new_score
                    if new_score < stats["score_min"]:
                        stats["score_min"] = new_score
                    if new_score > stats["score_max"]:
                        stats["score_max"] = new_score

                    if verbose:
                        tier_str = _tier_emoji(deal_score.score)
                        title_preview = deal.title[:55] if deal.title else "(no title)"
                        print(
                            f"{tier_str} {new_score:5.1f} pts  "
                            f"(was {old_score:5.1f})  "
                            f"[{shop_slug_val or '?':8s}] "
                            f"[{category_slug_val or '?':15s}] "
                            f"{title_preview}"
                        )
                        if verbose and deal_score.components:
                            comp = deal_score.components
                            path = comp.get("scoring_path", "?")
                            if path == "limited_history":
                                print(
                                    f"       F(disc)={comp.get('listed_discount', 0):4.1f}  "
                                    f"G(kw)={comp.get('keyword_boost', 0):4.1f}  "
                                    f"H(cat)={comp.get('category_relative', 0):4.1f}  "
                                    f"I(fresh)={comp.get('freshness', 0):4.1f}  "
                                    f"J(shop)={comp.get('shop_reliability', 0):4.1f}  "
                                    f"kws={comp.get('keywords_found', [])}"
                                )
                            else:
                                print(
                                    f"       A(avg)={comp.get('vs_average', 0):4.1f}  "
                                    f"B(rec)={comp.get('vs_recent', 0):4.1f}  "
                                    f"C(atl)={comp.get('all_time_low', 0):4.1f}  "
                                    f"D(disc)={comp.get('listed_discount', 0):4.1f}  "
                                    f"E(anom)={comp.get('anomaly_bonus', 0):4.1f}"
                                )
                        print(f"       Reasoning: {deal_score.reasoning}")
                        print()

                except Exception as exc:
                    stats["errors"] += 1
                    title_preview = deal.title[:50] if deal.title else "(no title)"
                    print(
                        f"[ERROR] Failed to score deal {deal.id} "
                        f"('{title_preview}'): {exc}",
                        file=sys.stderr,
                    )

            # --------------------------------------------------------------
            # Write batch updates to DB
            # --------------------------------------------------------------
            if not dry_run and updates:
                for upd in updates:
                    await session.execute(
                        update(Deal)
                        .where(Deal.id == upd["id"])
                        .values(
                            ai_score=upd["ai_score"],
                            ai_reasoning=upd["ai_reasoning"],
                        )
                    )
                await session.commit()

        processed = min(batch_start + BATCH_SIZE, len(deals))
        elapsed = time.monotonic() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        print(
            f"Progress: {processed}/{len(deals)} deals processed  "
            f"({rate:.1f} deals/sec)",
            flush=True,
        )

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------
    elapsed_total = time.monotonic() - start_time
    n = stats["scored"] or 1  # avoid division by zero

    print()
    print("=" * 70)
    print("RESCORING COMPLETE")
    print("=" * 70)
    print(f"Total deals processed : {stats['total']}")
    print(f"Successfully scored   : {stats['scored']}")
    print(f"Errors                : {stats['errors']}")
    print(f"Time elapsed          : {elapsed_total:.1f}s")
    print()
    print("Score distribution (new scores):")
    print(f"  Super deals (>= 85) : {stats['tiers'].get('super_deal', 0)}")
    print(f"  Hot deals   (>= 70) : {stats['tiers'].get('hot_deal', 0)}")
    print(f"  Deals       (>= 35) : {stats['tiers'].get('deal', 0)}")
    print(f"  No deal     (< 35)  : {stats['tiers'].get('none', 0)}")
    print()
    old_avg = stats["old_score_sum"] / n
    new_avg = stats["score_sum"] / n
    print(f"Average score (before): {old_avg:.1f}")
    print(f"Average score (after) : {new_avg:.1f}")
    print(f"Min score             : {stats['score_min']:.1f}")
    print(f"Max score             : {stats['score_max']:.1f}")

    if dry_run:
        print()
        print("[DRY RUN] No changes were written to the database.")
    else:
        print()
        print("Database updated successfully.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and run the rescore job."""
    parser = argparse.ArgumentParser(
        description="Re-calculate AI deal scores for all deals in the DealHawk database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Compute scores but do NOT write them to the database.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N deals (for testing).",
    )
    parser.add_argument(
        "--shop",
        type=str,
        default=None,
        metavar="SLUG",
        help="Only rescore deals from this shop slug (e.g. 'naver', 'steam').",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Print per-deal score breakdown.",
    )
    args = parser.parse_args()

    asyncio.run(
        rescore_all(
            dry_run=args.dry_run,
            limit=args.limit,
            shop_slug=args.shop,
            verbose=args.verbose,
        )
    )


if __name__ == "__main__":
    main()
