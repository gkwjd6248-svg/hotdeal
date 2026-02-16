"""Categories API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models.category import Category
from app.models.deal import Deal
from app.schemas import ApiResponse, CategoryResponse, CategoryTreeResponse, DealResponse, PaginationMeta
from app.services.deal_service import DealService
from app.services.cache_service import get_cache

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_categories(
    tree: bool = Query(False, description="Return hierarchical tree structure"),
    db: AsyncSession = Depends(get_db),
):
    """List all categories.

    By default returns a flat list of all categories.
    Set tree=true to get a hierarchical tree structure with nested children.

    This endpoint is cached for 300 seconds (5 minutes).
    """
    # Try to get from cache
    cache = await get_cache()
    cache_key = f"categories:tree={tree}"

    cached = await cache.get(cache_key)
    if cached:
        return ApiResponse.model_validate_json(cached)

    # Cache miss - fetch from database
    if tree:
        # Get root categories (no parent) with their children loaded recursively
        result = await db.execute(
            select(Category)
            .options(selectinload(Category.children))
            .where(Category.parent_id.is_(None))
            .order_by(Category.sort_order)
        )
        categories = result.scalars().all()

        # Build tree structure recursively
        async def build_tree(cat: Category) -> CategoryTreeResponse:
            # Count deals for this category
            deal_count_result = await db.execute(
                select(func.count(Deal.id))
                .where(Deal.category_id == cat.id)
                .where(Deal.is_active == True)
            )
            deal_count = deal_count_result.scalar() or 0

            # Recursively build children
            children = []
            if cat.children:
                for child in sorted(cat.children, key=lambda c: c.sort_order):
                    children.append(await build_tree(child))

            cat_data = CategoryTreeResponse.model_validate(cat)
            cat_data.deal_count = deal_count
            cat_data.children = children
            return cat_data

        tree_data = [await build_tree(cat) for cat in categories]

        response = ApiResponse(status="success", data=tree_data)
    else:
        # Flat list of all categories
        result = await db.execute(
            select(Category).order_by(Category.sort_order)
        )
        categories = result.scalars().all()

        # Count deals for each category
        category_responses = []
        for cat in categories:
            deal_count_result = await db.execute(
                select(func.count(Deal.id))
                .where(Deal.category_id == cat.id)
                .where(Deal.is_active == True)
            )
            deal_count = deal_count_result.scalar() or 0

            cat_data = CategoryResponse.model_validate(cat)
            cat_data.deal_count = deal_count
            category_responses.append(cat_data)

        response = ApiResponse(status="success", data=category_responses)

    # Cache the response for 300 seconds (5 minutes)
    await cache.set(cache_key, response.model_dump_json(), ttl=300)

    return response


@router.get("/{slug}/deals", response_model=ApiResponse)
async def get_category_deals(
    slug: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("newest", regex="^(newest|score|discount|views)$", description="Sort method"),
    db: AsyncSession = Depends(get_db),
):
    """Get deals in a specific category.

    Returns paginated deals filtered by category slug.
    """
    # Verify category exists
    result = await db.execute(
        select(Category).where(Category.slug == slug)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail=f"Category '{slug}' not found")

    # Get deals using DealService
    service = DealService(db)
    deals, total = await service.get_deals(
        page=page,
        limit=limit,
        category_slug=slug,
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
