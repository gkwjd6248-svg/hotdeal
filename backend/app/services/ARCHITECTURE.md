# DealHawk Services Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                      │
│                   [React Components]                        │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Application                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              API Endpoints (Routers)                 │  │
│  │  /deals  /search  /products  /trending               │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                       │
│  ┌──────────────────▼───────────────────────────────────┐  │
│  │            Dependency Injection                      │  │
│  │     get_db() → AsyncSession (auto-commit/rollback)   │  │
│  └──────────────────┬───────────────────────────────────┘  │
└────────────────────┬┼───────────────────────────────────────┘
                     ││
        ┌────────────┼┴────────────┐
        │            │              │
        ▼            ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ DealService │ │ProductSvc   │ │SearchService│
│             │ │             │ │             │
│ - get_deals │ │ - upsert    │ │ - search    │
│ - create    │ │ - history   │ │ - trending  │
│ - expire    │ │ - stats     │ └──────┬──────┘
└──────┬──────┘ └──────┬──────┘        │
       │               │               │
       │     ┌─────────▼─────────┐     │
       │     │  PriceAnalyzer    │     │
       │     │                   │     │
       └────►│ - AI Scoring      │     │
             │ - History Analysis│     │
             └─────────┬─────────┘     │
                       │               │
                       ▼               ▼
        ┌──────────────────────────────────────┐
        │      SQLAlchemy 2.0 (Async ORM)      │
        │  Models: Deal, Product, PriceHistory │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │      PostgreSQL 16 Database          │
        │   + pg_trgm (Trigram Search)         │
        │   + JSONB (Metadata)                 │
        └──────────────────────────────────────┘
```

## Data Flow: Scraper → Deal Creation

```
┌──────────────┐
│   Scraper    │
│  (Coupang,   │
│   11st, etc) │
└──────┬───────┘
       │ Outputs: NormalizedProduct, NormalizedDeal
       ▼
┌──────────────────────────────────────────────────────────┐
│                 ProductService.upsert_product()          │
│  1. Check if product exists (external_id + shop_id)      │
│  2. Create/update product record                         │
│  3. Record price in price_history (if changed)           │
│  4. Return Product                                       │
└──────────────────────┬───────────────────────────────────┘
                       │ product.id
                       ▼
┌──────────────────────────────────────────────────────────┐
│           DealService.create_or_update_deal()            │
│  1. Check for existing active deal (product+shop)        │
│  2. Call PriceAnalyzer.compute_deal_score()   ──┐        │
│  3. Calculate discount percentage                │        │
│  4. Create/update Deal record                    │        │
│  5. Return Deal with AI score                    │        │
└──────────────────────┬───────────────────────────┼───────┘
                       │                           │
                       │                ┌──────────▼─────────────┐
                       │                │  PriceAnalyzer         │
                       │                │  1. Fetch price history│
                       │                │  2. Compute statistics │
                       │                │  3. Score components   │
                       │                │  4. Generate reasoning │
                       │                └────────────────────────┘
                       ▼
               ┌──────────────┐
               │  Deal (Scored)│
               │  ai_score: 78.5│
               │  tier: hot_deal│
               │  is_active: true│
               └──────────────┘
```

## Service Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────┐    ┌──────────────┐                    │
│  │ PriceAnalyzer  │    │ DealService  │                    │
│  ├────────────────┤    ├──────────────┤                    │
│  │ Core Algorithm │    │ Deal CRUD    │                    │
│  │ - Multi-comp   │◄───│ - Create     │                    │
│  │   scoring      │    │ - Update     │                    │
│  │ - History      │    │ - Query      │                    │
│  │   analysis     │    │ - Expire     │                    │
│  │ - Reasoning    │    │ - Vote       │                    │
│  └────────────────┘    └──────────────┘                    │
│                                                             │
│  ┌────────────────┐    ┌──────────────┐                    │
│  │ProductService  │    │SearchService │                    │
│  ├────────────────┤    ├──────────────┤                    │
│  │ Product Mgmt   │    │ Search       │                    │
│  │ - Upsert       │    │ - Fuzzy text │                    │
│  │ - History      │    │ - Trigram    │                    │
│  │ - Statistics   │    │ - Trending   │                    │
│  │ - Cleanup      │    │ - Analytics  │                    │
│  └────────────────┘    └──────────────┘                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## AI Scoring Components Flow

```
Input: product_id, current_price, original_price, category

          ┌──────────────────────────┐
          │  Fetch Price History     │
          │  (last 90 days)          │
          └───────────┬──────────────┘
                      │
          ┌───────────▼──────────────┐
          │  Statistical Analysis    │
          │  - Mean, Min, Max        │
          │  - Std Dev, Median       │
          │  - Recent Avg (7d)       │
          └───────────┬──────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────┐         ┌───────────────┐
│  Component A  │         │  Component B  │
│  vs Average   │         │  vs Recent    │
│  (0-30 pts)   │         │  (0-20 pts)   │
└───────┬───────┘         └───────┬───────┘
        │                         │
        │         ┌───────────────┘
        │         │
        │         │       ┌───────────────┐
        │         │       │  Component C  │
        │         │       │  All-Time Low │
        │         │       │  (0-25 pts)   │
        │         │       └───────┬───────┘
        │         │               │
        │         │    ┌──────────┘
        │         │    │
        │         │    │   ┌───────────────┐
        │         │    │   │  Component D  │
        │         │    │   │  Listed Disc  │
        │         │    │   │  (0-15 pts)   │
        │         │    │   └───────┬───────┘
        │         │    │           │
        │         │    │   ┌───────┘
        │         │    │   │
        │         │    │   │   ┌───────────────┐
        │         │    │   │   │  Component E  │
        │         │    │   │   │  Anomaly      │
        │         │    │   │   │  (0-10 pts)   │
        │         │    │   │   └───────┬───────┘
        │         │    │   │           │
        └─────────┴────┴───┴───────────┘
                      │
          ┌───────────▼──────────────┐
          │   Sum Components         │
          │   Total Score (0-100)    │
          └───────────┬──────────────┘
                      │
          ┌───────────▼──────────────┐
          │  Apply Thresholds        │
          │  Determine Tier          │
          │  - none / deal           │
          │  - hot_deal / super_deal │
          └───────────┬──────────────┘
                      │
          ┌───────────▼──────────────┐
          │  Generate Reasoning      │
          │  (Korean language)       │
          └───────────┬──────────────┘
                      │
                      ▼
              ┌──────────────┐
              │   DealScore  │
              │  - score     │
              │  - tier      │
              │  - reasoning │
              │  - components│
              └──────────────┘
```

## Database Schema (Relevant Tables)

```sql
┌─────────────────────────────────────────────────────────────┐
│                         shops                               │
├─────────────────────────────────────────────────────────────┤
│ id (UUID PK), name, slug, adapter_type, is_active          │
└───────────────────────┬─────────────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  products   │  │    deals    │  │scraper_jobs │
├─────────────┤  ├─────────────┤  ├─────────────┤
│ id (PK)     │  │ id (PK)     │  │ id (PK)     │
│ external_id │  │ product_id ─┼──┤ shop_id (FK)│
│ shop_id (FK)│◄─┤ shop_id (FK)│  │ status      │
│ title       │  │ deal_price  │  │ started_at  │
│ current_price│ │ ai_score   ★│  └─────────────┘
│ original_pr │  │ ai_reasoning│
│ last_scraped│  │ is_active   │
└──────┬──────┘  └─────────────┘
       │
       │ 1:N
       ▼
┌─────────────┐         ┌─────────────┐
│price_history│         │ categories  │
├─────────────┤         ├─────────────┤
│ id (PK)     │         │ id (PK)     │
│ product_id  │         │ name, slug  │
│ price      ★│         │ parent_id   │
│ recorded_at │         └──────┬──────┘
└─────────────┘                │ N:1
                               │
                        ┌──────┴──────┐
                        │             │
                  products         deals

★ Key fields for AI scoring
```

## Dependency Injection Pattern

```
FastAPI Request
      │
      ▼
┌──────────────────┐
│  get_db()        │  ← Dependency
│  - Creates       │
│    AsyncSession  │
│  - Yields to     │
│    endpoint      │
│  - Auto-commits  │
│  - Auto-rollback │
│  - Closes        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Endpoint        │
│  @router.get()   │
│  async def ...   │
│  (db: Session =  │
│   Depends(get_db)│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Service Layer   │
│  service =       │
│    Service(db)   │
│  result = await  │
│    service.foo() │
└──────────────────┘
```

## Background Jobs Architecture

```
┌──────────────────────────────────────────────────────────┐
│              APScheduler (AsyncIOScheduler)              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐    ┌──────────────────┐          │
│  │  Hourly Jobs     │    │   Daily Jobs     │          │
│  ├──────────────────┤    ├──────────────────┤          │
│  │ - Expire Deals   │    │ - Cleanup        │          │
│  │   (every 1h)     │    │   Products       │          │
│  │                  │    │   (3 AM daily)   │          │
│  │ - Refresh Scores │    │                  │          │
│  │   (every 6h)     │    │ - Generate       │          │
│  │                  │    │   Reports        │          │
│  └────────┬─────────┘    └────────┬─────────┘          │
│           │                       │                     │
└───────────┼───────────────────────┼─────────────────────┘
            │                       │
            ▼                       ▼
    ┌──────────────┐       ┌──────────────┐
    │ DealService  │       │ProductService│
    │.expire_stale_│       │.deactivate_  │
    │  deals()     │       │  stale()     │
    └──────────────┘       └──────────────┘
```

## Request/Response Flow Example

### Example: GET /api/v1/deals?category=pc-hardware&sort=score

```
1. HTTP GET Request
   └─> FastAPI Router (app/api/v1/deals.py)
       └─> get_db() dependency
           └─> Creates AsyncSession
               └─> Endpoint handler: get_deals()
                   └─> DealService(db)
                       └─> deal_service.get_deals(
                             category_slug="pc-hardware",
                             sort_by="score"
                           )
                           └─> Build SQLAlchemy query
                               └─> JOIN categories ON slug
                               └─> WHERE is_active = true
                               └─> ORDER BY ai_score DESC
                               └─> Execute query
                                   └─> PostgreSQL
                                       └─> Returns rows
                                           └─> ORM hydration
                                               └─> List[Deal]
                                                   └─> Return to endpoint
                                                       └─> Pydantic schema
                                                           └─> JSON response

2. Session cleanup (automatic)
   └─> get_db() yields back
       └─> If no exception: commit
       └─> If exception: rollback
       └─> Close session
```

## Service Collaboration Example

### Scenario: Scraper finds a deal

```
┌──────────────┐
│   Scraper    │ Finds product with 50% discount
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────────────────┐
│ 1. ProductService.upsert_product()                 │
│    - Checks if product exists                      │
│    - Creates/updates product                       │
│    - Adds price to history                         │
│    Returns: Product object                         │
└──────────────────────┬─────────────────────────────┘
                       │
                       ▼ product.id
┌────────────────────────────────────────────────────┐
│ 2. DealService.create_or_update_deal()             │
│    Calls ─┐                                        │
│           │                                        │
│           ▼                                        │
│    ┌──────────────────────────────┐               │
│    │ 3. PriceAnalyzer              │               │
│    │    .compute_deal_score()      │               │
│    │    - Fetches price history    │               │
│    │    - Computes 5 components    │               │
│    │    - Determines tier          │               │
│    │    - Generates reasoning      │               │
│    │    Returns: DealScore(78.5)   │               │
│    └──────────────────────────────┘               │
│           │                                        │
│    ◄──────┘                                        │
│    - Creates Deal with ai_score = 78.5            │
│    - Sets ai_reasoning, tier, etc                 │
│    Returns: Deal object                            │
└────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│   Response   │ Deal created with AI score
└──────────────┘
```

## Technology Stack

```
┌────────────────────────────────────────┐
│           Application Layer            │
│  - FastAPI 0.110+                      │
│  - Pydantic 2.0+                       │
│  - structlog                           │
└────────────┬───────────────────────────┘
             │
┌────────────▼───────────────────────────┐
│         Business Logic Layer           │
│  - Services (This implementation)      │
│  - PriceAnalyzer, DealService, etc     │
└────────────┬───────────────────────────┘
             │
┌────────────▼───────────────────────────┐
│            ORM Layer                   │
│  - SQLAlchemy 2.0 (async)              │
│  - Alembic (migrations)                │
└────────────┬───────────────────────────┘
             │
┌────────────▼───────────────────────────┐
│         Database Layer                 │
│  - PostgreSQL 16                       │
│  - pg_trgm extension                   │
│  - asyncpg driver                      │
└────────────────────────────────────────┘
```

## Summary

The services layer acts as the business logic orchestrator:

1. **Receives requests** from API endpoints
2. **Processes data** using domain logic (AI scoring, etc.)
3. **Interacts with database** via SQLAlchemy ORM
4. **Returns structured results** to endpoints
5. **Logs operations** for observability

All services are:
- Fully async (async/await)
- Type-safe (full type hints)
- Well-tested (unit testable)
- Well-documented (docstrings + markdown)
- Production-ready (error handling, logging)
