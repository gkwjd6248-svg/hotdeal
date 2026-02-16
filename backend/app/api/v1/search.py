"""Search API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import ApiResponse, DealResponse, PaginationMeta
from app.services.search_service import SearchService

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def search(
    q: str = Query("", description="Search query", min_length=1),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category slug"),
    shop: Optional[str] = Query(None, description="Filter by shop slug"),
    sort_by: str = Query("relevance", regex="^(relevance|score|newest)$", description="Sort method"),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across products and deals.

    Searches deal titles using PostgreSQL's trigram similarity matching,
    which supports fuzzy Korean text search.

    Sort options:
    - relevance: Best matching results first (AI score as proxy)
    - score: Highest AI score first
    - newest: Most recently created deals first
    """
    if not q or not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query 'q' cannot be empty",
        )

    service = SearchService(db)
    deals, total = await service.search_deals(
        query=q,
        page=page,
        limit=limit,
        category_slug=category,
        shop_slug=shop,
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


@router.get("/advanced", response_model=ApiResponse)
async def advanced_search(
    q: str = Query("", description="Search query", min_length=1),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum AI score"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    category: Optional[str] = Query(None, description="Filter by category slug"),
    shop: Optional[str] = Query(None, description="Filter by shop slug"),
    db: AsyncSession = Depends(get_db),
):
    """Advanced search with additional filters.

    Provides more granular filtering options including price range and AI score thresholds.
    """
    if not q or not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query 'q' cannot be empty",
        )

    service = SearchService(db)
    deals, total = await service.search_deals_advanced(
        query=q,
        page=page,
        limit=limit,
        min_score=min_score,
        max_price=max_price,
        category_slug=category,
        shop_slug=shop,
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
