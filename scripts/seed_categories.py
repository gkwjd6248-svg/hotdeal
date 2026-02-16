"""Seed the categories table with product categories."""

import asyncio
import sys
import os

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.category import Category

CATEGORIES = [
    {
        "name": "전체",
        "name_en": "All",
        "slug": "all",
        "icon": "layout-grid",
        "sort_order": 0,
    },
    {
        "name": "PC/하드웨어",
        "name_en": "PC/Hardware",
        "slug": "pc-hardware",
        "icon": "monitor",
        "sort_order": 1,
    },
    {
        "name": "상품권/쿠폰",
        "name_en": "Gift Cards/Coupons",
        "slug": "gift-cards",
        "icon": "ticket",
        "sort_order": 2,
    },
    {
        "name": "게임/SW",
        "name_en": "Games/Software",
        "slug": "games-software",
        "icon": "gamepad-2",
        "sort_order": 3,
    },
    {
        "name": "노트북/모바일",
        "name_en": "Laptop/Mobile",
        "slug": "laptop-mobile",
        "icon": "laptop",
        "sort_order": 4,
    },
    {
        "name": "가전/TV",
        "name_en": "Electronics/TV",
        "slug": "electronics-tv",
        "icon": "tv",
        "sort_order": 5,
    },
    {
        "name": "생활/식품",
        "name_en": "Living/Food",
        "slug": "living-food",
        "icon": "shopping-basket",
        "sort_order": 6,
    },
    {
        "name": "패션/의류",
        "name_en": "Fashion/Clothing",
        "slug": "fashion-clothing",
        "icon": "shirt",
        "sort_order": 7,
    },
    {
        "name": "뷰티/화장품",
        "name_en": "Beauty/Cosmetics",
        "slug": "beauty-cosmetics",
        "icon": "sparkles",
        "sort_order": 8,
    },
    {
        "name": "가구/인테리어",
        "name_en": "Furniture/Interior",
        "slug": "furniture-interior",
        "icon": "armchair",
        "sort_order": 9,
    },
]


async def seed_categories():
    """Seed all categories into the database.

    This function is idempotent - running it multiple times will not
    create duplicate categories. Categories are identified by their unique slug.
    """
    print(f"\n{'='*60}")
    print(f"  Seeding Categories Database")
    print(f"{'='*60}\n")

    added_count = 0
    skipped_count = 0

    async with async_session_factory() as session:
        for cat_data in CATEGORIES:
            # Check if category already exists by slug
            result = await session.execute(
                select(Category).where(Category.slug == cat_data["slug"])
            )
            existing_category = result.scalar_one_or_none()

            if existing_category:
                print(f"  ⏭️  Category '{cat_data['name']}' ({cat_data['slug']}) already exists, skipping")
                skipped_count += 1
                continue

            # Create new category
            category = Category(**cat_data)
            session.add(category)
            print(f"  ✅ Added category: {cat_data['name']} ({cat_data['name_en']}) - icon: {cat_data['icon']}")
            added_count += 1

        # Commit all changes
        await session.commit()

    print(f"\n{'='*60}")
    print(f"  Seeding Complete")
    print(f"{'='*60}")
    print(f"  ✅ Added: {added_count} categories")
    print(f"  ⏭️  Skipped: {skipped_count} categories (already exist)")
    print(f"  📊 Total: {len(CATEGORIES)} categories in database\n")


if __name__ == "__main__":
    asyncio.run(seed_categories())
