# Scraper System Implementation Summary

## Completed Files

### 1. Core Base Classes (`base.py`)
- **NormalizedProduct** - Data structure for product information
  - Fields: external_id, title, current_price, product_url, original_price, currency, image_url, brand, category_hint, description, metadata
  - Includes validation in `__post_init__`

- **NormalizedDeal** - Data structure for deal information
  - Fields: product, deal_price, title, deal_url, original_price, discount_percentage, deal_type, description, image_url, starts_at, expires_at, metadata
  - Supports deal types: price_drop, flash_sale, coupon, clearance, bundle

- **BaseAdapter** - Abstract base class for all adapters
  - Abstract methods: `fetch_deals()`, `fetch_product_details()`
  - Helper methods: `health_check()`, `_calculate_discount_percentage()`
  - Properties: shop_slug, shop_name, adapter_type
  - Dependency injection: rate_limiter, logger

- **BaseScraperAdapter** - Base for Playwright-based scrapers
  - Methods: `_get_browser_context()`, `_safe_scrape()`, `cleanup()`
  - Additional dependency injection: proxy_manager, browser_context

- **BaseAPIAdapter** - Base for HTTP API adapters
  - Dependency injection: http_client

### 2. Utility Modules (`utils/`)

#### rate_limiter.py
- **TokenBucket** - Token bucket algorithm implementation
  - Thread-safe with asyncio.Lock
  - Configurable rate and capacity
  - Automatic token refill

- **DomainRateLimiter** - Per-domain rate limiting
  - Pre-configured limits for 17+ domains (Korean and international e-commerce)
  - Default 10 RPM for unknown domains
  - Methods: `acquire()`, `set_custom_limit()`, `get_current_rate()`

#### proxy_manager.py
- **ProxyEntry** - Proxy configuration with health tracking
  - Tracks: fail_count, success_count, last_used, last_failed, last_success
  - Methods: `mark_failed()`, `mark_success()`, `should_retry()`

- **ProxyManager** - Rotating proxy pool
  - Strategies: round-robin, random
  - Automatic health checking and failover
  - Configurable cooldown for failed proxies (default 10 minutes)
  - Methods: `get_proxy()`, `mark_failed()`, `mark_success()`, `get_stats()`, `reset_all()`

- **NoProxyManager** - Dummy proxy manager for development

#### user_agents.py
- 15+ realistic user-agent strings (Chrome, Firefox, Safari, Edge)
- Functions:
  - `get_random_user_agent()`
  - `get_chrome_user_agent()`
  - `get_firefox_user_agent()`
  - `get_safari_user_agent()`
  - `get_mobile_user_agent()`
  - `get_user_agent_by_browser(browser_name)`

#### normalizer.py
- **CATEGORY_KEYWORDS** - Keyword mapping for 6 categories:
  - pc-hardware
  - laptop-mobile
  - electronics-tv
  - games-software
  - gift-cards
  - living-food

- **PriceNormalizer**
  - Exchange rates for USD, CNY, JPY, EUR, GBP to KRW
  - Methods:
    - `to_krw(price, currency)` - Convert to KRW
    - `clean_price_string(raw)` - Parse price string
    - `extract_price_from_text(text)` - Extract first price from text

- **CategoryClassifier**
  - Methods:
    - `classify(title, shop_category)` - Auto-classify by keywords
    - `classify_with_confidence(title)` - Classify with confidence score

- **normalize_url(url)** - Remove tracking parameters

#### retry.py
- **http_retry** - Retry decorator for httpx requests
  - 3 attempts, exponential backoff (2-30s)
  - Retries on: HTTPStatusError, ConnectError, TimeoutException, ReadTimeout, ConnectTimeout

- **playwright_retry** - Retry decorator for Playwright
  - 3 attempts, exponential backoff (2-30s)
  - Retries on: PlaywrightError, TimeoutError

- **critical_retry** - Aggressive retry for critical operations
  - 5 attempts, exponential backoff (4-60s)

### 3. Factory Pattern (`factory.py`)
- **AdapterFactory** - Creates and manages adapter instances
  - Singleton pattern with `adapter_factory` global instance
  - Methods:
    - `register_adapter(shop_slug, adapter_class)`
    - `create_adapter(shop_slug)` - Creates adapter with dependency injection
    - `get_registered_shops()`
    - `has_adapter(shop_slug)`
  - Initializes shared services:
    - DomainRateLimiter
    - ProxyManager (from settings)

### 4. Configuration (`config.py` - updated)
- Added `get_proxy_list()` method to parse PROXY_LIST environment variable

### 5. Example Implementation (`adapters/example_scraper.py`)
- **ExampleScraperAdapter** - Reference implementation showing:
  - How to use BaseScraperAdapter
  - How to parse HTML with BeautifulSoup
  - How to use utility modules
  - Proper error handling and logging
  - Example selector patterns

### 6. Documentation
- **README.md** - Comprehensive documentation covering:
  - Architecture overview
  - How to create new adapters
  - Utility module usage
  - Data structures
  - Configuration
  - Anti-detection features
  - Testing

- **IMPLEMENTATION_SUMMARY.md** - This file

## Key Design Patterns

### 1. Dependency Injection
Adapters receive dependencies (rate_limiter, proxy_manager, logger, http_client) through the factory, making testing easier and allowing shared resource management.

### 2. Strategy Pattern
Different adapter types (scraper vs API) share the same interface but implement different strategies for data fetching.

### 3. Factory Pattern
AdapterFactory centralizes adapter creation and configuration, ensuring consistent setup.

### 4. Template Method Pattern
BaseScraperAdapter provides template methods (`_safe_scrape`, `_get_browser_context`) that subclasses use but don't override.

### 5. Data Transfer Objects
NormalizedProduct and NormalizedDeal are immutable dataclasses that ensure type safety and validation.

## Anti-Detection Features

1. **Rate Limiting** - Token bucket per domain with sensible defaults
2. **Proxy Rotation** - Automatic proxy rotation with health checking
3. **User-Agent Rotation** - Randomized realistic user-agents
4. **Request Spacing** - Natural delays between requests
5. **Retry Logic** - Exponential backoff prevents thundering herd
6. **URL Normalization** - Removes tracking parameters

## Integration Points

### With Database Models
NormalizedProduct and NormalizedDeal map to:
- `Product` model (external_id, title, price, etc.)
- `Deal` model (deal_price, discount, type, etc.)

### With Scheduler
Adapters can be invoked by APScheduler jobs in `scheduler.py`

### With API Endpoints
FastAPI endpoints can use adapters to fetch fresh data on-demand

## Next Steps

To complete the scraper system:

1. **Implement Shop-Specific Adapters**
   - Coupang scraper/API adapter
   - Naver Shopping API adapter
   - 11st API adapter
   - SSG scraper
   - Gmarket scraper
   - etc.

2. **Playwright Service**
   - Create service to manage Playwright browser lifecycle
   - Implement browser context creation with anti-detection
   - Handle browser pool for concurrent scraping

3. **Scraper Service Layer**
   - Service to coordinate adapter usage
   - Map NormalizedProduct/NormalizedDeal to database models
   - Handle deduplication and updates

4. **Scheduler Implementation**
   - Configure APScheduler jobs per shop
   - Implement job error handling and retry
   - Add job monitoring and metrics

5. **Testing**
   - Unit tests for utility modules
   - Integration tests for adapters
   - Mock responses for external dependencies

6. **Monitoring**
   - Add metrics collection (Prometheus)
   - Error tracking and alerting
   - Scraping success/failure dashboards

## File Locations

All files are in `C:\Users\gkwjd\Downloads\shopping\backend\app\scrapers\`:

```
scrapers/
├── __init__.py                     # Package exports
├── base.py                         # BaseAdapter, NormalizedProduct, NormalizedDeal
├── factory.py                      # AdapterFactory
├── scheduler.py                    # (existing placeholder)
├── README.md                       # Documentation
├── IMPLEMENTATION_SUMMARY.md       # This file
├── adapters/
│   ├── __init__.py                 # Adapter exports
│   └── example_scraper.py          # Reference implementation
└── utils/
    ├── __init__.py                 # Utility exports
    ├── rate_limiter.py             # DomainRateLimiter, TokenBucket
    ├── proxy_manager.py            # ProxyManager, ProxyEntry
    ├── user_agents.py              # User-agent rotation
    ├── normalizer.py               # PriceNormalizer, CategoryClassifier
    └── retry.py                    # Retry decorators
```

## Usage Example

```python
# Register an adapter
from app.scrapers.factory import adapter_factory
from app.scrapers.adapters.coupang import CoupangAdapter

adapter_factory.register_adapter("coupang", CoupangAdapter)

# Create and use adapter
adapter = adapter_factory.create_adapter("coupang")
deals = await adapter.fetch_deals(category="pc-hardware")

# Process deals
for deal in deals:
    print(f"{deal.title}: {deal.deal_price} KRW ({deal.discount_percentage}% off)")
```

## Dependencies Used

All dependencies are already in `requirements.txt`:
- playwright==1.49.1 (for scraping)
- beautifulsoup4==4.12.3 (for HTML parsing)
- lxml==5.3.0 (BeautifulSoup parser)
- httpx==0.28.1 (for HTTP requests)
- tenacity==9.0.0 (for retry logic)
- structlog==24.4.0 (for logging)

No additional dependencies need to be added.
