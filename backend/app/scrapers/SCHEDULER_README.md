# Scraper Scheduler Documentation

## Overview

The DealHawk scraper scheduler is built on APScheduler and orchestrates periodic scraping jobs for all active e-commerce shops. It automatically loads shop configurations from the database and schedules jobs at their configured intervals.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  (app/main.py - lifespan startup/shutdown)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  ScraperScheduler    │  (app/scrapers/scheduler.py)
          │  - APScheduler       │
          │  - Job management    │
          │  - Error handling    │
          └──────────┬───────────┘
                     │
                     │ For each shop job:
                     ▼
          ┌──────────────────────┐
          │  ScraperService      │  (app/scrapers/scraper_service.py)
          │  - Adapter → DB      │
          │  - Processing flow   │
          └──────────┬───────────┘
                     │
         ┌───────────┴────────────┐
         ▼                        ▼
   ┌─────────────┐         ┌─────────────┐
   │   Adapter   │         │  Services   │
   │  (Naver,    │         │  - Product  │
   │   Coupang,  │────────▶│  - Deal     │
   │   etc.)     │         │  - Price    │
   └─────────────┘         └─────────────┘
                                  │
                                  ▼
                           ┌──────────────┐
                           │  PostgreSQL  │
                           │  - Products  │
                           │  - Deals     │
                           │  - Jobs      │
                           └──────────────┘
```

## Components

### 1. ScraperScheduler (`app/scrapers/scheduler.py`)

Main scheduler class that manages periodic jobs.

**Methods:**
- `start()` - Start the scheduler
- `stop()` - Stop the scheduler gracefully
- `load_shop_jobs()` - Load and schedule jobs for all active shops from database
- `add_shop_job(shop_slug, interval_minutes, offset_seconds)` - Add a single shop job
- `remove_shop_job(shop_slug)` - Remove a shop job
- `run_shop_scrape(shop_slug)` - Execute a single scrape job (called by APScheduler)
- `get_jobs_status()` - Get status of all scheduled jobs
- `is_running()` - Check if scheduler is running

**Job Execution Flow:**
1. Create `ScraperJob` record with status="running"
2. Call `ScraperService.run_adapter(shop_slug)`
3. Update `ScraperJob` with results (success/failure)
4. Log metrics to database

**Error Handling:**
- All exceptions are caught and logged
- Job failures don't stop the scheduler
- Error details recorded to `scraper_jobs` table

### 2. ScraperService (`app/scrapers/scraper_service.py`)

Orchestrates the data flow from adapters to database services.

**Methods:**
- `run_adapter(shop_slug, category)` - Run a single adapter and process results
- `process_deals(deals, shop_slug)` - Process normalized deals into database

**Processing Flow (per deal):**
1. Auto-categorize product if `category_hint` provided
2. Upsert product via `ProductService.upsert_product()`
   - Records price history automatically
3. Compute AI score via `PriceAnalyzer.compute_deal_score()`
4. Create/update deal via `DealService.create_or_update_deal()`

**Returns:**
```python
{
    "deals_fetched": int,
    "products_created": int,
    "products_updated": int,
    "deals_created": int,
    "deals_updated": int,
    "errors": int
}
```

### 3. Adapter Registration (`app/scrapers/register_adapters.py`)

Registers all available adapters with the factory on startup.

**Registered Adapters:**
- `naver` - NaverShoppingAdapter (API-based)
- `coupang` - CoupangAdapter (Playwright scraper)
- `11st` - ElevenStAdapter (API-based)

## Configuration

### Shop Configuration (database)

Shops are configured in the `shops` table:

```sql
CREATE TABLE shops (
    id UUID PRIMARY KEY,
    slug VARCHAR(50) UNIQUE,
    name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    scrape_interval_minutes INTEGER DEFAULT 60,
    adapter_type VARCHAR(20) -- 'api' or 'scraper'
    ...
);
```

**Key Fields:**
- `is_active` - Whether scraping is enabled for this shop
- `scrape_interval_minutes` - How often to scrape (default: 60 minutes)
- `adapter_type` - Type of adapter ('api' or 'scraper')

### Default Intervals (from project_plan.md)

- **API shops** (Naver, 11st): 15 minutes
- **Scraper shops** (Coupang): 30 minutes

### Job Staggering

To avoid thundering herd, jobs are staggered by `shop_index * 30 seconds`:
- Shop 1: Starts immediately
- Shop 2: Starts after 30 seconds
- Shop 3: Starts after 60 seconds
- etc.

This distributes load and prevents all jobs from firing simultaneously.

## Usage

### Automatic Startup (Production)

The scheduler automatically starts on application startup (except in test environment):

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register adapters
    register_all_adapters()

    # Start scheduler (auto-loads shop jobs)
    if settings.ENVIRONMENT != "test":
        scheduler = ScraperScheduler(async_session_factory)
        scheduler.start()
        await scheduler.load_shop_jobs()

    yield

    # Shutdown
    scheduler.stop()
```

### Manual Control

```python
from app.scrapers.scheduler import ScraperScheduler
from app.db.session import async_session_factory

# Create scheduler
scheduler = ScraperScheduler(async_session_factory)

# Start scheduler
scheduler.start()

# Load jobs from database
await scheduler.load_shop_jobs()

# Add a single job manually
scheduler.add_shop_job(
    shop_slug="naver",
    interval_minutes=15,
    offset_seconds=0
)

# Remove a job
scheduler.remove_shop_job("naver")

# Check status
status = scheduler.get_jobs_status()
print(status)

# Stop scheduler
scheduler.stop()
```

### Run a Single Scrape Manually

```python
from app.scrapers.scraper_service import ScraperService
from app.db.session import async_session_factory

async with async_session_factory() as db:
    service = ScraperService(db)
    stats = await service.run_adapter("naver")
    print(stats)
```

## Monitoring

### ScraperJob Records

Every scrape job creates a record in `scraper_jobs` table:

```sql
SELECT
    shop.slug,
    sj.status,
    sj.started_at,
    sj.completed_at,
    sj.duration_seconds,
    sj.items_found,
    sj.items_created,
    sj.deals_detected,
    sj.error_message
FROM scraper_jobs sj
JOIN shops shop ON sj.shop_id = shop.id
ORDER BY sj.started_at DESC
LIMIT 10;
```

### Job Status API (TODO)

Future endpoint for monitoring:
```
GET /api/v1/admin/scheduler/status
GET /api/v1/admin/scheduler/jobs
POST /api/v1/admin/scheduler/jobs/{shop_slug}/run
```

## Logs

Scheduler uses `structlog` for structured logging:

```json
{
  "event": "scrape_job_completed",
  "shop_slug": "naver",
  "job_id": "uuid",
  "duration_seconds": 12.45,
  "deals_fetched": 150,
  "products_created": 10,
  "products_updated": 140,
  "deals_created": 25,
  "deals_updated": 125,
  "timestamp": "2026-02-17T10:30:00Z"
}
```

**Key Events:**
- `scheduler_started` - Scheduler initialized
- `shop_jobs_loaded` - Jobs loaded from database
- `shop_job_added` - Job registered with APScheduler
- `starting_scrape_job` - Job execution started
- `scrape_job_completed` - Job finished successfully
- `scrape_job_failed` - Job failed with error

## Troubleshooting

### Jobs Not Running

1. **Check if scheduler is running:**
   ```python
   scheduler.is_running()  # Should return True
   ```

2. **Check shop is active:**
   ```sql
   SELECT slug, is_active FROM shops WHERE slug = 'naver';
   ```

3. **Check adapter is registered:**
   ```python
   from app.scrapers.factory import get_adapter_factory
   factory = get_adapter_factory()
   print(factory.get_registered_shops())
   ```

4. **Check logs for errors:**
   ```bash
   tail -f logs/dealhawk.log | grep scraper
   ```

### Job Failures

Check `scraper_jobs` table for error details:
```sql
SELECT
    shop.slug,
    sj.error_message,
    sj.error_traceback
FROM scraper_jobs sj
JOIN shops shop ON sj.shop_id = shop.id
WHERE sj.status = 'failed'
ORDER BY sj.started_at DESC
LIMIT 5;
```

Common failures:
- **Adapter not found** - Adapter not registered with factory
- **API credentials missing** - Check `.env` for API keys
- **Rate limit exceeded** - Increase scrape interval
- **Network timeout** - Check network connectivity
- **Parsing error** - Website structure changed

### Memory Leaks

If scheduler runs for long periods:
1. Monitor memory usage: `ps aux | grep python`
2. Check for unclosed browser contexts (Playwright)
3. Ensure adapters implement `cleanup()` method

## Best Practices

1. **Start with long intervals** - Test with 60+ minute intervals, reduce gradually
2. **Monitor rate limits** - Respect API quotas and `robots.txt`
3. **Handle failures gracefully** - Don't let one job failure stop the scheduler
4. **Log everything** - Structured logs help debugging
5. **Clean up resources** - Always implement adapter `cleanup()` methods
6. **Use job staggering** - Prevent thundering herd on startup
7. **Test manually first** - Run `ScraperService.run_adapter()` before scheduling

## Future Enhancements

- [ ] Admin API for scheduler control
- [ ] Job priority and dependencies
- [ ] Pause/resume individual jobs
- [ ] Job history retention policy
- [ ] Alerting on consecutive failures
- [ ] Dynamic interval adjustment based on deal volume
- [ ] Circuit breaker for failing shops
- [ ] Job metrics dashboard
