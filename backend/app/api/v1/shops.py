"""Shops API endpoints."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.shop import Shop
from app.models.deal import Deal
from app.schemas import ApiResponse, ShopResponse, DealResponse, PaginationMeta
from app.services.deal_service import DealService
from app.services.cache_service import get_cache

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_shops(
    active_only: bool = Query(True, description="Only return active shops"),
    db: AsyncSession = Depends(get_db),
):
    """List all supported shopping platforms.

    Returns all shops with their basic information and active deal counts.

    This endpoint is cached for 300 seconds (5 minutes).
    """
    # Try to get from cache
    cache = await get_cache()
    cache_key = f"shops:active_only={active_only}"

    cached = await cache.get(cache_key)
    if cached:
        return ApiResponse.model_validate_json(cached)

    # Cache miss - fetch from database
    query = select(Shop).order_by(Shop.name)

    if active_only:
        query = query.where(Shop.is_active == True)

    result = await db.execute(query)
    shops = result.scalars().all()

    # Count active deals for each shop
    shop_responses = []
    for shop in shops:
        deal_count_result = await db.execute(
            select(func.count(Deal.id))
            .where(Deal.shop_id == shop.id)
            .where(Deal.is_active == True)
        )
        deal_count = deal_count_result.scalar() or 0

        shop_data = ShopResponse.model_validate(shop)
        shop_data.deal_count = deal_count
        shop_responses.append(shop_data)

    response = ApiResponse(status="success", data=shop_responses)

    # Cache the response for 300 seconds (5 minutes)
    await cache.set(cache_key, response.model_dump_json(), ttl=300)

    return response


@router.get("/{slug}", response_model=ApiResponse)
async def get_shop(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get shop details by slug.

    Returns detailed information about a specific shop including deal count.
    """
    result = await db.execute(
        select(Shop).where(Shop.slug == slug)
    )
    shop = result.scalar_one_or_none()

    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop '{slug}' not found")

    # Count active deals
    deal_count_result = await db.execute(
        select(func.count(Deal.id))
        .where(Deal.shop_id == shop.id)
        .where(Deal.is_active == True)
    )
    deal_count = deal_count_result.scalar() or 0

    shop_data = ShopResponse.model_validate(shop)
    shop_data.deal_count = deal_count

    return ApiResponse(status="success", data=shop_data)


@router.get("/{slug}/deals", response_model=ApiResponse)
async def get_shop_deals(
    slug: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("newest", regex="^(newest|score|discount|views)$", description="Sort method"),
    db: AsyncSession = Depends(get_db),
):
    """Get deals from a specific shop.

    Returns paginated deals filtered by shop slug.
    """
    # Verify shop exists
    result = await db.execute(
        select(Shop).where(Shop.slug == slug)
    )
    shop = result.scalar_one_or_none()

    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop '{slug}' not found")

    # Get deals using DealService
    service = DealService(db)
    deals, total = await service.get_deals(
        page=page,
        limit=limit,
        shop_slug=slug,
        sort_by=sort_by,
    )

    total_pages = (total + limit - 1) // limit if total > 0 else 0

    return ApiResponse(
        status="success",
        data=[DealResponse.model_validate(d) for d in deals],
        meta=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
        ),
    )
