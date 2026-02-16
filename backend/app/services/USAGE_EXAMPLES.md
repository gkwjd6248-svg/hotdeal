# Service Usage Examples

This document provides practical examples of using the DealHawk services in various scenarios.

## 1. Price Analysis - Computing Deal Scores

### Basic Usage

```python
from decimal import Decimal
from app.services import PriceAnalyzer
from app.dependencies import get_db

async def analyze_deal():
    async for db in get_db():
        analyzer = PriceAnalyzer(db)

        score = await analyzer.compute_deal_score(
            product_id=product_uuid,
            current_price=Decimal("49900"),
            original_price=Decimal("79900"),
            category_slug="pc-hardware",
        )

        print(f"AI Score: {score.score}")
        print(f"Is Deal: {score.is_deal}")
        print(f"Tier: {score.deal_tier}")
        print(f"Reasoning: {score.reasoning}")
        print(f"Components: {score.components}")
```

### Output Example

```
AI Score: 78.5
Is Deal: True
Tier: hot_deal
Reasoning: 🔥 핫딜 - 평균가 대비 35.2% 저렴, 최근 7일 대비 15.0% 급락, 역대 최저가
Components: {
    'vs_average': 28.5,
    'vs_recent': 18.0,
    'all_time_low': 25.0,
    'listed_discount': 4.5,
    'anomaly_bonus': 2.5
}
```

### Understanding the Score

- **0-35**: Not a deal (normal pricing)
- **35-70**: Good deal (worth considering)
- **70-85**: Hot deal (very good value)
- **85-100**: Super deal (exceptional value, featured)

## 2. Deal Service - Creating and Managing Deals

### Creating a Deal from Scraper Data

```python
from app.services import DealService
from decimal import Decimal
from datetime import datetime, timezone, timedelta

async def create_deal_from_scrape(db, scraped_data):
    deal_service = DealService(db)

    deal = await deal_service.create_or_update_deal(
        product_id=scraped_data["product_id"],
        shop_id=scraped_data["shop_id"],
        category_id=scraped_data.get("category_id"),
        deal_price=Decimal(scraped_data["price"]),
        original_price=Decimal(scraped_data["original_price"]),
        title=scraped_data["title"],
        deal_url=scraped_data["url"],
        image_url=scraped_data.get("image_url"),
        deal_type="price_drop",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    print(f"Deal created: {deal.id}")
    print(f"AI Score: {deal.ai_score}")
    print(f"Discount: {deal.discount_percentage}%")
    return deal
```

### Fetching Deals with Filters

```python
async def get_filtered_deals(db):
    deal_service = DealService(db)

    # Get top deals in PC hardware category
    deals, total = await deal_service.get_deals(
        page=1,
        limit=20,
        category_slug="pc-hardware",
        sort_by="score",
        min_discount=30.0,
    )

    for deal in deals:
        print(f"{deal.title}: {deal.ai_score} pts, {deal.discount_percentage}% off")

    return deals
```

### Getting Top Deals for Homepage

```python
async def get_homepage_deals(db):
    deal_service = DealService(db)

    # Get top 10 deals across all categories
    top_deals = await deal_service.get_top_deals(limit=10)

    # Get top 5 deals per category
    categories = ["pc-hardware", "games-software", "electronics-tv"]
    deals_by_category = {}

    for cat in categories:
        deals_by_category[cat] = await deal_service.get_top_deals(
            limit=5,
            category_slug=cat,
        )

    return {
        "featured": top_deals,
        "by_category": deals_by_category,
    }
```

### Running Expiration Job

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def expire_deals_job(db):
    """Run every hour to expire stale deals."""
    deal_service = DealService(db)
    expired_count = await deal_service.expire_stale_deals()
    print(f"Expired {expired_count} deals")

# Schedule with APScheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(
    expire_deals_job,
    'interval',
    hours=1,
    args=[db],
)
```

## 3. Product Service - Managing Product Catalog

### Upserting Product from Scraper

```python
from app.services import ProductService
from app.scrapers.base import NormalizedProduct
from decimal import Decimal

async def import_scraped_product(db, scraper_output):
    product_service = ProductService(db)

    # Create normalized product from scraper
    normalized = NormalizedProduct(
        external_id=scraper_output["id"],
        title=scraper_output["title"],
        current_price=Decimal(scraper_output["price"]),
        product_url=scraper_output["url"],
        original_price=Decimal(scraper_output["original_price"]) if scraper_output.get("original_price") else None,
        currency="KRW",
        image_url=scraper_output.get("image"),
        brand=scraper_output.get("brand"),
        category_hint=scraper_output.get("category"),
        metadata=scraper_output.get("extra_data", {}),
    )

    # Upsert (idempotent - safe to call multiple times)
    product = await product_service.upsert_product(
        shop_id=shop_uuid,
        normalized=normalized,
        category_id=category_uuid,
    )

    print(f"Product upserted: {product.id}")
    print(f"Is new: {product.created_at == product.updated_at}")
    return product
```

### Getting Price History for Charts

```python
async def get_price_chart_data(db, product_id):
    product_service = ProductService(db)

    # Get 30 days of price history
    history = await product_service.get_price_history(
        product_id=product_id,
        days=30,
    )

    # Format for chart library (e.g., Chart.js)
    chart_data = {
        "labels": [h.recorded_at.isoformat() for h in history],
        "prices": [float(h.price) for h in history],
    }

    return chart_data
```

### Computing Price Statistics

```python
async def show_price_stats(db, product_id):
    product_service = ProductService(db)

    stats = await product_service.get_price_statistics(
        product_id=product_id,
        days=90,
    )

    if stats:
        print(f"Average Price (90d): ₩{stats['avg_price']:,.0f}")
        print(f"Lowest Price: ₩{stats['min_price']:,.0f}")
        print(f"Highest Price: ₩{stats['max_price']:,.0f}")
        print(f"Current Price: ₩{stats['current_price']:,.0f}")
        print(f"Data Points: {stats['data_points']}")
    else:
        print("Insufficient price history")
```

### Cleanup Job for Stale Products

```python
async def cleanup_stale_products_job(db):
    """Run daily to deactivate products not scraped in 30 days."""
    product_service = ProductService(db)

    deactivated = await product_service.deactivate_stale_products(days=30)
    print(f"Deactivated {deactivated} stale products")

# Schedule daily at 3 AM
scheduler.add_job(
    cleanup_stale_products_job,
    'cron',
    hour=3,
    args=[db],
)
```

## 4. Search Service - Finding Deals

### Basic Search

```python
async def search_deals(db, user_query):
    search_service = SearchService(db)

    deals, total = await search_service.search_deals(
        query=user_query,
        page=1,
        limit=20,
    )

    print(f"Found {total} results for '{user_query}'")
    for deal in deals:
        print(f"- {deal.title} (Score: {deal.ai_score})")

    return deals
```

### Advanced Search with Filters

```python
async def advanced_search(db, query):
    search_service = SearchService(db)

    # Search for high-quality deals under ₩100,000
    deals, total = await search_service.search_deals_advanced(
        query=query,
        min_score=70.0,  # Only hot deals and above
        max_price=100000.0,
        category_slug="pc-hardware",
        page=1,
        limit=20,
    )

    return deals
```

### Getting Trending Searches

```python
async def show_trending(db):
    search_service = SearchService(db)

    trending = await search_service.get_trending_keywords(limit=10)

    print("Top 10 Trending Searches:")
    for i, item in enumerate(trending, 1):
        print(f"{i}. {item['keyword']} ({item['count']} searches)")
```

### Implementing Search Autocomplete

```python
async def get_search_suggestions(db, partial_query):
    search_service = SearchService(db)

    # Get recent searches that match partial query
    recent = await search_service.get_recent_keywords(limit=50)

    # Filter to matches
    suggestions = [
        kw["keyword"]
        for kw in recent
        if partial_query.lower() in kw["keyword"].lower()
    ][:5]  # Top 5 matches

    return suggestions
```

## 5. Complete Scraper Integration Flow

### End-to-End Example: From Scraping to Deal Creation

```python
from app.services import ProductService, DealService
from app.scrapers.base import NormalizedProduct, NormalizedDeal
from decimal import Decimal

async def process_scraped_deal(db, scraper_output):
    """Complete flow from scraper output to live deal."""

    # 1. Upsert product
    product_service = ProductService(db)
    normalized_product = NormalizedProduct(
        external_id=scraper_output["product_id"],
        title=scraper_output["title"],
        current_price=Decimal(scraper_output["price"]),
        product_url=scraper_output["product_url"],
        original_price=Decimal(scraper_output["original_price"]),
        currency="KRW",
        image_url=scraper_output["image_url"],
        brand=scraper_output.get("brand"),
        metadata=scraper_output.get("metadata", {}),
    )

    product = await product_service.upsert_product(
        shop_id=scraper_output["shop_id"],
        normalized=normalized_product,
        category_id=scraper_output.get("category_id"),
    )

    print(f"✓ Product upserted: {product.id}")

    # 2. Create deal with AI scoring
    deal_service = DealService(db)
    deal = await deal_service.create_or_update_deal(
        product_id=product.id,
        shop_id=scraper_output["shop_id"],
        category_id=scraper_output.get("category_id"),
        deal_price=Decimal(scraper_output["price"]),
        original_price=Decimal(scraper_output["original_price"]),
        title=scraper_output["title"],
        deal_url=scraper_output["deal_url"],
        image_url=scraper_output["image_url"],
        deal_type=scraper_output.get("deal_type", "price_drop"),
    )

    print(f"✓ Deal created: {deal.id}")
    print(f"  AI Score: {deal.ai_score}")
    print(f"  Reasoning: {deal.ai_reasoning}")
    print(f"  Is Deal: {deal.ai_score >= 35}")

    return deal
```

## 6. FastAPI Endpoint Integration

### Example Endpoint Using Services

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.services import DealService, SearchService
from typing import Optional

router = APIRouter(prefix="/api/v1", tags=["deals"])

@router.get("/deals")
async def get_deals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    shop: Optional[str] = None,
    sort: str = Query("newest", regex="^(newest|score|discount|views)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated deals with optional filters."""
    deal_service = DealService(db)

    deals, total = await deal_service.get_deals(
        page=page,
        limit=limit,
        category_slug=category,
        shop_slug=shop,
        sort_by=sort,
    )

    return {
        "deals": deals,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }

@router.get("/search")
async def search_deals(
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search deals by keyword."""
    search_service = SearchService(db)

    deals, total = await search_service.search_deals(
        query=q,
        page=page,
        limit=limit,
    )

    return {
        "query": q,
        "deals": deals,
        "total": total,
        "page": page,
    }

@router.get("/trending")
async def get_trending_searches(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get trending search keywords."""
    search_service = SearchService(db)
    trending = await search_service.get_trending_keywords(limit=limit)
    return {"trending": trending}
```

## 7. Background Jobs with APScheduler

### Complete Scheduler Setup

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db.session import async_session_factory
from app.services import DealService, ProductService

async def expire_deals():
    """Job: Expire stale deals every hour."""
    async with async_session_factory() as db:
        deal_service = DealService(db)
        count = await deal_service.expire_stale_deals()
        print(f"[JOB] Expired {count} deals")

async def cleanup_products():
    """Job: Deactivate stale products daily."""
    async with async_session_factory() as db:
        product_service = ProductService(db)
        count = await product_service.deactivate_stale_products(days=30)
        print(f"[JOB] Deactivated {count} products")

# Initialize scheduler
scheduler = AsyncIOScheduler()

# Add jobs
scheduler.add_job(expire_deals, 'interval', hours=1)
scheduler.add_job(cleanup_products, 'cron', hour=3, minute=0)

# Start scheduler
scheduler.start()
```

## 8. Testing Services

### Example Pytest Test

```python
import pytest
from decimal import Decimal
from app.services import DealService
from app.models import Product, Shop, Category, Deal

@pytest.mark.asyncio
async def test_create_deal_with_ai_scoring(async_session, test_product, test_shop):
    """Test deal creation with AI score computation."""
    deal_service = DealService(async_session)

    deal = await deal_service.create_or_update_deal(
        product_id=test_product.id,
        shop_id=test_shop.id,
        category_id=None,
        deal_price=Decimal("49900"),
        original_price=Decimal("79900"),
        title="테스트 특가",
        deal_url="https://example.com/deal",
    )

    # Assertions
    assert deal.id is not None
    assert deal.ai_score is not None
    assert deal.ai_score >= 0
    assert deal.ai_score <= 100
    assert deal.discount_percentage == Decimal("37.55")
    assert deal.is_active is True

    print(f"✓ Deal AI Score: {deal.ai_score}")
```

## Summary

These examples demonstrate the key patterns for using DealHawk services:

1. **Dependency Injection**: Services receive `AsyncSession` via constructor
2. **Async/Await**: All service methods are async
3. **Decimal for Money**: Always use `Decimal` for prices
4. **Structured Logging**: Services log operations with context
5. **Idempotent Operations**: Upsert patterns allow safe retries
6. **Transaction Management**: Services commit changes, dependencies manage session lifecycle

For more details, see `README.md` in this directory.
