"""Verify DealHawk setup and configuration.

This script checks that all components are properly configured:
- Database connection
- Required extensions (pg_trgm)
- Seeded data (categories, shops)
- API credentials (optional)

Usage:
    python scripts/verify_setup.py
"""

import asyncio
import sys
import os

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select, text

from app.db.session import async_session_factory
from app.models.shop import Shop
from app.models.category import Category
from app.config import settings


async def verify_database_connection():
    """Verify database connection is working."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"    PostgreSQL version: {version.split(',')[0]}")
            return True
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False


async def verify_extensions():
    """Verify required PostgreSQL extensions are installed."""
    required_extensions = ["pg_trgm", "uuid-ossp"]
    all_ok = True

    async with async_session_factory() as session:
        for ext in required_extensions:
            try:
                result = await session.execute(
                    text("SELECT 1 FROM pg_extension WHERE extname = :ext"),
                    {"ext": ext}
                )
                if result.scalar():
                    print(f"    ✅ {ext} extension installed")
                else:
                    print(f"    ❌ {ext} extension NOT installed")
                    all_ok = False
            except Exception as e:
                print(f"    ❌ Error checking {ext}: {e}")
                all_ok = False

    return all_ok


async def verify_tables():
    """Verify all required tables exist."""
    required_tables = [
        "shops",
        "categories",
        "products",
        "deals",
        "price_history",
        "scraper_jobs",
        "search_keywords",
    ]
    all_ok = True

    async with async_session_factory() as session:
        for table in required_tables:
            try:
                result = await session.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_name = :table"
                    ),
                    {"table": table}
                )
                if result.scalar():
                    print(f"    ✅ {table} table exists")
                else:
                    print(f"    ❌ {table} table NOT found")
                    all_ok = False
            except Exception as e:
                print(f"    ❌ Error checking {table}: {e}")
                all_ok = False

    return all_ok


async def verify_seeded_data():
    """Verify base data has been seeded."""
    all_ok = True

    async with async_session_factory() as session:
        # Check categories
        result = await session.execute(select(Category))
        categories = result.scalars().all()
        category_count = len(categories)

        if category_count > 0:
            print(f"    ✅ {category_count} categories found")
        else:
            print(f"    ⚠️  No categories found (run: python scripts/seed_categories.py)")
            all_ok = False

        # Check shops
        result = await session.execute(select(Shop))
        shops = result.scalars().all()
        shop_count = len(shops)

        if shop_count > 0:
            print(f"    ✅ {shop_count} shops found")
        else:
            print(f"    ⚠️  No shops found (run: python scripts/seed_shops.py)")
            all_ok = False

    return all_ok


def verify_api_credentials():
    """Verify API credentials are configured (non-blocking)."""
    credentials = {
        "Naver Shopping": (settings.NAVER_CLIENT_ID, settings.NAVER_CLIENT_SECRET),
        "Coupang Partners": (settings.COUPANG_ACCESS_KEY, settings.COUPANG_SECRET_KEY),
        "11st": (settings.ELEVEN_ST_API_KEY,),
        "AliExpress": (settings.ALIEXPRESS_APP_KEY, settings.ALIEXPRESS_APP_SECRET),
        "Amazon": (settings.AMAZON_ACCESS_KEY, settings.AMAZON_SECRET_KEY, settings.AMAZON_PARTNER_TAG),
        "eBay": (settings.EBAY_CLIENT_ID, settings.EBAY_CLIENT_SECRET),
    }

    configured_count = 0
    for platform, creds in credentials.items():
        if all(creds):
            print(f"    ✅ {platform} API configured")
            configured_count += 1
        else:
            print(f"    ⚠️  {platform} API not configured (optional)")

    return configured_count > 0


def verify_environment():
    """Verify environment variables."""
    required_vars = {
        "DATABASE_URL": settings.DATABASE_URL,
        "REDIS_URL": settings.REDIS_URL,
    }

    all_ok = True
    for var_name, var_value in required_vars.items():
        if var_value:
            # Mask sensitive parts
            masked = var_value
            if "@" in masked:
                # Mask password in connection string
                parts = masked.split("@")
                user_pass = parts[0].split("//")[1]
                if ":" in user_pass:
                    user, _ = user_pass.split(":", 1)
                    masked = masked.replace(user_pass, f"{user}:****")
            print(f"    ✅ {var_name} = {masked}")
        else:
            print(f"    ❌ {var_name} NOT SET")
            all_ok = False

    return all_ok


async def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("  DealHawk Setup Verification")
    print("=" * 70 + "\n")

    checks = []

    # 1. Environment variables
    print("📋 Checking environment variables...")
    checks.append(verify_environment())
    print()

    # 2. Database connection
    print("🔌 Checking database connection...")
    checks.append(await verify_database_connection())
    print()

    # 3. PostgreSQL extensions
    print("🔧 Checking PostgreSQL extensions...")
    checks.append(await verify_extensions())
    print()

    # 4. Database tables
    print("📊 Checking database tables...")
    checks.append(await verify_tables())
    print()

    # 5. Seeded data
    print("🌱 Checking seeded data...")
    checks.append(await verify_seeded_data())
    print()

    # 6. API credentials (optional)
    print("🔑 Checking API credentials (optional)...")
    verify_api_credentials()
    print()

    # Summary
    print("=" * 70)
    required_checks = checks[:5]  # First 5 checks are required
    if all(required_checks):
        print("  ✅ All Required Checks Passed!")
        print("=" * 70)
        print("\n🎉 Your DealHawk setup is ready!")
        print("\n📋 Next Steps:")
        print("   1. Start the backend: cd backend && uvicorn app.main:app --reload")
        print("   2. Visit API docs: http://localhost:8000/docs")
        print("   3. Test a scraper: python scripts/run_scraper.py --shop naver")
        print()
        return 0
    else:
        print("  ❌ Some Checks Failed")
        print("=" * 70)
        print("\n🔧 Troubleshooting:")

        if not checks[0]:
            print("   - Check your .env file in backend/")
            print("   - Copy from .env.example if needed")

        if not checks[1]:
            print("   - Make sure PostgreSQL is running: docker-compose up -d postgres")
            print("   - Check DATABASE_URL in .env")

        if not checks[2]:
            print("   - Run: docker-compose down -v && docker-compose up -d postgres")
            print("   - This will recreate the database with extensions")

        if not checks[3]:
            print("   - Run migrations: cd backend && alembic upgrade head")

        if not checks[4]:
            print("   - Run seed scripts: python scripts/seed_all.py")

        print()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
