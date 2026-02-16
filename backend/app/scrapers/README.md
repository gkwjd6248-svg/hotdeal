# Scraper System Documentation

## Overview

The scraper system provides a flexible, extensible framework for fetching deals and product data from multiple e-commerce platforms. It supports both API-based adapters and web scraping adapters.

## Architecture

### Core Components

1. **BaseAdapter** - Abstract base class for all adapters
2. **BaseScraperAdapter** - Base class for Playwright-based web scrapers
3. **BaseAPIAdapter** - Base class for HTTP API adapters
4. **AdapterFactory** - Factory for creating and managing adapter instances
5. **Utility Modules** - Rate limiting, proxy management, data normalization

### Directory Structure

```
scrapers/
├── __init__.py          # Package exports
├── base.py              # Base adapter classes and data structures
├── factory.py           # Adapter factory
├── scheduler.py         # Scheduled scraping jobs (APScheduler)
├── adapters/            # Shop-specific adapter implementations
│   ├── __init__.py
│   ├── example_scraper.py  # Reference implementation
│   ├── coupang.py       # (to be implemented)
│   ├── naver.py         # (to be implemented)
│   └── ...
└── utils/               # Utility modules
    ├── __init__.py
    ├── rate_limiter.py  # Token bucket rate limiting
    ├── proxy_manager.py # Proxy rotation and health checking
    ├── user_agents.py   # User-Agent rotation
    ├── normalizer.py    # Price parsing and category classification
    └── retry.py         # Retry decorators with exponential backoff
```

## Creating a New Adapter

### 1. For Web Scraping (Playwright)

Inherit from `BaseScraperAdapter`:

```python
from app.scrapers.base import BaseScraperAdapter, NormalizedDeal, NormalizedProduct
from app.scrapers.utils import PriceNormalizer, CategoryClassifier
from bs4 import BeautifulSoup

class MyShopAdapter(BaseScraperAdapter):
    shop_slug = "myshop"
    shop_name = "My Shop"

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        context = await self._get_browser_context()
        page = await context.new_page()

        html = await self._safe_scrape(page, "https://myshop.com/deals")
        soup = BeautifulSoup(html, "lxml")

        # Parse deals from HTML
        deals = []
        for item in soup.select(".deal-item"):
            # Extract data and create NormalizedDeal
            pass

        await page.close()
        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        # Implement product detail scraping
        pass
```

### 2. For API-based Adapters

Inherit from `BaseAPIAdapter`:

```python
from app.scrapers.base import BaseAPIAdapter, NormalizedDeal
import httpx

class MyAPIAdapter(BaseAPIAdapter):
    shop_slug = "myshop-api"
    shop_name = "My Shop API"

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        # Use self.http_client for HTTP requests
        # Apply rate limiting via self.rate_limiter
        pass
```

### 3. Register the Adapter

```python
from app.scrapers.factory import adapter_factory
from .adapters.myshop import MyShopAdapter

# Register during app startup
adapter_factory.register_adapter("myshop", MyShopAdapter)
```

## Utility Modules

### Rate Limiter

Per-domain rate limiting using token bucket algorithm:

```python
from app.scrapers.utils import DomainRateLimiter

limiter = DomainRateLimiter()

# Acquires a token, waiting if necessary
await limiter.acquire("www.example.com")
```

Pre-configured limits for known domains (see `rate_limiter.py`).

### Proxy Manager

Rotating proxy pool with automatic health checking:

```python
from app.scrapers.utils import ProxyManager

proxy_manager = ProxyManager([
    "http://user:pass@proxy1.com:8080",
    "socks5://proxy2.com:1080",
])

proxy_url = proxy_manager.get_proxy()
# Use proxy_url with httpx or Playwright

# Mark success/failure for health tracking
proxy_manager.mark_success(proxy_url)
proxy_manager.mark_failed(proxy_url)

# Get stats
stats = proxy_manager.get_stats()
```

### User-Agent Rotation

```python
from app.scrapers.utils import get_random_user_agent

user_agent = get_random_user_agent()
```

### Price Normalization

```python
from app.scrapers.utils import PriceNormalizer

# Parse price strings
price = PriceNormalizer.clean_price_string("1,234원")  # -> Decimal("1234")

# Convert to KRW
krw_price = PriceNormalizer.to_krw(Decimal("10.99"), "USD")  # -> Decimal("14836")

# Extract price from text
price = PriceNormalizer.extract_price_from_text("Sale: 12,345원 (50% off)")
```

### Category Classification

```python
from app.scrapers.utils import CategoryClassifier

# Auto-classify based on keywords
category = CategoryClassifier.classify("RTX 4090 그래픽카드")  # -> "pc-hardware"

# With confidence score
category, confidence = CategoryClassifier.classify_with_confidence("노트북")
```

### Retry Decorators

```python
from app.scrapers.utils import http_retry, playwright_retry

@http_retry
async def fetch_data():
    # HTTP request with automatic retry
    pass

@playwright_retry
async def scrape_page():
    # Playwright scraping with automatic retry
    pass
```

## Data Structures

### NormalizedProduct

```python
@dataclass
class NormalizedProduct:
    external_id: str              # Shop-specific product ID
    title: str                    # Product title
    current_price: Decimal        # Current price
    product_url: str              # Product page URL
    original_price: Optional[Decimal] = None
    currency: str = "KRW"
    image_url: Optional[str] = None
    brand: Optional[str] = None
    category_hint: Optional[str] = None  # Auto-classified category
    description: Optional[str] = None
    metadata: dict = field(default_factory=dict)
```

### NormalizedDeal

```python
@dataclass
class NormalizedDeal:
    product: NormalizedProduct    # Associated product
    deal_price: Decimal           # Deal price
    title: str                    # Deal title
    deal_url: str                 # Deal page URL
    original_price: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    deal_type: str = "price_drop" # 'price_drop', 'flash_sale', 'coupon', etc.
    description: Optional[str] = None
    image_url: Optional[str] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)
```

## Configuration

Set environment variables in `.env`:

```bash
# Proxy configuration (comma-separated)
PROXY_LIST=http://user:pass@proxy1.com:8080,socks5://proxy2.com:1080

# API credentials (per shop)
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_secret
COUPANG_ACCESS_KEY=your_key
# ...
```

## Usage Example

```python
from app.scrapers.factory import adapter_factory

# Create adapter
adapter = adapter_factory.create_adapter("coupang")

# Fetch deals
deals = await adapter.fetch_deals(category="pc-hardware")

# Fetch product details
product = await adapter.fetch_product_details("12345")

# Health check
is_healthy = await adapter.health_check()
```

## Anti-Detection Features

The scraper system includes several anti-detection measures:

1. **Rate Limiting** - Respects per-domain rate limits
2. **User-Agent Rotation** - Randomizes user-agent headers
3. **Proxy Rotation** - Routes requests through proxy pool
4. **Request Delays** - Token bucket ensures natural request spacing
5. **Retry Logic** - Exponential backoff on failures

## Testing

See `app/scrapers/adapters/example_scraper.py` for a complete reference implementation.

## Notes

- Always use `await self._safe_scrape()` for Playwright scraping to apply rate limiting
- Mark adapter methods with `@playwright_retry` or `@http_retry` for automatic retries
- Use `PriceNormalizer` for all price parsing to ensure consistency
- Use `normalize_url()` to remove tracking parameters from URLs
- Category classification is a hint; manual categorization may be needed
