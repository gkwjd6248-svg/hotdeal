"""Products API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import ApiResponse, ProductResponse, ProductDetailResponse, PaginationMeta, PriceHistoryPoint
from app.services.product_service import ProductService

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_products(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    shop_id: Optional[str] = Query(None, description="Filter by shop UUID"),
    category_id: Optional[str] = Query(None, description="Filter by category UUID"),
    active_only: bool = Query(True, description="Only return active products"),
    db: AsyncSession = Depends(get_db),
):
    """List products with pagination, filtering, and sorting.

    Returns all products from the catalog, ordered by most recently scraped.
    """
    service = ProductService(db)

    # Parse UUIDs if provided
    shop_uuid = UUID(shop_id) if shop_id else None
    category_uuid = UUID(category_id) if category_id else None

    products, total = await service.get_products(
        page=page,
        limit=limit,
        shop_id=shop_uuid,
        category_id=category_uuid,
        is_active=active_only,
    )

    total_pages = (total + limit - 1) // limit if total > 0 else 0

    return ApiResponse(
        status="success",
        data=[ProductResponse.model_validate(p) for p in products],
        meta=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get("/{product_id}", response_model=ApiResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get product details by ID.

    Returns full product information with current deals and related data.
    """
    service = ProductService(db)
    product = await service.get_product_by_id(product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return ApiResponse(
        status="success",
        data=ProductDetailResponse.model_validate(product),
    )


@router.get("/{product_id}/price-history", response_model=ApiResponse)
async def get_price_history(
    product_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
):
    """Get price history for a product.

    Returns historical price data points for the specified time period.
    """
    service = ProductService(db)

    # Verify product exists
    product = await service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get price history
    history = await service.get_price_history(product_id, days=days)

    return ApiResponse(
        status="success",
        data=[PriceHistoryPoint.model_validate(h) for h in history],
    )


@router.get("/{product_id}/price-statistics", response_model=ApiResponse)
async def get_price_statistics(
    product_id: UUID,
    days: int = Query(90, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Get price statistics for a product.

    Returns min, max, average, and current price from historical data.
    """
    service = ProductService(db)

    # Verify product exists
    product = await service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get statistics
    stats = await service.get_price_statistics(product_id, days=days)

    if not stats:
        raise HTTPException(
            status_code=404,
            detail="Insufficient price history data to compute statistics",
        )

    return ApiResponse(status="success", data=stats)
