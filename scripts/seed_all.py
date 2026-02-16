"""Run all seed scripts in the correct order.

This script seeds all base data needed for the DealHawk application:
1. Categories - Product categories
2. Shops - E-commerce platforms

Usage:
    python scripts/seed_all.py
"""

import asyncio
import sys
import os

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from seed_categories import seed_categories
from seed_shops import seed_shops


async def seed_all():
    """Run all seed scripts in the correct order."""
    print("\n" + "=" * 70)
    print("  DealHawk Database Seeding")
    print("=" * 70)
    print("\n🌱 Starting database seeding process...\n")

    try:
        # 1. Seed categories first (no dependencies)
        print("📁 Step 1: Seeding Categories...")
        await seed_categories()

        # 2. Seed shops (no dependencies)
        print("\n🏪 Step 2: Seeding Shops...")
        await seed_shops()

        # Success summary
        print("\n" + "=" * 70)
        print("  ✅ All Seeding Complete!")
        print("=" * 70)
        print("\n🎉 Database is ready for use!")
        print("\n📋 Next Steps:")
        print("   1. Start the backend server: cd backend && uvicorn app.main:app --reload")
        print("   2. Run a test scraper: python scripts/run_scraper.py --shop naver")
        print("   3. Check the API docs: http://localhost:8000/docs\n")

    except Exception as e:
        print("\n" + "=" * 70)
        print("  ❌ Seeding Failed")
        print("=" * 70)
        print(f"\n🔥 Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Troubleshooting:")
        print("   - Make sure PostgreSQL is running")
        print("   - Check your DATABASE_URL in .env")
        print("   - Run migrations first: cd backend && alembic upgrade head\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(seed_all())
