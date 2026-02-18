"""Health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import HealthCheckResponse
from app.services.cache_service import get_cache
from app.config import settings

router = APIRouter()


@router.get("/debug/scrape/{shop_slug}")
async def debug_scrape(shop_slug: str, db: AsyncSession = Depends(get_db)):
    """Debug endpoint to manually trigger a scrape and see results."""
    if not settings.DEBUG:
        return {"error": "only available in debug mode"}
    try:
        from app.scrapers.scraper_service import ScraperService
        service = ScraperService(db)
        stats = await service.run_adapter(shop_slug)
        return {"status": "success", "stats": stats}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@router.post("/debug/cleanup-low-score-deals")
async def debug_cleanup_low_score_deals(
    threshold: float = 35.0,
    db: AsyncSession = Depends(get_db),
):
    """Debug endpoint to deactivate all active deals with AI score below threshold.

    Useful for one-time cleanup of pre-threshold deals that were created before
    the score gate was introduced.  Only available in DEBUG mode.

    Args:
        threshold: Minimum qualifying score (default: 35.0 = DEAL_THRESHOLD)
    """
    if not settings.DEBUG:
        return {"error": "only available in debug mode"}
    try:
        from decimal import Decimal
        from app.services.deal_service import DealService
        service = DealService(db)
        count = await service.deactivate_low_score_deals(threshold=Decimal(str(threshold)))
        return {"status": "success", "deals_deactivated": count, "threshold": threshold}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@router.get("/debug/config")
async def debug_config():
    """Debug endpoint to check config (redacted)."""
    if not settings.DEBUG:
        return {"error": "only available in debug mode"}
    return {
        "naver_client_id_set": bool(settings.NAVER_CLIENT_ID),
        "naver_client_id_length": len(settings.NAVER_CLIENT_ID),
        "naver_secret_set": bool(settings.NAVER_CLIENT_SECRET),
        "environment": settings.ENVIRONMENT,
        "database_url_prefix": settings.DATABASE_URL[:30] + "...",
    }


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Return service health status.

    Checks connectivity to:
    - Database (PostgreSQL)
    - Redis (cache)

    Returns 200 if all services are healthy, otherwise returns error details.
    """
    services = {}

    # Check database connectivity
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    services["database"] = db_status

    # Check Redis connectivity
    try:
        cache = await get_cache()
        redis_healthy = await cache.health_check()
        redis_status = "ok" if redis_healthy else "error: ping failed"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    services["redis"] = redis_status

    # Overall status
    overall_status = "ok" if all(s == "ok" for s in services.values()) else "degraded"

    return HealthCheckResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
        services=services,
    )
