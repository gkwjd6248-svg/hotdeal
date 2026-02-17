"""DealHawk Backend -- FastAPI Application Entry Point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.config import settings
from app.db.session import async_session_factory
import asyncio

from app.scrapers.scheduler import ScraperScheduler
from app.scrapers.register_adapters import register_all_adapters
from app.scrapers.utils.browser_manager import get_browser_manager
from app.scrapers.utils.normalizer import CurrencyConverter
from app.services.cache_service import get_cache_service

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
