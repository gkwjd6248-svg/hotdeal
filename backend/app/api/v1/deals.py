"""Deals API endpoints."""

import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user, get_optional_user
from app.models.user import User
from app.schemas import ApiResponse, DealDetailResponse, DealResponse, PaginationMeta, VoteRequest
from app.services.deal_service import DealService
from app.services.product_service import ProductService
from app.services.vote_service import VoteService
from app.services.cache_service import get_cache, cache_key_for_deals, cache_key_for_top_deals, invalidate_deals_cache

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_deals(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category slug"),
    shop: Optional[str] = Query(None, description="Filter by shop slug"),
    sort_by: str = Query("newest", regex="^(newest|score|discount|views)$", description="Sort method"),
    min_discount: Optional[float] = Query(None, ge=0, le=100, description="Minimum discount percentage"),
    deal_type: Optional[str] = Query(None, description="Filter by deal type"),
    db: AsyncSession = Depends(get_db),
):
    """List active deals with pagination and filtering.

    Sort options:
    - newest: Most recently created deals first (default)
    - score: Highest AI score first
    - discount: Highest discount percentage first
    - views: Most viewed deals first

    This endpoint is cached for 30 seconds.
    """
    # Try to get from cache
    cache = await get_cache()
    cache_key = cache_key_for_deals(
        page=page,
        limit=limit,
        category_slug=category,
        shop_slug=shop,
        sort_by=sort_by,
        min_discount=min_discount,
        deal_type=deal_type,
    )

    cached = await cache.get(cache_key)
    if cached:
        return ApiResponse.model_validate_json(cached)

    # Cache miss - fetch from database
    service = DealService(db)
    deals, total = await service.get_deals(
        page=page,
        limit=limit,
        category_slug=category,
        shop_slug=shop,
        sort_by=sort_by,
        min_discount=min_discount,
        deal_type=deal_type,
    )

    total_pages = (total + limit - 1) // limit if total > 0 else 0

    response = ApiResponse(
        status="success",
        data=[DealResponse.model_validate(d) for d in deals],
        meta=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
        ),
    )

    # Cache the response for 30 seconds
    await cache.set(cache_key, response.model_dump_json(), ttl=30)

    return response


@router.get("/top", response_model=ApiResponse)
async def top_deals(
    limit: int = Query(20, ge=1, le=50, description="Number of top deals to return"),
    category: Optional[str] = Query(None, description="Filter by category slug"),
    db: AsyncSession = Depends(get_db),
):
    """Get top AI-scored deals.

    Returns the highest-quality deals based on AI scoring algorithm.
    Only includes deals with non-null AI scores.

    This endpoint is cached for 60 seconds.
    """
    # Try to get from cache
    cache = await get_cache()
    cache_key = cache_key_for_top_deals(limit=limit, category_slug=category)

    cached = await cache.get(cache_key)
    if cached:
        return ApiResponse.model_validate_json(cached)

    # Cache miss - fetch from database
    service = DealService(db)
    deals = await service.get_top_deals(limit=limit, category_slug=category)

    response = ApiResponse(
        status="success",
        data=[DealResponse.model_validate(d) for d in deals],
    )

    # Cache the response for 60 seconds
    await cache.set(cache_key, response.model_dump_json(), ttl=60)

    return response


@router.get("/{deal_id}", response_model=ApiResponse)
async def get_deal(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get deal details by ID.

    Includes full deal information, shop and category details,
    and price history for the associated product (last 30 days).

    Also increments the view count for this deal.
    """
    service = DealService(db)
    deal = await service.get_deal_by_id(deal_id)

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Get price history for the associated product
    product_service = ProductService(db)
    history = await product_service.get_price_history(deal.product_id, days=30)

    # Build response with price history
    deal_data = DealDetailResponse.model_validate(deal)
    deal_data.price_history = [
        {
            "price": float(h.price),
            "recorded_at": h.recorded_at.isoformat(),
        }
        for h in history
    ]

    return ApiResponse(status="success", data=deal_data)


@router.get("/{deal_id}/vote", response_model=ApiResponse)
async def get_vote_status(
    deal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's vote status for a deal."""
    service = VoteService(db)
    user_vote = await service.get_user_vote(deal_id, current_user.id)
    return ApiResponse(status="success", data={"user_vote": user_vote})


@router.post("/{deal_id}/vote", response_model=ApiResponse)
async def vote_on_deal(
    deal_id: UUID,
    vote: VoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Vote on a deal (upvote or downvote). Requires authentication.

    Voting the same type again toggles the vote off.
    Voting the opposite type switches the vote.
    """
    if vote.vote_type not in ["up", "down"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid vote_type. Must be 'up' or 'down'.",
        )

    service = VoteService(db)
    result = await service.vote(deal_id, current_user.id, vote.vote_type)

    if result is None:
        raise HTTPException(status_code=404, detail="Deal not found")

    return ApiResponse(status="success", data=result)
