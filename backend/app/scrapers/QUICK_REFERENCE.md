# Quick Reference Guide

## Import Statements

```python
# Base classes and data structures
from app.scrapers.base import (
    BaseAdapter,
    BaseScraperAdapter,
    BaseAPIAdapter,
    NormalizedProduct,
    NormalizedDeal,
)

# Factory
from app.scrapers.factory import adapter_factory

# Utilities
from app.scrapers.utils import (
    # Rate limiting
    DomainRateLimiter,
    # Proxy management
    ProxyManager,
    ProxyEntry,
    NoProxyManager,
    # User agents
    get_random_user_agent,
    get_chrome_user_agent,
    # Price parsing
    PriceNormalizer,
    # Category classification
    CategoryClassifier,
    # URL normalization
    normalize_url,
    # Retry decorators
    http_retry,
    playwright_retry,
    critical_retry,
)
```

## Creating a Scraper Adapter

```python
from typing import List, Optional
from decimal import Decimal
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraperAdapter, NormalizedDeal, NormalizedProduct
from app.scrapers.utils import PriceNormalizer, CategoryClassifier, normalize_url
from app.scrapers.utils.retry import playwright_retry


class MyShopAdapter(BaseScraperAdapter):
    shop_slug = "myshop"
    shop_name = "My Shop"

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        deals = []
        url = "https://www.myshop.com/deals"

        context = await self._get_browser_context()
        page = await context.new_page()

        html = await self._scrape_with_retry(page, url, ".deal-item")
        soup = BeautifulSoup(html, "lxml")

        for item in soup.select(".deal-item"):
            deal = self._parse_deal(item)
            if deal:
                deals.append(deal)

        await page.close()
        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        url = f"https://www.myshop.com/product/{external_id}"

        context = await self._get_browser_context()
        page = await context.new_page()

        html = await self._scrape_with_retry(page, url, ".product-detail")
        soup = BeautifulSoup(html, "lxml")

        product = self._parse_product(soup, external_id)

        await page.close()
        return product

    @playwright_retry
    async def _scrape_with_retry(self, page, url: str, selector: str) -> str:
        """Wrapper with retry decorator."""
        return await self._safe_scrape(page, url, wait_selector=selector)

    def _parse_deal(self, item) -> Optional[NormalizedDeal]:
        try:
            title = item.select_one(".title").get_text(strip=True)
            deal_url = normalize_url(item.select_one("a")["href"])
            price_text = item.select_one(".price").get_text(strip=True)
            deal_price = PriceNormalizer.clean_price_string(price_text)

            if not deal_price:
                return None

            product = NormalizedProduct(
                external_id=self._extract_id(deal_url),
                title=title,
                current_price=deal_price,
                product_url=deal_url,
                currency="KRW",
                category_hint=CategoryClassifier.classify(title),
            )

            return NormalizedDeal(
                product=product,
                deal_price=deal_price,
                title=title,
                deal_url=deal_url,
                deal_type="price_drop",
            )
        except Exception as e:
            self.logger.warning("parse_failed", error=str(e))
            return None

    def _parse_product(self, soup, external_id: str) -> Optional[NormalizedProduct]:
        # Similar parsing logic
        pass

    def _extract_id(self, url: str) -> str:
        import re
        match = re.search(r"/product/(\w+)", url)
        return match.group(1) if match else url[-16:]
```

## Creating an API Adapter

```python
from app.scrapers.base import BaseAPIAdapter, NormalizedDeal
from app.scrapers.utils import PriceNormalizer, http_retry
import httpx


class MyAPIAdapter(BaseAPIAdapter):
    shop_slug = "myshop-api"
    shop_name = "My Shop API"

    def __init__(self):
        super().__init__()
        self.api_key = settings.MYSHOP_API_KEY
        self.base_url = "https://api.myshop.com/v1"

    @http_retry
    async def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make API request with retry."""
        url = f"{self.base_url}/{endpoint}"

        # Rate limiting
        if self.rate_limiter:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            await self.rate_limiter.acquire(domain)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={"X-API-Key": self.api_key},
            )
            response.raise_for_status()
            return response.json()

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        data = await self._request("deals", {"category": category})
        deals = []

        for item in data.get("deals", []):
            deal = self._parse_api_deal(item)
            if deal:
                deals.append(deal)

        return deals

    def _parse_api_deal(self, item: dict) -> Optional[NormalizedDeal]:
        # Parse API response
        pass
```

## Registering and Using Adapters

```python
# In app startup (main.py or similar)
from app.scrapers.factory import adapter_factory
from app.scrapers.adapters.myshop import MyShopAdapter

# Register adapter
adapter_factory.register_adapter("myshop", MyShopAdapter)

# Later, in route handler or service
adapter = adapter_factory.create_adapter("myshop")

# Fetch deals
deals = await adapter.fetch_deals(category="pc-hardware")

# Fetch product
product = await adapter.fetch_product_details("12345")

# Health check
is_healthy = await adapter.health_check()
```

## Common Utility Usage

### Parse Price

```python
from app.scrapers.utils import PriceNormalizer

# Parse Korean price
price = PriceNormalizer.clean_price_string("1,234원")  # Decimal("1234")

# Parse US price
price = PriceNormalizer.clean_price_string("$12.99")  # Decimal("12.99")

# Extract from text
price = PriceNormalizer.extract_price_from_text("판매가: 123,456원")

# Convert to KRW
krw = PriceNormalizer.to_krw(Decimal("19.99"), "USD")  # Decimal("26986")
```

### Auto-Categorize

```python
from app.scrapers.utils import CategoryClassifier

# Simple classification
category = CategoryClassifier.classify("RTX 4090 그래픽카드")  # "pc-hardware"

# With confidence
category, confidence = CategoryClassifier.classify_with_confidence("아이폰15 프로")
# ("laptop-mobile", 0.67)
```

### Rate Limiting

```python
from app.scrapers.utils import DomainRateLimiter

limiter = DomainRateLimiter()

# Acquire token (waits if necessary)
await limiter.acquire("www.coupang.com")

# Set custom limit
limiter.set_custom_limit("www.example.com", 30)  # 30 RPM
```

### Proxy Management

```python
from app.scrapers.utils import ProxyManager

manager = ProxyManager([
    "http://proxy1.com:8080",
    "http://user:pass@proxy2.com:8080",
])

# Get proxy
proxy_url = manager.get_proxy()

# After request
manager.mark_success(proxy_url)  # or mark_failed()

# Check stats
stats = manager.get_stats()
# {
#   "total_proxies": 2,
#   "healthy_proxies": 2,
#   "total_requests": 150,
#   "success_rate_percent": 94.5
# }
```

### User Agent Rotation

```python
from app.scrapers.utils import get_random_user_agent, get_chrome_user_agent

# Random UA
ua = get_random_user_agent()

# Specific browser
ua = get_chrome_user_agent()
```

### Retry Decorators

```python
from app.scrapers.utils import http_retry, playwright_retry

# HTTP request with retry
@http_retry
async def fetch_api_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        response.raise_for_status()
        return response.json()

# Playwright scraping with retry
@playwright_retry
async def scrape_page(page, url):
    await page.goto(url)
    return await page.content()
```

## Data Structures

### Creating NormalizedProduct

```python
from decimal import Decimal
from app.scrapers.base import NormalizedProduct

product = NormalizedProduct(
    external_id="12345",
    title="RTX 4090 Gaming GPU",
    current_price=Decimal("2499000"),
    product_url="https://shop.com/product/12345",
    original_price=Decimal("2799000"),
    currency="KRW",
    image_url="https://shop.com/images/12345.jpg",
    brand="NVIDIA",
    category_hint="pc-hardware",
    description="High-performance graphics card",
    metadata={"stock": "in_stock", "seller": "Official Store"},
)
```

### Creating NormalizedDeal

```python
from app.scrapers.base import NormalizedDeal
from datetime import datetime, timedelta

deal = NormalizedDeal(
    product=product,  # NormalizedProduct instance
    deal_price=Decimal("2299000"),
    title="RTX 4090 특가 세일",
    deal_url="https://shop.com/deals/12345",
    original_price=Decimal("2799000"),
    discount_percentage=Decimal("17.86"),
    deal_type="flash_sale",
    description="오늘만 특가",
    image_url="https://shop.com/images/12345.jpg",
    starts_at=datetime.utcnow(),
    expires_at=datetime.utcnow() + timedelta(hours=24),
    metadata={"badge": "HOT DEAL", "quantity_left": 5},
)
```

## Configuration

### Environment Variables

```bash
# .env file
PROXY_LIST=http://proxy1.com:8080,http://user:pass@proxy2.com:8080

# API Keys (per shop)
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
COUPANG_ACCESS_KEY=your_access_key
```

### Using in Code

```python
from app.config import settings

# Get proxy list
proxies = settings.get_proxy_list()

# Get API credentials
api_key = settings.NAVER_CLIENT_ID
```

## BeautifulSoup Parsing Patterns

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, "lxml")

# Select single element
title = soup.select_one(".product-title").get_text(strip=True)

# Select multiple elements
items = soup.select(".deal-item")

# Get attribute
url = item.select_one("a")["href"]
image = item.select_one("img")["src"]

# Conditional selection
price = soup.select_one(".sale-price")
if not price:
    price = soup.select_one(".regular-price")

# Safe attribute access
link = item.select_one("a")
url = link["href"] if link else None
```

## Error Handling Patterns

```python
# Log and skip individual items
for item in items:
    try:
        deal = parse_deal(item)
        deals.append(deal)
    except Exception as e:
        self.logger.warning("parse_failed", error=str(e))
        continue  # Skip this item

# Log and raise for critical errors
try:
    html = await self._safe_scrape(page, url)
except Exception as e:
    self.logger.error("scrape_failed", url=url, error=str(e))
    raise  # Propagate error

# Return None for not found
try:
    product = parse_product(soup)
    return product
except Exception as e:
    self.logger.error("parse_failed", error=str(e))
    return None  # Graceful degradation
```
