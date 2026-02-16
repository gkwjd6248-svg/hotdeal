"""Seed the shops table with all 18 supported shopping malls."""

import asyncio
import sys
import os

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.shop import Shop

SHOPS = [
    # Korean domestic - API based
    {
        "name": "쿠팡",
        "name_en": "Coupang",
        "slug": "coupang",
        "base_url": "https://www.coupang.com",
        "adapter_type": "api",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 30,
        "logo_url": "/images/shop-logos/coupang.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "네이버쇼핑",
        "name_en": "Naver Shopping",
        "slug": "naver",
        "base_url": "https://shopping.naver.com",
        "adapter_type": "api",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 30,
        "logo_url": "/images/shop-logos/naver.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "11번가",
        "name_en": "11st",
        "slug": "11st",
        "base_url": "https://www.11st.co.kr",
        "adapter_type": "api",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/11st.png",
        "is_active": True,
        "metadata_": {},
    },
    # Korean domestic - Scraping based
    {
        "name": "하이마트",
        "name_en": "Hi-Mart",
        "slug": "himart",
        "base_url": "https://www.e-himart.co.kr",
        "adapter_type": "scraper",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/himart.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "옥션",
        "name_en": "Auction",
        "slug": "auction",
        "base_url": "https://www.auction.co.kr",
        "adapter_type": "scraper",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/auction.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "지마켓",
        "name_en": "G-Market",
        "slug": "gmarket",
        "base_url": "https://www.gmarket.co.kr",
        "adapter_type": "scraper",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/gmarket.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "SSG",
        "name_en": "SSG.com",
        "slug": "ssg",
        "base_url": "https://www.ssg.com",
        "adapter_type": "scraper",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/ssg.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "롯데온",
        "name_en": "Lotte ON",
        "slug": "lotteon",
        "base_url": "https://www.lotteon.com",
        "adapter_type": "scraper",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/lotteon.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "인터파크",
        "name_en": "Interpark",
        "slug": "interpark",
        "base_url": "https://www.interpark.com",
        "adapter_type": "scraper",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/interpark.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "무신사",
        "name_en": "Musinsa",
        "slug": "musinsa",
        "base_url": "https://www.musinsa.com",
        "adapter_type": "scraper",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 120,
        "logo_url": "/images/shop-logos/musinsa.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "SSF",
        "name_en": "Samsung Fashion",
        "slug": "ssf",
        "base_url": "https://www.ssfshop.com",
        "adapter_type": "scraper",
        "country": "KR",
        "currency": "KRW",
        "scrape_interval_minutes": 120,
        "logo_url": "/images/shop-logos/ssf.png",
        "is_active": True,
        "metadata_": {},
    },
    # International - API based
    {
        "name": "알리익스프레스",
        "name_en": "AliExpress",
        "slug": "aliexpress",
        "base_url": "https://www.aliexpress.com",
        "adapter_type": "api",
        "country": "CN",
        "currency": "USD",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/aliexpress.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "아마존",
        "name_en": "Amazon",
        "slug": "amazon",
        "base_url": "https://www.amazon.com",
        "adapter_type": "api",
        "country": "US",
        "currency": "USD",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/amazon.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "이베이",
        "name_en": "eBay",
        "slug": "ebay",
        "base_url": "https://www.ebay.com",
        "adapter_type": "api",
        "country": "US",
        "currency": "USD",
        "scrape_interval_minutes": 60,
        "logo_url": "/images/shop-logos/ebay.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "스팀",
        "name_en": "Steam",
        "slug": "steam",
        "base_url": "https://store.steampowered.com",
        "adapter_type": "api",
        "country": "GLOBAL",
        "currency": "KRW",
        "scrape_interval_minutes": 120,
        "logo_url": "/images/shop-logos/steam.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "뉴에그",
        "name_en": "Newegg",
        "slug": "newegg",
        "base_url": "https://www.newegg.com",
        "adapter_type": "hybrid",
        "country": "US",
        "currency": "USD",
        "scrape_interval_minutes": 120,
        "logo_url": "/images/shop-logos/newegg.png",
        "is_active": True,
        "metadata_": {},
    },
    # International - Scraping based
    {
        "name": "타오바오",
        "name_en": "Taobao",
        "slug": "taobao",
        "base_url": "https://world.taobao.com",
        "adapter_type": "scraper",
        "country": "CN",
        "currency": "CNY",
        "scrape_interval_minutes": 120,
        "logo_url": "/images/shop-logos/taobao.png",
        "is_active": True,
        "metadata_": {},
    },
    {
        "name": "큐텐",
        "name_en": "Qoo10",
        "slug": "qoo10",
        "base_url": "https://www.qoo10.com",
        "adapter_type": "scraper",
        "country": "SG",
        "currency": "KRW",
        "scrape_interval_minutes": 90,
        "logo_url": "/images/shop-logos/qoo10.png",
        "is_active": True,
        "metadata_": {},
    },
]


async def seed_shops():
    """Seed all shops into the database.

    This function is idempotent - running it multiple times will not
    create duplicate shops. Shops are identified by their unique slug.
    """
    print(f"\n{'='*60}")
    print(f"  Seeding Shops Database")
    print(f"{'='*60}\n")

    added_count = 0
    skipped_count = 0

    async with async_session_factory() as session:
        for shop_data in SHOPS:
            # Check if shop already exists by slug
            result = await session.execute(
                select(Shop).where(Shop.slug == shop_data["slug"])
            )
            existing_shop = result.scalar_one_or_none()

            if existing_shop:
                print(f"  ⏭️  Shop '{shop_data['name']}' ({shop_data['slug']}) already exists, skipping")
                skipped_count += 1
                continue

            # Create new shop
            shop = Shop(**shop_data)
            session.add(shop)
            print(f"  ✅ Added shop: {shop_data['name']} ({shop_data['name_en']}) - {shop_data['adapter_type']}")
            added_count += 1

        # Commit all changes
        await session.commit()

    print(f"\n{'='*60}")
    print(f"  Seeding Complete")
    print(f"{'='*60}")
    print(f"  ✅ Added: {added_count} shops")
    print(f"  ⏭️  Skipped: {skipped_count} shops (already exist)")
    print(f"  📊 Total: {len(SHOPS)} shops in database\n")


if __name__ == "__main__":
    asyncio.run(seed_shops())
