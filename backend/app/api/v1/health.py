"""Health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import HealthCheckResponse
from app.services.cache_service import get_cache

router = APIRouter()


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
