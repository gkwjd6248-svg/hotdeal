# Scraper Adapters Implementation Summary

## Overview

This document summarizes the implementation status of all scraper adapters for the DealHawk backend.

## Completed Adapters (3/6)

### 1. Naver Shopping Adapter ✓

**File**: `app/scrapers/adapters/naver.py`

**API Type**: REST JSON API
**Authentication**: Custom headers (`X-Naver-Client-Id`, `X-Naver-Client-Secret`)
**Rate Limit**: 15 requests per minute (25,000/day total)
**Documentation**: `README_NAVER.md`
**Example**: `examples/naver_adapter_usage.py`

**Key Features**:
- Multi-category keyword search (6 categories, ~25 keywords)
- HTML tag stripping (Naver returns `<b>` tags in product titles)
- Automatic deduplication by `productId`
- Auto-categorization using `CategoryClassifier`
- Retry logic with exponential backoff

**Price Fields**:
- `lprice` (lowest price) → `deal_price`
- `hprice` (highest price) → `original_price` (if > lprice)

---

### 2. Coupang Partners Adapter ✓

**File**: `app/scrapers/adapters/coupang.py`

**API Type**: REST JSON API
**Authentication**: HMAC-SHA256 signature (`ACCESS_KEY` + `SECRET_KEY`)
**Rate Limit**: 60 requests per minute
**Documentation**: `README_COUPANG.md`
**Example**: `examples/coupang_adapter_usage.py`

**Key Features**:
- HMAC-SHA256 request signing for authentication
- Signature format: `CEA algorithm=HmacSHA256, access-key={key}, signed-date={date}, signature={sig}`
- Message to sign: `{datetime}{method}{path}`
- Rocket delivery flag detection
- Multi-category keyword search

**Authentication Implementation**:
```python
def _generate_auth_headers(method, path, datetime_str):
    message = datetime_str + method + path
    signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    return {"Authorization": f"CEA algorithm=HmacSHA256, ..."}
```

**Price Fields**:
- `productPrice` → `deal_price`
- No original price in search results

**Special Metadata**:
- `isRocket`: Fast delivery flag
- `isFresh`: Fresh product flag
- `freeShipping`: Free shipping flag

---

### 3. 11st (11번가) Adapter ✓

**File**: `app/scrapers/adapters/eleven_st.py`

**API Type**: REST XML API (not JSON!)
**Authentication**: API key in query parameter (`key=API_KEY`)
**Rate Limit**: 2 requests per minute (conservative, 1,000/day limit)
**Documentation**: `README_ELEVEN_ST.md`
**Example**: `examples/eleven_st_adapter_usage.py`

**Key Features**:
- **XML Response Parsing**: Uses `xml.etree.ElementTree` to parse XML responses
- Discount percentage provided directly by API
- Graceful XML parse error handling with preview logging
- Multi-category keyword search

**XML Structure**:
```xml
<ProductSearchResponse>
  <Products>
    <Product>
      <ProductCode>123456</ProductCode>
      <ProductName>제품명</ProductName>
      <SalePrice>80000</SalePrice>
      <ProductPrice>100000</ProductPrice>
      <Discount>20</Discount>
      <DeliveryFee>2500</DeliveryFee>
      ...
    </Product>
  </Products>
</ProductSearchResponse>
```

**Price Fields**:
- `SalePrice` → `deal_price`
- `ProductPrice` → `original_price`
- `Discount` → `discount_percentage` (as percentage)

**Special Features**:
- Delivery fee tracking in metadata
- Handles both explicit discount and price-based discount calculation

---

## Adapter Architecture

### Base Classes

All adapters inherit from `BaseAPIAdapter` which provides:
- Common HTTP client patterns
- Rate limiting integration
- Error handling and retry logic
- Health check interface
- Cleanup lifecycle management

**Inheritance Chain**:
```
BaseAdapter (abstract)
└── BaseAPIAdapter
    ├── NaverShoppingAdapter
    ├── CoupangAdapter
    └── ElevenStAdapter
```

### Data Models

**NormalizedProduct**:
- `external_id`: Shop-specific product ID
- `title`: Product name
- `current_price`: Current price (Decimal)
- `original_price`: Original price if on sale
- `product_url`: Product page URL
- `image_url`: Product image URL
- `category_hint`: For auto-categorization
- `metadata`: Shop-specific additional data (dict)

**NormalizedDeal**:
- `product`: NormalizedProduct instance
- `deal_price`: Deal price (Decimal)
- `title`: Deal title
- `deal_url`: Deal page URL
- `original_price`: Price before discount
- `discount_percentage`: Discount as percentage
- `deal_type`: `price_drop`, `flash_sale`, `coupon`, `clearance`, `bundle`
- `metadata`: Shop-specific additional data (dict)

### Shared Utilities

**DomainRateLimiter** (`app/scrapers/utils/rate_limiter.py`):
- Token bucket algorithm
- Per-domain rate limiting
- Custom rate configuration per adapter

**PriceNormalizer** (`app/scrapers/utils/normalizer.py`):
- Clean price strings (remove `₩`, `,`, whitespace)
- Convert to Decimal for precise calculations
- Validate non-negative prices

**CategoryClassifier** (`app/scrapers/utils/normalizer.py`):
- Auto-categorize products based on title and shop category
- Keyword-based classification
- Supports Korean text

---

## Search Strategy

All adapters use the same 6-category keyword search strategy:

### Categories and Keywords

1. **pc-hardware**
   - 그래픽카드 특가, SSD 할인, CPU 특가, RAM DDR5 할인, 메인보드 특가

2. **laptop-mobile**
   - 노트북 특가, 스마트폰 할인, 태블릿 특가, 갤럭시 할인

3. **electronics-tv**
   - TV 특가, 모니터 할인, 세탁기 특가, 에어컨 할인, 냉장고 특가

4. **games-software**
   - 게임 특가, PS5 할인, 닌텐도 특가

5. **gift-cards**
   - 상품권 할인, 기프트카드 특가

6. **living-food**
   - 식품 특가, 생활용품 할인, 건강식품 특가

**Total**: ~25 keywords across 6 categories

---

## Error Handling Patterns

All adapters follow these error handling patterns:

### 1. Retry Logic
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
)
async def _call_api(...):
    ...
```

### 2. Rate Limit Detection
```python
if response.status_code == 429:
    logger.warning("rate_limit_hit", keyword=keyword)
    raise httpx.HTTPStatusError("Rate limit exceeded", ...)
```

### 3. Error Isolation
```python
for keyword in keywords:
    try:
        results = await self._call_api(keyword)
        # Process results...
    except Exception as e:
        logger.error("keyword_search_failed", keyword=keyword, error=str(e))
        # Continue with next keyword
```

### 4. Structured Logging
```python
logger.info("searching_shop", category=cat_slug, keyword=keyword)
logger.error("normalization_failed", product_id=product_id, error=str(e))
logger.debug("api_success", keyword=keyword, returned_items=len(items))
```

---

## Rate Limiting Summary

| Adapter | Domain | Rate Limit | Daily Limit | Notes |
|---------|--------|------------|-------------|-------|
| Naver | `openapi.naver.com` | 15 RPM | 25,000 | Conservative to avoid quota |
| Coupang | `api-gateway.coupang.com` | 60 RPM | Unknown | Standard tier |
| 11st | `openapi.11st.co.kr` | 2 RPM | 1,000 | Very conservative |

---

## Configuration (.env)

Required environment variables for all adapters:

```env
# Naver Shopping API
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret

# Coupang Partners API
COUPANG_ACCESS_KEY=your_access_key
COUPANG_SECRET_KEY=your_secret_key

# 11st Open API
ELEVEN_ST_API_KEY=your_api_key
```

All credentials are loaded via `app.config.settings` using Pydantic Settings.

---

## Testing

Each adapter includes:

1. **Example Script**: `examples/{adapter_name}_adapter_usage.py`
   - Basic usage examples
   - Category filtering
   - Product details fetching
   - Health checks
   - Deal analysis

2. **Health Check Method**: `await adapter.health_check()`
   - Returns `True` if API is accessible
   - Tests credentials validity
   - Logs success/failure

3. **Manual Testing**:
   ```bash
   cd backend
   python examples/naver_adapter_usage.py
   python examples/coupang_adapter_usage.py
   python examples/eleven_st_adapter_usage.py
   ```

---

## Next Steps

### Remaining Adapters (3/6 TODO)

1. **Gmarket** (Playwright scraper)
2. **AliExpress** (API adapter)
3. **Amazon** (API adapter - PA-API)

### Integration Tasks

1. Update scraper factory to auto-discover all adapters
2. Create unified scraper service that orchestrates all adapters
3. Implement scraper job scheduling (APScheduler)
4. Build API endpoints for:
   - Triggering scraper jobs
   - Viewing scraper job history
   - Health checks for all adapters
5. Store scraped deals in database

---

## File Locations

```
backend/
├── app/
│   ├── scrapers/
│   │   ├── adapters/
│   │   │   ├── __init__.py (exports all adapters)
│   │   │   ├── naver.py ✓
│   │   │   ├── coupang.py ✓
│   │   │   ├── eleven_st.py ✓
│   │   │   ├── README_NAVER.md
│   │   │   ├── README_COUPANG.md
│   │   │   ├── README_ELEVEN_ST.md
│   │   │   └── IMPLEMENTATION_SUMMARY.md (this file)
│   │   ├── base.py (base classes + data models)
│   │   ├── utils/
│   │   │   ├── rate_limiter.py
│   │   │   └── normalizer.py
│   │   └── factory.py
│   └── config.py (settings with API credentials)
└── examples/
    ├── naver_adapter_usage.py
    ├── coupang_adapter_usage.py
    └── eleven_st_adapter_usage.py
```

---

## Summary Statistics

- **Adapters Completed**: 3/6 (50%)
- **Total Lines of Code**: ~1,500 lines
- **API Types Supported**: JSON (2), XML (1)
- **Authentication Methods**: Custom Headers (1), HMAC-SHA256 (1), API Key (1)
- **Total Keywords**: ~25 across 6 categories
- **Rate Limit Range**: 2-60 RPM
- **Documentation Files**: 3 READMEs + 3 example scripts

---

**Last Updated**: 2026-02-17
**Status**: 3 adapters operational, ready for integration testing
