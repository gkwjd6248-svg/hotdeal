# -*- coding: utf-8 -*-
"""Add Steam shop to the DB and run a test scrape of Steam featured deals.

Usage:
    python add_steam_and_scrape.py

Requirements:
    - SQLite DB must already be initialised (run init_and_scrape.py first, or
      ensure backend/dealhawk.db exists with the expected schema).
    - No API key is required; Steam Store API is public/free.
"""

import asyncio
import sys
from pathlib import Path

# Make sure the backend package is importable when running from backend/
sys.path.insert(0, str(Path(__file__).parent))


# ---------------------------------------------------------------------------
# Step 1: Ensure tables exist (safe no-op if already created)
# ---------------------------------------------------------------------------

async def create_tables() -> None:
    """Create all SQLAlchemy-mapped tables if they do not already exist."""
    from app.db.session import engine
    from app.models.base import Base
    import app.models  # noqa: F401 – registers all models with Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("[OK] Tables verified / created")


# ---------------------------------------------------------------------------
# Step 2: Seed the Steam shop and games-software category
# ---------------------------------------------------------------------------

async def seed_steam() -> None:
    """Insert the Steam shop (and games-software category) if not present."""
    from sqlalchemy import select
    from app.db.session import async_session_factory
    from app.models.shop import Shop
    from app.models.category import Category

    async with async_session_factory() as session:
        # ---- Steam shop -------------------------------------------------------
        result = await session.execute(
            select(Shop).where(Shop.slug == "steam")
        )
        steam_shop = result.scalar_one_or_none()

        if steam_shop:
            print(f"[SKIP] Steam shop already in DB (id={steam_shop.id})")
        else:
            steam_shop = Shop(
                name="스팀",
                name_en="Steam",
                slug="steam",
                base_url="https://store.steampowered.com",
                adapter_type="api",
                is_active=True,
                scrape_interval_minutes=60,
                country="US",
                currency="USD",
                metadata_={},
            )
            session.add(steam_shop)
            await session.flush()  # populate id before commit
            print(f"[OK] Steam shop inserted (id={steam_shop.id})")

        # ---- games-software category ------------------------------------------
        result = await session.execute(
            select(Category).where(Category.slug == "games-software")
        )
        games_cat = result.scalar_one_or_none()

        if games_cat:
            print(f"[SKIP] 'games-software' category already in DB (id={games_cat.id})")
        else:
            games_cat = Category(
                name="게임/SW",
                name_en="Games/Software",
                slug="games-software",
                icon="gamepad",
                sort_order=4,
            )
            session.add(games_cat)
            await session.flush()
            print(f"[OK] 'games-software' category inserted (id={games_cat.id})")

        await session.commit()


# ---------------------------------------------------------------------------
# Step 3: Run the Steam adapter and persist results
# ---------------------------------------------------------------------------

async def run_steam_scraper() -> None:
    """Fetch Steam featured specials and save them to the database."""
    from app.db.session import async_session_factory
    from app.scrapers.adapters.steam import SteamAdapter
    from app.scrapers.scraper_service import ScraperService

    print("\n[...] Initialising Steam adapter...")
    adapter = SteamAdapter()

    # Optional quick health check (makes one API call to Steam)
    print("[...] Running Steam API health check...")
    try:
        healthy = await adapter.health_check()
    except Exception as exc:
        print(f"[WARN] Health check raised an exception: {exc}")
        healthy = False

    if not healthy:
        print("[ERROR] Steam API health check failed – aborting scrape.")
        return

    print("[OK] Steam API is reachable")

    # Fetch deals (no category filter – Steam adapter ignores it anyway)
    print("[...] Fetching Steam featured specials...")
    try:
        deals = await adapter.fetch_deals()
    except Exception as exc:
        print(f"[ERROR] fetch_deals() raised: {exc}")
        return

    print(f"[OK] {len(deals)} deals fetched from Steam")

    if not deals:
        print("[WARN] No deals returned – nothing to save.")
        return

    # Persist via ScraperService (same pattern as init_and_scrape.py)
    async with async_session_factory() as session:
        service = ScraperService(session)
        stats = await service.process_deals(deals, shop_slug="steam")
        await session.commit()

    print("\n[RESULTS]")
    print(f"  Deals fetched:    {stats['deals_fetched']}")
    print(f"  Products created: {stats['products_created']}")
    print(f"  Products updated: {stats['products_updated']}")
    print(f"  Deals created:    {stats['deals_created']}")
    print(f"  Deals updated:    {stats['deals_updated']}")
    print(f"  Errors:           {stats['errors']}")


# ---------------------------------------------------------------------------
# Step 4: Display top deals that were saved
# ---------------------------------------------------------------------------

async def show_steam_deals() -> None:
    """Print the top Steam deals currently in the database."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.db.session import async_session_factory
    from app.models.deal import Deal
    from app.models.shop import Shop

    async with async_session_factory() as session:
        # Load deals that belong to the steam shop
        result = await session.execute(
            select(Deal)
            .join(Shop, Deal.shop_id == Shop.id)
            .where(Shop.slug == "steam")
            .where(Deal.is_active == True)
            .order_by(Deal.discount_percentage.desc().nullslast())
            .limit(15)
        )
        deals = result.scalars().all()

        if not deals:
            print("\n[INFO] No Steam deals found in DB yet.")
            return

        sep = "=" * 72
        print(f"\n{sep}")
        print(f"  Top {len(deals)} Steam Deals in DB (sorted by discount %)")
        print(sep)
        for i, d in enumerate(deals, 1):
            price = f"{d.deal_price:,.0f}" if d.deal_price else "?"
            orig  = f"{d.original_price:,.0f}" if d.original_price else "-"
            disc  = f"{d.discount_percentage:.0f}%" if d.discount_percentage else "N/A"
            title = (d.title or "")[:55]
            print(f"  {i:2}. {title}")
            print(f"      현재가: {price}원  /  정가: {orig}원  /  할인: {disc}")
        print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=== DealHawk – Add Steam Shop & Test Scrape ===\n")

    print("1. Ensuring tables exist...")
    await create_tables()

    print("\n2. Seeding Steam shop + games-software category...")
    await seed_steam()

    print("\n3. Running Steam scraper...")
    await run_steam_scraper()

    print("\n4. Steam deals saved in DB:")
    await show_steam_deals()

    print("\nDone!")


if __name__ == "__main__":
    # Use UTF-8 output on Windows to avoid UnicodeEncodeError with Korean text
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    asyncio.run(main())
