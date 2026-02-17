"""Initialize SQLite DB, seed data, and run Naver scraper.

Usage: python init_and_scrape.py
"""
import asyncio
import sys
from pathlib import Path

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).parent))


async def create_tables():
    """Create all tables from SQLAlchemy models."""
    from app.db.session import engine
    from app.models.base import Base
    # Import all models so they register with Base
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Tables created")


async def seed_data():
    """Seed shops and categories."""
    from sqlalchemy import select
    from app.db.session import async_session_factory
    from app.models.shop import Shop
    from app.models.category import Category

    async with async_session_factory() as session:
        # Check if already seeded
        result = await session.execute(select(Shop).limit(1))
        if result.scalar_one_or_none():
            print("[SKIP] Already seeded")
            return

        # Shops
        shops = [
            Shop(name="네이버 쇼핑", name_en="Naver Shopping", slug="naver",
                 base_url="https://shopping.naver.com", adapter_type="api",
                 is_active=True, scrape_interval_minutes=30,
                 country="KR", currency="KRW", metadata_={}),
            Shop(name="쿠팡", name_en="Coupang", slug="coupang",
                 base_url="https://www.coupang.com", adapter_type="api",
                 is_active=False, scrape_interval_minutes=60,
                 country="KR", currency="KRW", metadata_={}),
            Shop(name="11번가", name_en="11st", slug="11st",
                 base_url="https://www.11st.co.kr", adapter_type="api",
                 is_active=False, scrape_interval_minutes=60,
                 country="KR", currency="KRW", metadata_={}),
        ]
        for s in shops:
            session.add(s)

        # Categories
        categories = [
            Category(name="PC/하드웨어", name_en="PC/Hardware", slug="pc-hardware", icon="cpu", sort_order=1),
            Category(name="노트북/모바일", name_en="Laptop/Mobile", slug="laptop-mobile", icon="smartphone", sort_order=2),
            Category(name="가전/TV", name_en="Electronics/TV", slug="electronics-tv", icon="tv", sort_order=3),
            Category(name="게임/SW", name_en="Games/Software", slug="games-software", icon="gamepad", sort_order=4),
            Category(name="상품권/쿠폰", name_en="Gift Cards", slug="gift-cards", icon="gift", sort_order=5),
            Category(name="생활/식품", name_en="Living/Food", slug="living-food", icon="shopping-basket", sort_order=6),
        ]
        for c in categories:
            session.add(c)

        await session.commit()
        print(f"[OK] Seeded {len(shops)} shops, {len(categories)} categories")


async def run_naver_scraper():
    """Run Naver Shopping adapter and save results to DB."""
    from app.config import settings
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        print("[ERROR] NAVER_CLIENT_ID / NAVER_CLIENT_SECRET not set in .env")
        print("  -> https://developers.naver.com 에서 애플리케이션 등록 후 키를 .env에 입력하세요")
        return

    from app.db.session import async_session_factory
    from app.scrapers.adapters.naver import NaverShoppingAdapter

    adapter = NaverShoppingAdapter()

    # Health check
    print("[...] Naver API health check...")
    healthy = await adapter.health_check()
    if not healthy:
        print("[ERROR] Naver API health check failed")
        return
    print("[OK] Naver API is healthy")

    # Fetch deals from just 2 categories to start small
    test_categories = ["pc-hardware", "laptop-mobile"]
    all_deals = []

    for cat in test_categories:
        print(f"[...] Fetching deals for category: {cat}")
        try:
            deals = await adapter.fetch_deals(category=cat)
            all_deals.extend(deals)
            print(f"  -> {len(deals)} deals found")
        except Exception as e:
            print(f"  -> Error: {e}")

    print(f"\n[TOTAL] {len(all_deals)} deals fetched from Naver")

    if not all_deals:
        print("[WARN] No deals to save")
        return

    # Save to DB
    from app.scrapers.scraper_service import ScraperService

    async with async_session_factory() as session:
        service = ScraperService(session)
        stats = await service.process_deals(all_deals, "naver")
        await session.commit()

    print(f"\n[RESULTS]")
    print(f"  Products created: {stats['products_created']}")
    print(f"  Products updated: {stats['products_updated']}")
    print(f"  Deals created:    {stats['deals_created']}")
    print(f"  Deals updated:    {stats['deals_updated']}")
    print(f"  Errors:           {stats['errors']}")


async def show_saved_deals():
    """Print deals saved in DB."""
    from sqlalchemy import select
    from app.db.session import async_session_factory
    from app.models.deal import Deal

    async with async_session_factory() as session:
        result = await session.execute(
            select(Deal).where(Deal.is_active == True)
            .order_by(Deal.ai_score.desc().nullslast())
            .limit(10)
        )
        deals = result.scalars().all()

        if not deals:
            print("\n[INFO] No deals in DB yet")
            return

        print(f"\n{'='*70}")
        print(f"  Top {len(deals)} Deals in DB (by AI Score)")
        print(f"{'='*70}")
        for i, d in enumerate(deals, 1):
            score = f"{d.ai_score:.0f}" if d.ai_score else "N/A"
            disc = f"{d.discount_percentage:.0f}%" if d.discount_percentage else "-"
            price = f"{d.deal_price:,.0f}" if d.deal_price else "?"
            print(f"  {i:2}. [{score}점] {d.title[:50]}")
            print(f"      {price}원 (할인 {disc})")
        print(f"{'='*70}")


async def main():
    print("=== DealHawk DB Init & Naver Scrape ===\n")

    print("1. Creating tables...")
    await create_tables()

    print("\n2. Seeding data...")
    await seed_data()

    print("\n3. Running Naver scraper...")
    await run_naver_scraper()

    print("\n4. Saved deals:")
    await show_saved_deals()

    print("\nDone! Start backend with: python -m uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(main())
