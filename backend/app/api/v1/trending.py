"""Trending API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import ApiResponse, TrendingKeywordResponse, RecentKeywordResponse
from app.services.search_service import SearchService
from app.services.cache_service import get_cache

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def get_trending(
    limit: int = Query(10, ge=1, le=50, description="Number of trending keywords to return"),
    db: AsyncSession = Depends(get_db),
):
    """Get trending search keywords.

    Returns the most frequently searched keywords, useful for displaying
    popular searches on the homepage or autocomplete suggestions.

    This endpoint is cached for 120 seconds (2 minutes).
    """
    # Try to get from cache
    cache = await get_cache()
    cache_key = f"trending:limit={limit}"

    cached = await cache.get(cache_key)
    if cached:
        return ApiResponse.model_validate_json(cached)

    # Cache miss - fetch from database
    service = SearchService(db)
    trending = await service.get_trending_keywords(limit=limit)

    response = ApiResponse(
        status="success",
        data=[TrendingKeywordResponse(**kw) for kw in trending],
    )

    # Cache the response for 120 seconds (2 minutes)
    await cache.set(cache_key, response.model_dump_json(), ttl=120)

    return response


@router.get("/recent", response_model=ApiResponse)
async def get_recent_searches(
    limit: int = Query(10, ge=1, le=50, description="Number of recent keywords to return"),
    db: AsyncSession = Depends(get_db),
):
    """Get recently searched keywords.

    Returns the most recently searched keywords with their search counts and timestamps.
    """
    service = SearchService(db)
    recent = await service.get_recent_keywords(limit=limit)

    return ApiResponse(
        status="success",
        data=[RecentKeywordResponse(**kw) for kw in recent],
    )
