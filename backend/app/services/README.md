# DealHawk Services Layer

This directory contains the business logic layer for the DealHawk platform. Services orchestrate database operations, implement core algorithms, and provide clean interfaces for API endpoints.

## Architecture

```
API Endpoints (FastAPI)
        ↓
   Dependencies
        ↓
   Services Layer  ← You are here
        ↓
   Models (SQLAlchemy)
        ↓
   Database (PostgreSQL)
```

## Core Services

### 1. PriceAnalyzer (`price_analysis.py`)

**Purpose**: AI-powered deal scoring engine - the core value proposition of DealHawk.

**Key Features**:
- Computes deal quality scores (0-100) based on historical price analysis
- Multi-component scoring algorithm:
  - Component A (0-30): Discount from 90-day average
  - Component B (0-20): Recent price drop (7-day comparison)
  - Component C (0-25): Proximity to all-time low
  - Component D (0-15): Listed discount percentage
  - Component E (0-10): Statistical anomaly detection (Z-score)
- Category-specific thresholds (e.g., PC hardware vs. food items)
- Generates Korean-language reasoning for scores

**Usage**:
```python
from app.services import PriceAnalyzer

analyzer = PriceAnalyzer(db)
score_result = await analyzer.compute_deal_score(
    product_id=product_id,
    current_price=Decimal("49900"),
    original_price=Decimal("79900"),
    category_slug="pc-hardware",
)

print(f"Score: {score_result.score}")  # e.g., 78.5
print(f"Tier: {score_result.deal_tier}")  # e.g., "hot_deal"
print(f"Reason: {score_result.reasoning}")  # e.g., "🔥 핫딜 - 평균가 대비 35.2% 저렴, 역대 최저가"
```

**Scoring Tiers**:
- `none`: Below threshold (not a deal)
- `deal`: 35-70 points (standard deal)
- `hot_deal`: 70-85 points (hot deal)
- `super_deal`: 85+ points (featured super deal)

### 2. DealService (`deal_service.py`)

**Purpose**: CRUD operations and lifecycle management for deals.

**Key Features**:
- Create/update deals with automatic AI scoring
- Paginated deal listings with filters (category, shop, price, etc.)
- Top deals by AI score
- Deal expiration management
- Vote tracking (upvote/downvote)
- Automatic discount calculation

**Usage**:
```python
from app.services import DealService

deal_service = DealService(db)

# Create or update a deal
deal = await deal_service.create_or_update_deal(
    product_id=product_id,
    shop_id=shop_id,
    category_id=category_id,
    deal_price=Decimal("49900"),
    original_price=Decimal("79900"),
    title="삼성 SSD 1TB 특가",
    deal_url="https://example.com/deal",
)

# Get paginated deals
deals, total = await deal_service.get_deals(
    page=1,
    limit=20,
    category_slug="pc-hardware",
    sort_by="score",
)

# Get top AI-scored deals
top_deals = await deal_service.get_top_deals(limit=10)

# Expire stale deals (run periodically)
expired_count = await deal_service.expire_stale_deals()
```

**Filtering Options**:
- `category_slug`: Filter by category
- `shop_slug`: Filter by shop
- `min_discount`: Minimum discount percentage
- `deal_type`: Deal type filter
- `sort_by`: "newest", "score", "discount", "views"

### 3. ProductService (`product_service.py`)

**Purpose**: Product catalog management and price history tracking.

**Key Features**:
- Upsert products from scrapers (idempotent)
- Automatic price history recording
- Smart price tracking (avoids duplicate entries)
- Price statistics computation
- Product deactivation for stale items

**Usage**:
```python
from app.services import ProductService
from app.scrapers.base import NormalizedProduct

product_service = ProductService(db)

# Upsert product from scraper
normalized = NormalizedProduct(
    external_id="ABC123",
    title="삼성 SSD 1TB",
    current_price=Decimal("49900"),
    product_url="https://shop.com/product/ABC123",
    original_price=Decimal("79900"),
    currency="KRW",
)

product = await product_service.upsert_product(
    shop_id=shop_id,
    normalized=normalized,
    category_id=category_id,
)

# Get price history for charts
history = await product_service.get_price_history(
    product_id=product.id,
    days=30,
)

# Get price statistics
stats = await product_service.get_price_statistics(
    product_id=product.id,
    days=90,
)
print(stats["avg_price"])  # 65000.50
print(stats["min_price"])  # 49900.00

# Deactivate stale products (cleanup job)
deactivated = await product_service.deactivate_stale_products(days=30)
```

**Price History Logic**:
- Records price only if changed OR 1+ hour since last record
- Prevents duplicate entries for unchanged prices
- Supports chart rendering for frontend

### 4. SearchService (`search_service.py`)

**Purpose**: Full-text search and search analytics.

**Key Features**:
- Fuzzy Korean text search using PostgreSQL trigram indexes
- Search keyword tracking for analytics
- Trending keywords computation
- Advanced filtering (price, score, category, shop)

**Usage**:
```python
from app.services import SearchService

search_service = SearchService(db)

# Basic search
deals, total = await search_service.search_deals(
    query="삼성 SSD",
    page=1,
    limit=20,
    category_slug="pc-hardware",
    sort_by="relevance",
)

# Advanced search with filters
deals, total = await search_service.search_deals_advanced(
    query="그래픽카드",
    min_score=70.0,
    max_price=500000,
    category_slug="pc-hardware",
)

# Get trending searches
trending = await search_service.get_trending_keywords(limit=10)
for item in trending:
    print(f"{item['keyword']}: {item['count']} searches")

# Get recent searches
recent = await search_service.get_recent_keywords(limit=10)
```

**Search Features**:
- Case-insensitive ILIKE pattern matching
- Trigram GIN indexes for fast Korean text search
- Automatic keyword tracking (normalized to lowercase)
- Filters very short queries (< 2 chars)

## Service Patterns

### Dependency Injection

All services use dependency injection via FastAPI's `Depends()`:

```python
from fastapi import Depends
from app.dependencies import get_db
from app.services import DealService

@router.get("/deals")
async def get_deals(
    db: AsyncSession = Depends(get_db),
):
    deal_service = DealService(db)
    deals, total = await deal_service.get_deals()
    return {"deals": deals, "total": total}
```

### Error Handling

Services log errors using structlog but generally don't catch exceptions - let FastAPI handle them:

```python
try:
    deal = await deal_service.create_or_update_deal(...)
except IntegrityError as e:
    logger.error("integrity_error", error=str(e))
    raise HTTPException(status_code=400, detail="Invalid data")
```

### Structured Logging

All services use structlog for structured logging:

```python
self.logger.info(
    "deal_created",
    deal_id=str(deal.id),
    ai_score=float(deal.ai_score),
    shop=shop_slug,
)
```

## Database Session Management

Services **do not** commit or close sessions - that's handled by the dependency layer:

```python
# ✅ Correct
deal = Deal(...)
self.db.add(deal)
await self.db.commit()  # OK - service commits its own changes

# ❌ Wrong
await self.db.close()  # Never close in service - dependency handles this
```

## Testing Services

Example unit test structure:

```python
import pytest
from app.services import DealService

@pytest.mark.asyncio
async def test_create_deal(async_session):
    service = DealService(async_session)

    deal = await service.create_or_update_deal(
        product_id=test_product_id,
        shop_id=test_shop_id,
        # ... other params
    )

    assert deal.id is not None
    assert deal.ai_score > 0
```

## Performance Considerations

1. **Eager Loading**: Services use `selectinload()` to avoid N+1 queries:
   ```python
   query = select(Deal).options(
       selectinload(Deal.shop),
       selectinload(Deal.category),
   )
   ```

2. **Pagination**: Always paginate large result sets:
   ```python
   query = query.offset((page - 1) * limit).limit(limit)
   ```

3. **Indexing**: Services rely on database indexes defined in models:
   - Trigram GIN indexes for text search
   - Partial indexes for filtered queries
   - Composite indexes for common query patterns

4. **Batch Operations**: Use bulk operations for large datasets:
   ```python
   # For future optimization
   self.db.add_all([deal1, deal2, deal3])
   await self.db.commit()
   ```

## Future Enhancements

Planned service additions:

1. **RecommendationService**: Personalized deal recommendations
2. **NotificationService**: Alert users about price drops
3. **CategoryService**: Category management and auto-categorization
4. **ShopService**: Shop management and health monitoring
5. **AnalyticsService**: Business intelligence and metrics

## Integration with API Layer

Services are consumed by FastAPI routers in `app/api/v1/`:

```
app/api/v1/
├── deals.py        → DealService
├── products.py     → ProductService
├── search.py       → SearchService
└── health.py       → PriceAnalyzer (health check)
```

## Best Practices

1. **Single Responsibility**: Each service focuses on one domain entity
2. **No Business Logic in Models**: Keep models as data structures
3. **Type Hints**: All parameters and returns are type-hinted
4. **Docstrings**: All public methods have docstrings
5. **Async All The Way**: Use `async/await` for all I/O operations
6. **Structured Logging**: Use structlog with context binding
7. **Decimal for Money**: Always use `Decimal` for prices, never `float`

## Common Patterns

### Service Factory Pattern

For creating services with shared dependencies:

```python
class ServiceFactory:
    def __init__(self, db: AsyncSession):
        self.db = db

    def deal_service(self) -> DealService:
        return DealService(self.db)

    def product_service(self) -> ProductService:
        return ProductService(self.db)
```

### Transactional Operations

For multi-service operations:

```python
async def create_deal_with_product(
    db: AsyncSession,
    normalized_product: NormalizedProduct,
    deal_data: dict,
):
    # Both services share same transaction
    product_service = ProductService(db)
    deal_service = DealService(db)

    product = await product_service.upsert_product(...)
    deal = await deal_service.create_or_update_deal(
        product_id=product.id,
        ...
    )

    # Single commit for atomic operation
    await db.commit()
    return deal
```

## References

- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Structlog](https://www.structlog.org/en/stable/)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [pg_trgm Extension](https://www.postgresql.org/docs/current/pgtrgm.html)
