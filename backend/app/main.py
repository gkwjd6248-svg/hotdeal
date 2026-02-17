"""DealHawk Backend -- FastAPI Application Entry Point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.config import settings
from app.db.session import async_session_factory, engine
import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

from app.scrapers.scheduler import ScraperScheduler
from app.scrapers.register_adapters import register_all_adapters
from app.scrapers.utils.browser_manager import get_browser_manager
from app.scrapers.utils.normalizer import CurrencyConverter
from app.services.cache_service import get_cache_service
from app.models.base import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: ScraperScheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    global scheduler

    # Startup
    logger.info("Starting DealHawk API server...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Auto-create tables on startup (safe for fresh deployments)
    try:
        # Import all models so they register with Base.metadata
        from app.models import shop, category, product, price_history, deal, scraper_job, search_keyword, user, comment, user_vote, price_alert

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created")

        # Create optional PostgreSQL-specific indexes (GIN trigram for search)
        if not settings.DATABASE_URL.startswith("sqlite"):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                    await conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_deals_title_trgm "
                        "ON deals USING gin (title gin_trgm_ops)"
                    ))
                    await conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_products_title_trgm "
                        "ON products USING gin (title gin_trgm_ops)"
                    ))
                    await conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_deals_ai_score_active "
                        "ON deals (ai_score) WHERE is_active = true"
                    ))
                logger.info("PostgreSQL GIN/partial indexes created")
            except Exception as idx_err:
                logger.warning(f"Could not create optional PG indexes (non-fatal): {idx_err}")

        # Seed initial data if empty
        from app.models.shop import Shop
        from app.models.category import Category
        async_sess = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_sess() as session:
            result = await session.execute(select(Shop).limit(1))
            if not result.scalar_one_or_none():
                logger.info("Seeding initial shops and categories...")
                shops = [
                    Shop(id=uuid.uuid4(), name="네이버 쇼핑", name_en="Naver Shopping", slug="naver", base_url="https://shopping.naver.com", adapter_type="api", is_active=True, scrape_interval_minutes=30, country="KR", currency="KRW"),
                    Shop(id=uuid.uuid4(), name="스팀", name_en="Steam", slug="steam", base_url="https://store.steampowered.com", adapter_type="api", is_active=True, scrape_interval_minutes=60, country="US", currency="USD"),
                    Shop(id=uuid.uuid4(), name="쿠팡", name_en="Coupang", slug="coupang", base_url="https://www.coupang.com", adapter_type="api", is_active=False, scrape_interval_minutes=30, country="KR", currency="KRW"),
                    Shop(id=uuid.uuid4(), name="11번가", name_en="11st", slug="11st", base_url="https://www.11st.co.kr", adapter_type="api", is_active=False, scrape_interval_minutes=30, country="KR", currency="KRW"),
                ]
                session.add_all(shops)
                categories = [
                    Category(id=uuid.uuid4(), name="PC/하드웨어", slug="pc-hardware", icon="Monitor", sort_order=1),
                    Category(id=uuid.uuid4(), name="노트북/모바일", slug="laptop-mobile", icon="Laptop", sort_order=2),
                    Category(id=uuid.uuid4(), name="게임/SW", slug="games-software", icon="Gamepad2", sort_order=3),
                    Category(id=uuid.uuid4(), name="가전/TV", slug="electronics-tv", icon="Tv", sort_order=4),
                    Category(id=uuid.uuid4(), name="생활/식품", slug="living-food", icon="ShoppingCart", sort_order=5),
                    Category(id=uuid.uuid4(), name="상품권/쿠폰", slug="voucher-coupon", icon="Ticket", sort_order=6),
                ]
                session.add_all(categories)
                await session.commit()
                logger.info("Seed data inserted")
    except Exception as e:
        logger.error(f"Database init failed: {e}", exc_info=True)

    # Register all scraper adapters
    logger.info("Registering scraper adapters...")
    register_all_adapters()

    # Start scraper scheduler (only in non-test environments)
    if settings.ENVIRONMENT != "test":
        logger.info("Initializing scraper scheduler...")
        scheduler = ScraperScheduler(async_session_factory)
        scheduler.start()

        # Load and schedule jobs for all active shops
        try:
            jobs_count = await scheduler.load_shop_jobs()
            logger.info(f"Scheduler started with {jobs_count} shop jobs")
        except Exception as e:
            logger.error(f"Failed to load shop jobs: {e}", exc_info=True)
    else:
        logger.info("Scheduler disabled (test environment)")

    # Initialize cache service (ensure connection is ready)
    try:
        cache = get_cache_service()
        cache_healthy = await cache.health_check()
        if cache_healthy:
            logger.info("Redis cache connected successfully")
        else:
            logger.warning("Redis cache connection failed (will operate without caching)")
    except Exception as e:
        logger.warning(f"Redis cache initialization failed: {e}")

    # Fetch live exchange rates on startup and schedule hourly refresh
    exchange_task = None
    try:
        await CurrencyConverter.refresh_rates()

        async def _refresh_rates_loop():
            while True:
                await asyncio.sleep(3600)
                await CurrencyConverter.refresh_rates()

        exchange_task = asyncio.create_task(_refresh_rates_loop())
        logger.info("Exchange rate refresh scheduled (hourly)")
    except Exception as e:
        logger.warning(f"Exchange rate fetch failed, using fallback rates: {e}")

    yield

    # Shutdown
    logger.info("Shutting down DealHawk API server...")

    # Stop scheduler
    if scheduler:
        logger.info("Stopping scraper scheduler...")
        scheduler.stop()

    # Stop browser manager (closes Playwright)
    try:
        browser_mgr = get_browser_manager()
        await browser_mgr.stop()
        logger.info("Browser manager stopped")
    except Exception as e:
        logger.warning(f"Error stopping browser manager: {e}")

    # Close cache connection
    try:
        cache = get_cache_service()
        await cache.close()
        logger.info("Redis cache connection closed")
    except Exception as e:
        logger.warning(f"Error closing cache: {e}")


app = FastAPI(
    title="DealHawk API",
    description="AI-driven E-commerce Deal Aggregator API",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "https://hotdeal-pi.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 router
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "DealHawk API",
        "version": "0.1.0",
        "description": "AI-driven E-commerce Deal Aggregator",
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/api/v1/health",
    }
