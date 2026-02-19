"""External scraper ingest endpoint.

Local Playwright scrapers (running on a developer machine or a dedicated
scraping host) POST their results here.  The endpoint authenticates via a
shared API key and then runs each submitted deal through the exact same
processing pipeline used by the internal scraper service:

  1. Resolve shop by slug
  2. Resolve / auto-create category from category_hint
  3. Upsert product  (ProductService.upsert_product)
  4. Record price history (done inside ProductService)
  5. Compute AI score and create / update deal  (DealService.create_or_update_deal)

Deals whose AI score falls below the configured threshold are still saved as
products + price history, but no Deal row is created (same behaviour as the
internal pipeline).

Security model
--------------
A single pre-shared key (``INGEST_API_KEY`` env var) is used.  This is a
secret-in-body pattern (rather than Authorization header) so that the local
scraper only needs a plain HTTP POST with a JSON body—no extra header
management required.  The key is compared with ``secrets.compare_digest`` to
avoid timing-oracle attacks.
"""

import secrets
from decimal import Decimal
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.shop import Shop
from app.schemas.ingest import IngestRequest, IngestResponse, IngestStats
from app.scrapers.base import NormalizedDeal, NormalizedProduct
from app.scrapers.scraper_service import ScraperService

router = APIRouter()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verify_api_key(submitted_key: str) -> None:
    """Raise HTTP 403 if the submitted key does not match INGEST_API_KEY.

    Uses ``secrets.compare_digest`` to prevent timing attacks.

    Args:
        submitted_key: The api_key field from the request body.

    Raises:
        HTTPException: 403 Forbidden when the key is empty, not configured,
            or does not match.
    """
    configured_key: str = settings.INGEST_API_KEY

    # Reject immediately when the server has no key configured.  This prevents
    # the endpoint from being open by default on a misconfigured deployment.
    if not configured_key:
        logger.warning("ingest_api_key_not_configured")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ingest endpoint is disabled (INGEST_API_KEY not configured)",
        )

    # Constant-time comparison
    if not secrets.compare_digest(submitted_key.encode(), configured_key.encode()):
        logger.warning("ingest_api_key_rejected")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


def _to_normalized_deal(item: "IngestDealItem", shop_slug: str) -> NormalizedDeal:  # noqa: F821
    """Convert a single IngestDealItem into a NormalizedDeal dataclass.

    The NormalizedDeal wraps a NormalizedProduct, mirroring the structure
    produced by every internal scraper adapter.

    Args:
        item: Validated IngestDealItem from the request body.
        shop_slug: Used only for context / logging; not stored on the dataclass.

    Returns:
        NormalizedDeal ready to be passed to ScraperService.process_deals.
    """
    deal_price = Decimal(str(item.deal_price))
    original_price: Optional[Decimal] = (
        Decimal(str(item.original_price)) if item.original_price is not None else None
    )

    product = NormalizedProduct(
        external_id=item.external_id,
        title=item.title,
        current_price=deal_price,
        product_url=item.deal_url,
        original_price=original_price,
        currency="KRW",
        image_url=item.image_url,
        brand=item.brand,
        category_hint=item.category_hint,
        description=item.description,
        # Carry extra scraper-supplied metadata through to the JSONB column.
        metadata=item.metadata,
    )

    return NormalizedDeal(
        product=product,
        deal_price=deal_price,
        title=item.title,
        deal_url=item.deal_url,
        original_price=original_price,
        deal_type=item.deal_type,
        description=item.description,
        image_url=item.image_url,
        # starts_at / expires_at are not exposed in the ingest schema because
        # local scrapers rarely have reliable expiry data.  Extend the schema
        # here if that changes.
        metadata=item.metadata,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/deals",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest deals from an external local scraper",
    description=(
        "Authenticated endpoint for local Playwright scrapers to push scraped "
        "deal data to the backend.  Each deal is processed through the same "
        "pipeline as internally-scraped deals: product upsert, price history "
        "recording, AI scoring, and deal creation / deactivation."
    ),
    responses={
        403: {"description": "API key missing or incorrect"},
        422: {"description": "Request body validation failed"},
    },
    tags=["ingest"],
)
async def ingest_deals(
    body: IngestRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Accept a batch of scraped deals from an external local scraper.

    The request body must contain:
    - ``api_key``: shared secret matching ``INGEST_API_KEY`` on the server
    - ``shop_slug``: must match an existing, active shop in the database
    - ``deals``: list of 1-N deal objects

    Each deal is individually error-isolated; a failure on one item does not
    abort the rest of the batch.  The ``errors`` field in the response counts
    per-item failures.

    Returns processing statistics reflecting what was written to the database.
    """
    # --- Authentication ---
    _verify_api_key(body.api_key)

    log = logger.bind(shop_slug=body.shop_slug, received=len(body.deals))
    log.info("ingest_request_received")

    # --- Convert payload to NormalizedDeal objects ---
    normalized: list[NormalizedDeal] = []
    conversion_errors = 0

    for idx, item in enumerate(body.deals):
        try:
            normalized.append(_to_normalized_deal(item, body.shop_slug))
        except Exception as exc:
            conversion_errors += 1
            log.error(
                "ingest_deal_conversion_failed",
                index=idx,
                external_id=item.external_id,
                error=str(exc),
            )
            # Continue with remaining items

    # --- Process through existing pipeline ---
    service = ScraperService(db)

    # process_deals raises ValueError if shop_slug is unknown or inactive.
    # Surface that as a 422 so the local scraper knows immediately.
    try:
        raw_stats = await service.process_deals(normalized, body.shop_slug)
    except ValueError as exc:
        log.error("ingest_shop_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # --- Build response ---
    # raw_stats comes from ScraperService.process_deals which tracks:
    #   deals_fetched, products_created, products_updated,
    #   deals_created, deals_updated, deals_skipped, deals_deactivated, errors

    total_errors = raw_stats.get("errors", 0) + conversion_errors
    total_skipped = (
        raw_stats.get("deals_skipped", 0) + raw_stats.get("deals_deactivated", 0)
    )

    stats = IngestStats(
        received=len(body.deals),
        products_created=raw_stats.get("products_created", 0),
        products_updated=raw_stats.get("products_updated", 0),
        deals_created=raw_stats.get("deals_created", 0),
        deals_skipped=total_skipped,
        errors=total_errors,
    )

    log.info(
        "ingest_complete",
        products_created=stats.products_created,
        products_updated=stats.products_updated,
        deals_created=stats.deals_created,
        deals_skipped=stats.deals_skipped,
        errors=stats.errors,
    )

    return IngestResponse(status="success", stats=stats)


# ---------------------------------------------------------------------------
# Shop seed endpoint
# ---------------------------------------------------------------------------

# Complete list of all 17 supported shops
ALL_SHOPS: List[Dict[str, Any]] = [
    # --- Korean API-based ---
    {"name": "네이버 쇼핑", "name_en": "Naver Shopping", "slug": "naver", "base_url": "https://shopping.naver.com", "adapter_type": "api", "scrape_interval_minutes": 30, "country": "KR", "currency": "KRW"},
    {"name": "쿠팡", "name_en": "Coupang", "slug": "coupang", "base_url": "https://www.coupang.com", "adapter_type": "api", "scrape_interval_minutes": 60, "country": "KR", "currency": "KRW"},
    {"name": "11번가", "name_en": "11st", "slug": "11st", "base_url": "https://www.11st.co.kr", "adapter_type": "api", "scrape_interval_minutes": 60, "country": "KR", "currency": "KRW"},
    # --- Korean scraper-based ---
    {"name": "G마켓", "name_en": "Gmarket", "slug": "gmarket", "base_url": "https://www.gmarket.co.kr", "adapter_type": "scraper", "scrape_interval_minutes": 120, "country": "KR", "currency": "KRW"},
    {"name": "옥션", "name_en": "Auction", "slug": "auction", "base_url": "https://www.auction.co.kr", "adapter_type": "scraper", "scrape_interval_minutes": 120, "country": "KR", "currency": "KRW"},
    {"name": "SSG닷컴", "name_en": "SSG", "slug": "ssg", "base_url": "https://www.ssg.com", "adapter_type": "scraper", "scrape_interval_minutes": 120, "country": "KR", "currency": "KRW"},
    {"name": "하이마트", "name_en": "Himart", "slug": "himart", "base_url": "https://www.e-himart.co.kr", "adapter_type": "scraper", "scrape_interval_minutes": 120, "country": "KR", "currency": "KRW"},
    {"name": "롯데온", "name_en": "Lotteon", "slug": "lotteon", "base_url": "https://www.lotteon.com", "adapter_type": "scraper", "scrape_interval_minutes": 120, "country": "KR", "currency": "KRW"},
    {"name": "인터파크", "name_en": "Interpark", "slug": "interpark", "base_url": "https://www.interpark.com", "adapter_type": "scraper", "is_active": False, "scrape_interval_minutes": 120, "country": "KR", "currency": "KRW"},
    {"name": "무신사", "name_en": "Musinsa", "slug": "musinsa", "base_url": "https://www.musinsa.com", "adapter_type": "scraper", "scrape_interval_minutes": 120, "country": "KR", "currency": "KRW"},
    {"name": "SSF샵", "name_en": "SSF Shop", "slug": "ssf", "base_url": "https://www.ssfshop.com", "adapter_type": "scraper", "scrape_interval_minutes": 120, "country": "KR", "currency": "KRW"},
    # --- International API-based ---
    {"name": "스팀", "name_en": "Steam", "slug": "steam", "base_url": "https://store.steampowered.com", "adapter_type": "api", "scrape_interval_minutes": 60, "country": "US", "currency": "USD"},
    {"name": "알리익스프레스", "name_en": "AliExpress", "slug": "aliexpress", "base_url": "https://www.aliexpress.com", "adapter_type": "api", "scrape_interval_minutes": 180, "country": "CN", "currency": "USD"},
    {"name": "아마존", "name_en": "Amazon", "slug": "amazon", "base_url": "https://www.amazon.com", "adapter_type": "api", "scrape_interval_minutes": 180, "country": "US", "currency": "USD"},
    {"name": "이베이", "name_en": "eBay", "slug": "ebay", "base_url": "https://www.ebay.com", "adapter_type": "api", "scrape_interval_minutes": 180, "country": "US", "currency": "USD"},
    {"name": "뉴에그", "name_en": "Newegg", "slug": "newegg", "base_url": "https://www.newegg.com", "adapter_type": "api", "scrape_interval_minutes": 180, "country": "US", "currency": "USD"},
    # --- International scraper-based ---
    {"name": "타오바오", "name_en": "Taobao", "slug": "taobao", "base_url": "https://www.taobao.com", "adapter_type": "scraper", "scrape_interval_minutes": 180, "country": "CN", "currency": "CNY"},
    {"name": "테무", "name_en": "Temu", "slug": "temu", "base_url": "https://www.temu.com", "adapter_type": "scraper", "scrape_interval_minutes": 120, "country": "CN", "currency": "KRW"},
]


class SeedShopsRequest(BaseModel):
    api_key: str = Field(..., min_length=1)


class SeedShopsResponse(BaseModel):
    status: str
    created: List[str]
    already_existed: List[str]


@router.post(
    "/seed-shops",
    response_model=SeedShopsResponse,
    status_code=status.HTTP_200_OK,
    summary="Seed all shop records into the database",
    tags=["ingest"],
)
async def seed_shops(
    body: SeedShopsRequest,
    db: AsyncSession = Depends(get_db),
) -> SeedShopsResponse:
    """Create missing shop records so the ingest pipeline can resolve shop slugs."""
    _verify_api_key(body.api_key)

    created: List[str] = []
    already_existed: List[str] = []

    for shop_data in ALL_SHOPS:
        slug = shop_data["slug"]
        result = await db.execute(select(Shop).where(Shop.slug == slug))
        existing = result.scalar_one_or_none()

        if existing:
            already_existed.append(slug)
            continue

        shop = Shop(
            name=shop_data["name"],
            name_en=shop_data["name_en"],
            slug=slug,
            base_url=shop_data["base_url"],
            adapter_type=shop_data.get("adapter_type", "scraper"),
            is_active=shop_data.get("is_active", True),
            scrape_interval_minutes=shop_data.get("scrape_interval_minutes", 60),
            country=shop_data.get("country", "KR"),
            currency=shop_data.get("currency", "KRW"),
            metadata_={},
        )
        db.add(shop)
        created.append(slug)

    await db.commit()

    logger.info(
        "seed_shops_complete",
        created=created,
        already_existed=already_existed,
    )

    return SeedShopsResponse(
        status="success",
        created=created,
        already_existed=already_existed,
    )


# ---------------------------------------------------------------------------
# Data migration: fix image URLs + re-classify categories
# ---------------------------------------------------------------------------


class MigrateRequest(BaseModel):
    api_key: str


class MigrateResponse(BaseModel):
    status: str = "success"
    images_fixed_products: int = 0
    images_fixed_deals: int = 0
    categories_fixed_products: int = 0
    categories_fixed_deals: int = 0


@router.post(
    "/migrate-fix",
    response_model=MigrateResponse,
    status_code=status.HTTP_200_OK,
    summary="Fix existing data: http→https images + auto-classify empty categories",
    tags=["ingest"],
)
async def migrate_fix(
    body: MigrateRequest,
    db: AsyncSession = Depends(get_db),
) -> MigrateResponse:
    """One-time migration to fix image URLs and empty categories in existing data."""
    _verify_api_key(body.api_key)

    from app.models.product import Product
    from app.models.deal import Deal
    from app.models.category import Category
    from app.scrapers.utils.normalizer import CategoryClassifier

    log = logger.bind(endpoint="migrate-fix")

    # --- 1. Fix http:// → https:// in image URLs ---
    result_p = await db.execute(
        update(Product)
        .where(Product.image_url.like("http://%"))
        .values(image_url=func.concat("https://", func.substr(Product.image_url, 8)))
        .execution_options(synchronize_session=False)
    )
    images_fixed_products = result_p.rowcount

    result_d = await db.execute(
        update(Deal)
        .where(Deal.image_url.like("http://%"))
        .values(image_url=func.concat("https://", func.substr(Deal.image_url, 8)))
        .execution_options(synchronize_session=False)
    )
    images_fixed_deals = result_d.rowcount

    log.info("images_fixed", products=images_fixed_products, deals=images_fixed_deals)

    # --- 2. Load category slug → id mapping ---
    cat_result = await db.execute(select(Category.slug, Category.id))
    cat_map = {row[0]: row[1] for row in cat_result.all()}

    # --- 3. Re-classify products with no category ---
    products_fixed = 0
    result = await db.execute(
        select(Product.id, Product.title).where(Product.category_id.is_(None))
    )
    for prod_id, title in result.all():
        slug = CategoryClassifier.classify(title)
        if slug and slug in cat_map:
            await db.execute(
                update(Product)
                .where(Product.id == prod_id)
                .values(category_id=cat_map[slug])
            )
            products_fixed += 1

    # --- 4. Re-classify deals with no category ---
    deals_fixed = 0
    result = await db.execute(
        select(Deal.id, Deal.title).where(Deal.category_id.is_(None))
    )
    for deal_id, title in result.all():
        slug = CategoryClassifier.classify(title)
        if slug and slug in cat_map:
            await db.execute(
                update(Deal)
                .where(Deal.id == deal_id)
                .values(category_id=cat_map[slug])
            )
            deals_fixed += 1

    await db.commit()

    log.info(
        "migrate_fix_complete",
        images_products=images_fixed_products,
        images_deals=images_fixed_deals,
        categories_products=products_fixed,
        categories_deals=deals_fixed,
    )

    return MigrateResponse(
        status="success",
        images_fixed_products=images_fixed_products,
        images_fixed_deals=images_fixed_deals,
        categories_fixed_products=products_fixed,
        categories_fixed_deals=deals_fixed,
    )
