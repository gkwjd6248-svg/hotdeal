# Quick Start Guide - DealHawk Services

## 5-Minute Overview

The DealHawk services layer provides four main services for managing deals, products, search, and AI scoring.

## Installation

```bash
# Already included in project requirements
pip install -r requirements.txt
```

## Basic Usage

### 1. Score a Deal with AI

```python
from app.services import PriceAnalyzer
from decimal import Decimal

async with get_db() as db:
    analyzer = PriceAnalyzer(db)

    score = await analyzer.compute_deal_score(
        product_id=product_uuid,
        current_price=Decimal("49900"),
        original_price=Decimal("79900"),
    )

    print(f"Score: {score.score}/100")
    print(f"Tier: {score.deal_tier}")
    print(f"Why: {score.reasoning}")
```

**Output:**
```
Score: 78.5/100
Tier: hot_deal
Why: 🔥 핫딜 - 평균가 대비 35.2% 저렴, 최근 7일 대비 15.0% 급락
```

### 2. Create a Deal

```python
from app.services import DealService
from decimal import Decimal

async with get_db() as db:
    deal_service = DealService(db)

    deal = await deal_service.create_or_update_deal(
        product_id=product_id,
        shop_id=shop_id,
        category_id=category_id,
        deal_price=Decimal("49900"),
        original_price=Decimal("79900"),
        title="삼성 SSD 1TB 특가",
        deal_url="https://shop.com/deal/123",
    )

    print(f"Deal created with AI score: {deal.ai_score}")
```

### 3. Search Deals

```python
from app.services import SearchService

async with get_db() as db:
    search = SearchService(db)

    deals, total = await search.search_deals(
        query="삼성 SSD",
        page=1,
        limit=20,
    )

    print(f"Found {total} deals")
```

### 4. Upsert Product

```python
from app.services import ProductService
from app.scrapers.base import NormalizedProduct
from decimal import Decimal

normalized = NormalizedProduct(
    external_id="PROD123",
    title="삼성 SSD 1TB",
    current_price=Decimal("49900"),
    product_url="https://shop.com/product/123",
)

async with get_db() as db:
    product_service = ProductService(db)
    product = await product_service.upsert_product(
        shop_id=shop_id,
        normalized=normalized,
    )
```

## In FastAPI Endpoints

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.services import DealService

router = APIRouter()

@router.get("/deals")
async def get_deals(
    page: int = 1,
    db: AsyncSession = Depends(get_db),
):
    deal_service = DealService(db)
    deals, total = await deal_service.get_deals(page=page, limit=20)
    return {"deals": deals, "total": total}
```

## Common Patterns

### Pattern 1: Process Scraper Output

```python
async def process_scrape(db, scraper_data):
    # 1. Upsert product
    product_service = ProductService(db)
    product = await product_service.upsert_product(
        shop_id=shop_id,
        normalized=scraper_data["product"],
    )

    # 2. Create deal with AI scoring
    deal_service = DealService(db)
    deal = await deal_service.create_or_update_deal(
        product_id=product.id,
        shop_id=shop_id,
        deal_price=scraper_data["price"],
        title=scraper_data["title"],
        deal_url=scraper_data["url"],
    )

    return deal
```

### Pattern 2: Get Homepage Deals

```python
async def get_homepage_data(db):
    deal_service = DealService(db)

    return {
        "featured": await deal_service.get_top_deals(limit=10),
        "pc_hardware": await deal_service.get_top_deals(
            limit=5,
            category_slug="pc-hardware"
        ),
        "games": await deal_service.get_top_deals(
            limit=5,
            category_slug="games-software"
        ),
    }
```

### Pattern 3: Background Job

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def expire_deals_job():
    async with async_session_factory() as db:
        deal_service = DealService(db)
        count = await deal_service.expire_stale_deals()
        print(f"Expired {count} deals")

scheduler = AsyncIOScheduler()
scheduler.add_job(expire_deals_job, 'interval', hours=1)
scheduler.start()
```

## Service Methods Cheat Sheet

### PriceAnalyzer
- `compute_deal_score()` - Analyze price and compute 0-100 score

### DealService
- `get_deals()` - Paginated list with filters
- `get_top_deals()` - Top AI-scored deals
- `get_deal_by_id()` - Single deal detail
- `create_or_update_deal()` - Upsert deal with AI scoring
- `expire_stale_deals()` - Mark expired deals
- `vote_deal()` - Upvote/downvote

### ProductService
- `upsert_product()` - Idempotent product insert/update
- `get_product_by_id()` - Single product detail
- `get_products()` - Paginated product list
- `get_price_history()` - Historical prices for charts
- `get_price_statistics()` - Min/max/avg price stats
- `deactivate_stale_products()` - Cleanup old products

### SearchService
- `search_deals()` - Full-text search
- `search_deals_advanced()` - Search with filters
- `get_trending_keywords()` - Popular searches
- `get_recent_keywords()` - Recent searches

## Filters Available

### DealService.get_deals()
```python
deals, total = await deal_service.get_deals(
    page=1,
    limit=20,
    category_slug="pc-hardware",  # Filter by category
    shop_slug="coupang",          # Filter by shop
    sort_by="score",              # Sort: newest/score/discount/views
    min_discount=30.0,            # Min discount %
    deal_type="price_drop",       # Type filter
)
```

### SearchService.search_deals_advanced()
```python
deals, total = await search.search_deals_advanced(
    query="SSD",
    min_score=70.0,     # Minimum AI score
    max_price=100000,   # Maximum price
    category_slug="pc-hardware",
    shop_slug="coupang",
)
```

## Deal Score Tiers

| Score Range | Tier | Label | Description |
|------------|------|-------|-------------|
| 0-35 | none | - | Not a deal |
| 35-70 | deal | 💰 특가 | Standard deal |
| 70-85 | hot_deal | 🔥 핫딜 | Hot deal |
| 85-100 | super_deal | 🔥 슈퍼특가 | Super deal |

## Score Components

The AI score is composed of 5 components:

1. **vs_average** (0-30): Price vs 90-day average
2. **vs_recent** (0-20): Price vs 7-day average
3. **all_time_low** (0-25): Proximity to historical minimum
4. **listed_discount** (0-15): Advertised discount %
5. **anomaly_bonus** (0-10): Statistical outlier detection

Access component breakdown:
```python
score = await analyzer.compute_deal_score(...)
print(score.components)
# {'vs_average': 28.5, 'vs_recent': 18.0, ...}
```

## Error Handling

Services don't catch exceptions - let FastAPI handle them:

```python
from fastapi import HTTPException

@router.post("/deals")
async def create_deal(data: DealCreate, db: AsyncSession = Depends(get_db)):
    try:
        deal_service = DealService(db)
        deal = await deal_service.create_or_update_deal(**data.dict())
        return deal
    except Exception as e:
        logger.error("deal_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create deal")
```

## Logging

All services use structlog:

```python
# Logs automatically include context
self.logger.info(
    "deal_created",
    deal_id=str(deal.id),
    ai_score=float(deal.ai_score),
)

# Output: {"event": "deal_created", "deal_id": "...", "ai_score": 78.5, ...}
```

## Testing

```python
import pytest
from app.services import DealService

@pytest.mark.asyncio
async def test_create_deal(async_session):
    service = DealService(async_session)
    deal = await service.create_or_update_deal(...)
    assert deal.ai_score >= 0
```

## Common Issues

### Issue: Price history is empty
**Solution**: Product needs at least 3 price history entries for accurate scoring. New products will have fallback scoring based on current/original price only.

### Issue: Search returns no results
**Solution**: Ensure pg_trgm extension is enabled and trigram indexes exist:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Issue: Decimal conversion errors
**Solution**: Always use `Decimal("49900")` not `Decimal(49900)` or `float`.

### Issue: Session is closed
**Solution**: Don't close sessions in services - the dependency handles it.

## Next Steps

1. **Read Full Docs**: See `README.md` for comprehensive documentation
2. **View Examples**: See `USAGE_EXAMPLES.md` for detailed examples
3. **Check Architecture**: See `ARCHITECTURE.md` for system design
4. **Review Checklist**: See `CHECKLIST.md` for implementation status

## File Locations

```
backend/app/services/
├── __init__.py              # Service exports
├── price_analysis.py        # AI scoring engine
├── deal_service.py          # Deal management
├── product_service.py       # Product catalog
├── search_service.py        # Search & analytics
├── README.md                # Full documentation
├── USAGE_EXAMPLES.md        # Code examples
├── ARCHITECTURE.md          # System diagrams
├── CHECKLIST.md             # Implementation status
└── QUICK_START.md           # This file
```

## Support

For detailed information:
- Architecture questions → `ARCHITECTURE.md`
- Usage patterns → `USAGE_EXAMPLES.md`
- Implementation details → `IMPLEMENTATION_SUMMARY.md`
- General reference → `README.md`

---

**Quick Reference Card**

```python
# AI Score
score = await PriceAnalyzer(db).compute_deal_score(product_id, price)

# Create Deal
deal = await DealService(db).create_or_update_deal(product_id, ...)

# Search
deals, total = await SearchService(db).search_deals(query)

# Upsert Product
product = await ProductService(db).upsert_product(shop_id, normalized)

# Get Deals
deals, total = await DealService(db).get_deals(page=1, limit=20)

# Get Top Deals
deals = await DealService(db).get_top_deals(limit=10)

# Price History
history = await ProductService(db).get_price_history(product_id)

# Trending
trending = await SearchService(db).get_trending_keywords()
```
