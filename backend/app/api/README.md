# DealHawk API Documentation

Complete API documentation for the DealHawk backend.

## Base URL

```
http://localhost:8000/api/v1
```

## Response Envelope

All API responses follow a standard envelope format:

```json
{
  "status": "success",
  "data": [...],
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

## Endpoints

### Health Check

#### GET `/health`

Check service health status.

**Response:**
```json
{
  "status": "ok",
  "database": "ok",
  "services": {
    "database": "ok"
  }
}
```

---

### Deals

#### GET `/deals`

List active deals with pagination and filtering.

**Query Parameters:**
- `page` (int, default: 1): Page number
- `limit` (int, default: 20, max: 100): Items per page
- `category` (string, optional): Category slug filter
- `shop` (string, optional): Shop slug filter
- `sort_by` (string, default: "newest"): Sort method (`newest`, `score`, `discount`, `views`)
- `min_discount` (float, optional): Minimum discount percentage (0-100)
- `deal_type` (string, optional): Deal type filter

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "title": "Product Title",
      "deal_price": 19900,
      "original_price": 29900,
      "discount_percentage": 33.44,
      "ai_score": 85.5,
      "ai_reasoning": "Great deal...",
      "deal_type": "price_drop",
      "deal_url": "https://...",
      "image_url": "https://...",
      "is_active": true,
      "expires_at": "2024-02-20T12:00:00Z",
      "created_at": "2024-02-15T10:00:00Z",
      "view_count": 150,
      "vote_up": 42,
      "comment_count": 5,
      "shop": {
        "name": "쿠팡",
        "slug": "coupang",
        "logo_url": "https://...",
        "country": "KR"
      },
      "category": {
        "name": "전자제품",
        "slug": "electronics"
      }
    }
  ],
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

#### GET `/deals/top`

Get top AI-scored deals.

**Query Parameters:**
- `limit` (int, default: 20, max: 50): Number of deals to return
- `category` (string, optional): Category slug filter

#### GET `/deals/{deal_id}`

Get detailed deal information including price history.

**Response includes:**
- All fields from list endpoint
- `description`: Deal description
- `starts_at`: Deal start time
- `vote_down`: Downvote count
- `price_history`: Array of price history points (last 30 days)

#### POST `/deals/{deal_id}/vote`

Vote on a deal.

**Request Body:**
```json
{
  "vote_type": "up"  // or "down"
}
```

---

### Categories

#### GET `/categories`

List all categories.

**Query Parameters:**
- `tree` (bool, default: false): Return hierarchical tree structure

**Flat Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "name": "전자제품",
      "name_en": "Electronics",
      "slug": "electronics",
      "icon": "cpu",
      "sort_order": 1,
      "parent_id": null,
      "deal_count": 150
    }
  ]
}
```

**Tree Response (tree=true):**
```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "name": "전자제품",
      "name_en": "Electronics",
      "slug": "electronics",
      "icon": "cpu",
      "sort_order": 1,
      "parent_id": null,
      "deal_count": 150,
      "children": [
        {
          "id": "uuid",
          "name": "PC/하드웨어",
          "name_en": "PC/Hardware",
          "slug": "pc-hardware",
          "icon": "desktop",
          "sort_order": 1,
          "parent_id": "parent-uuid",
          "deal_count": 45,
          "children": []
        }
      ]
    }
  ]
}
```

#### GET `/categories/{slug}/deals`

Get deals in a specific category.

**Query Parameters:**
- `page` (int)
- `limit` (int)
- `sort_by` (string)

---

### Shops

#### GET `/shops`

List all shopping platforms.

**Query Parameters:**
- `active_only` (bool, default: true): Only return active shops

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "name": "쿠팡",
      "name_en": "Coupang",
      "slug": "coupang",
      "logo_url": "https://...",
      "base_url": "https://www.coupang.com",
      "adapter_type": "scraper",
      "is_active": true,
      "country": "KR",
      "currency": "KRW",
      "deal_count": 250
    }
  ]
}
```

#### GET `/shops/{slug}`

Get shop details.

#### GET `/shops/{slug}/deals`

Get deals from a specific shop.

**Query Parameters:**
- `page` (int)
- `limit` (int)
- `sort_by` (string)

---

### Products

#### GET `/products`

List products with pagination.

**Query Parameters:**
- `page` (int)
- `limit` (int, default: 50)
- `shop_id` (UUID, optional)
- `category_id` (UUID, optional)
- `active_only` (bool, default: true)

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "title": "Product Title",
      "original_price": 29900,
      "current_price": 19900,
      "currency": "KRW",
      "image_url": "https://...",
      "product_url": "https://...",
      "brand": "Samsung",
      "external_id": "12345"
    }
  ],
  "meta": { ... }
}
```

#### GET `/products/{product_id}`

Get product details.

#### GET `/products/{product_id}/price-history`

Get price history for a product.

**Query Parameters:**
- `days` (int, default: 30, max: 365): Number of days to look back

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "price": 19900,
      "recorded_at": "2024-02-15T10:00:00Z"
    }
  ]
}
```

#### GET `/products/{product_id}/price-statistics`

Get price statistics.

**Query Parameters:**
- `days` (int, default: 90, max: 365)

**Response:**
```json
{
  "status": "success",
  "data": {
    "product_id": "uuid",
    "days_analyzed": 90,
    "min_price": 15000,
    "max_price": 35000,
    "avg_price": 22500,
    "current_price": 19900,
    "data_points": 45,
    "first_recorded": "2023-11-15T10:00:00Z",
    "last_recorded": "2024-02-15T10:00:00Z"
  }
}
```

---

### Search

#### GET `/search`

Full-text search across deals.

**Query Parameters:**
- `q` (string, required): Search query
- `page` (int)
- `limit` (int)
- `category` (string, optional)
- `shop` (string, optional)
- `sort_by` (string, default: "relevance"): `relevance`, `score`, `newest`

**Response:** Same as `/deals` endpoint

#### GET `/search/advanced`

Advanced search with additional filters.

**Query Parameters:**
- `q` (string, required)
- `page` (int)
- `limit` (int)
- `min_score` (float, optional): Minimum AI score (0-100)
- `max_price` (float, optional): Maximum price
- `category` (string, optional)
- `shop` (string, optional)

---

### Trending

#### GET `/trending`

Get trending search keywords.

**Query Parameters:**
- `limit` (int, default: 10, max: 50)

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "keyword": "아이폰",
      "count": 523
    }
  ]
}
```

#### GET `/trending/recent`

Get recently searched keywords.

**Query Parameters:**
- `limit` (int, default: 10, max: 50)

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "keyword": "갤럭시",
      "last_searched_at": "2024-02-15T12:34:56Z",
      "count": 42
    }
  ]
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "status": "error",
  "error": {
    "code": "not_found",
    "message": "Deal not found",
    "field": null
  }
}
```

Common HTTP status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Resource not found
- `422`: Validation error
- `500`: Internal server error

---

## Usage Examples

### Get Top Deals in Electronics Category

```bash
curl "http://localhost:8000/api/v1/deals/top?limit=10&category=electronics"
```

### Search for iPhone Deals

```bash
curl "http://localhost:8000/api/v1/search?q=아이폰&page=1&limit=20"
```

### Get Price History for a Product

```bash
curl "http://localhost:8000/api/v1/products/{product_id}/price-history?days=30"
```

### Get Deals from Coupang

```bash
curl "http://localhost:8000/api/v1/shops/coupang/deals?page=1&limit=20&sort_by=score"
```

---

## Development

### Running the Server

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Note: Documentation is only available when `DEBUG=True` in settings.
