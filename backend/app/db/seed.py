"""Database seeding script for development.

Populates the database with initial shops and categories.
Run with: python -m app.db.seed
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import Shop, Category


async def seed_shops():
    """Seed initial shop data."""
    shops_data = [
        {
            "name": "쿠팡",
            "name_en": "Coupang",
            "slug": "coupang",
            "base_url": "https://www.coupang.com",
            "adapter_type": "api",
            "is_active": True,
            "scrape_interval_minutes": 60,
            "country": "KR",
            "currency": "KRW",
            "logo_url": "https://image.coupangcdn.com/image/coupang/common/logo_coupang_w350.png",
            "metadata_": {
                "api_type": "coupang_partners",
                "requires_auth": True,
            }
        },
        {
            "name": "11번가",
            "name_en": "11st",
            "slug": "11st",
            "base_url": "https://www.11st.co.kr",
            "adapter_type": "api",
            "is_active": True,
            "scrape_interval_minutes": 60,
            "country": "KR",
            "currency": "KRW",
            "metadata_": {
                "api_type": "11st_open_api",
                "requires_auth": True,
            }
        },
        {
            "name": "네이버 쇼핑",
            "name_en": "Naver Shopping",
            "slug": "naver",
            "base_url": "https://shopping.naver.com",
            "adapter_type": "api",
            "is_active": True,
            "scrape_interval_minutes": 30,
            "country": "KR",
            "currency": "KRW",
            "metadata_": {
                "api_type": "naver_search_api",
                "requires_auth": True,
            }
        },
        {
            "name": "G마켓",
            "name_en": "Gmarket",
            "slug": "gmarket",
            "base_url": "https://www.gmarket.co.kr",
            "adapter_type": "scraper",
            "is_active": True,
            "scrape_interval_minutes": 120,
            "country": "KR",
            "currency": "KRW",
            "metadata_": {
                "scraper_type": "playwright",
                "requires_js": True,
            }
        },
        {
            "name": "옥션",
            "name_en": "Auction",
            "slug": "auction",
            "base_url": "https://www.auction.co.kr",
            "adapter_type": "scraper",
            "is_active": True,
            "scrape_interval_minutes": 120,
            "country": "KR",
            "currency": "KRW",
            "metadata_": {
                "scraper_type": "playwright",
                "requires_js": True,
            }
        },
        {
            "name": "Amazon US",
            "name_en": "Amazon US",
            "slug": "amazon-us",
            "base_url": "https://www.amazon.com",
            "adapter_type": "api",
            "is_active": False,
            "scrape_interval_minutes": 180,
            "country": "US",
            "currency": "USD",
            "metadata_": {
                "api_type": "amazon_pa_api",
                "requires_auth": True,
            }
        },
        {
            "name": "AliExpress",
            "name_en": "AliExpress",
            "slug": "aliexpress",
            "base_url": "https://www.aliexpress.com",
            "adapter_type": "api",
            "is_active": False,
            "scrape_interval_minutes": 180,
            "country": "CN",
            "currency": "USD",
            "metadata_": {
                "api_type": "aliexpress_open_api",
                "requires_auth": True,
            }
        },
    ]

    async with async_session_factory() as session:
        # Check if shops already exist
        result = await session.execute(select(Shop).limit(1))
        if result.scalar_one_or_none():
            print("Shops already seeded. Skipping...")
            return

        # Create shops
        for shop_data in shops_data:
            shop = Shop(**shop_data)
            session.add(shop)

        await session.commit()
        print(f"✓ Seeded {len(shops_data)} shops")


async def seed_categories():
    """Seed initial category data."""
    categories_data = [
        # Top-level categories
        {
            "name": "전자제품",
            "name_en": "Electronics",
            "slug": "electronics",
            "icon": "cpu",
            "sort_order": 1,
            "parent_id": None,
        },
        {
            "name": "패션/의류",
            "name_en": "Fashion",
            "slug": "fashion",
            "icon": "shirt",
            "sort_order": 2,
            "parent_id": None,
        },
        {
            "name": "뷰티",
            "name_en": "Beauty",
            "slug": "beauty",
            "icon": "sparkles",
            "sort_order": 3,
            "parent_id": None,
        },
        {
            "name": "식품",
            "name_en": "Food",
            "slug": "food",
            "icon": "apple",
            "sort_order": 4,
            "parent_id": None,
        },
        {
            "name": "생활용품",
            "name_en": "Home & Living",
            "slug": "home",
            "icon": "home",
            "sort_order": 5,
            "parent_id": None,
        },
        {
            "name": "스포츠/레저",
            "name_en": "Sports & Leisure",
            "slug": "sports",
            "icon": "dumbbell",
            "sort_order": 6,
            "parent_id": None,
        },
    ]

    # Sub-categories (will be added after parent categories are created)
    electronics_subcategories = [
        ("PC/하드웨어", "PC/Hardware", "pc-hardware", "laptop"),
        ("스마트폰", "Smartphones", "smartphones", "smartphone"),
        ("TV/영상", "TV/Video", "tv-video", "tv"),
        ("가전", "Appliances", "appliances", "refrigerator"),
        ("게임", "Gaming", "gaming", "gamepad"),
    ]

    async with async_session_factory() as session:
        # Check if categories already exist
        result = await session.execute(select(Category).limit(1))
        if result.scalar_one_or_none():
            print("Categories already seeded. Skipping...")
            return

        # Create top-level categories
        category_map = {}
        for cat_data in categories_data:
            category = Category(**cat_data)
            session.add(category)
            category_map[cat_data["slug"]] = category

        await session.flush()  # Get IDs for parent categories

        # Create electronics subcategories
        electronics_parent = category_map["electronics"]
        for idx, (name, name_en, slug, icon) in enumerate(electronics_subcategories):
            subcategory = Category(
                name=name,
                name_en=name_en,
                slug=slug,
                icon=icon,
                sort_order=idx + 1,
                parent_id=electronics_parent.id,
            )
            session.add(subcategory)

        await session.commit()
        print(f"✓ Seeded {len(categories_data)} top-level categories and {len(electronics_subcategories)} subcategories")


async def main():
    """Run all seeding functions."""
    print("Starting database seeding...")

    try:
        await seed_shops()
        await seed_categories()
        print("\n✅ Database seeding completed successfully!")
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
