# DealHawk Database Schema

## Entity Relationship Diagram

```mermaid
erDiagram
    shops ||--o{ products : "has many"
    shops ||--o{ deals : "has many"
    shops ||--o{ scraper_jobs : "tracks"

    categories ||--o{ categories : "parent/child"
    categories ||--o{ products : "categorizes"
    categories ||--o{ deals : "categorizes"

    products ||--o{ price_history : "tracks prices"
    products ||--o{ deals : "creates"
    products }o--|| shops : "sold by"
    products }o--o| categories : "belongs to"

    deals }o--|| products : "references"
    deals }o--|| shops : "sold by"
    deals }o--o| categories : "belongs to"

    price_history }o--|| products : "records"

    scraper_jobs }o--|| shops : "scrapes"

    shops {
        uuid id PK
        string name "Korean name"
        string name_en "English name"
        string slug UK "URL identifier"
        string logo_url
        string base_url
        string adapter_type "api, scraper, hybrid"
        boolean is_active
        int scrape_interval_minutes
        string country "ISO code"
        string currency "ISO code"
        jsonb metadata_ "Scraper config"
        timestamp created_at
        timestamp updated_at
    }

    categories {
        uuid id PK
        string name "Korean name"
        string name_en "English name"
        string slug UK "URL identifier"
        string icon
        int sort_order
        uuid parent_id FK "Self-referential"
        timestamp created_at
    }

    products {
        uuid id PK
        string external_id "Shop's product ID"
        uuid shop_id FK
        string title
        text description
        decimal original_price
        decimal current_price
        string currency
        string image_url
        string product_url
        string brand
        uuid category_id FK
        boolean is_active
        timestamp last_scraped_at
        jsonb metadata_ "Specs, attributes"
        timestamp created_at
        timestamp updated_at
    }

    price_history {
        uuid id PK
        uuid product_id FK
        decimal price
        string currency
        string source "scraper, api, manual"
        timestamp recorded_at
    }

    deals {
        uuid id PK
        uuid product_id FK
        uuid shop_id FK
        uuid category_id FK
        decimal deal_price
        decimal original_price
        decimal discount_percentage
        decimal discount_amount
        string deal_type "price_drop, flash_sale, etc"
        decimal ai_score "0-100"
        text ai_reasoning
        string title
        text description
        string image_url
        string deal_url
        boolean is_active
        boolean is_expired
        timestamp starts_at
        timestamp expires_at
        int vote_up
        int vote_down
        int view_count
        int comment_count
        jsonb metadata_
        timestamp created_at
        timestamp updated_at
    }

    scraper_jobs {
        uuid id PK
        uuid shop_id FK
        string status "pending, running, completed, failed"
        timestamp started_at
        timestamp completed_at
        decimal duration_seconds
        int items_found
        int items_created
        int items_updated
        int deals_detected
        text error_message
        text error_traceback
        jsonb metadata_ "Job config"
        timestamp created_at
    }

    search_keywords {
        uuid id PK
        string keyword UK "Normalized search term"
        int search_count
        timestamp last_searched_at
        timestamp created_at
    }
```

## Key Relationships

### One-to-Many Relationships

1. **Shop → Products**
   - One shop has many products
   - Products are deleted when shop is deleted (CASCADE)

2. **Shop → Deals**
   - One shop has many deals
   - Deals are deleted when shop is deleted (CASCADE)

3. **Shop → Scraper Jobs**
   - One shop has many scraper job executions
   - Jobs are deleted when shop is deleted (CASCADE)

4. **Product → Price History**
   - One product has many price history records
   - Price history deleted when product is deleted (CASCADE)

5. **Product → Deals**
   - One product can have multiple deals (e.g., different time periods)
   - Deals deleted when product is deleted (CASCADE)

### Optional Relationships (SET NULL on delete)

1. **Category → Products**
   - Products can belong to a category
   - When category deleted, product.category_id → NULL

2. **Category → Deals**
   - Deals can belong to a category
   - When category deleted, deal.category_id → NULL

### Self-Referential Relationship

1. **Category → Category (parent/child)**
   - Categories can have parent categories
   - Enables hierarchical category tree
   - When parent deleted, children are also deleted (CASCADE)

## Indexes

### Primary Indexes (Automatic)

- `id` (UUID) on all tables

### Unique Indexes

- `shops.slug` - Ensures unique URL identifiers
- `categories.slug` - Ensures unique URL identifiers
- `(products.external_id, products.shop_id)` - One product per shop
- `search_keywords.keyword` - Unique keywords

### Performance Indexes

#### Text Search (Trigram GIN)
- `products.title` - Fuzzy search on product titles
- `deals.title` - Fuzzy search on deal titles

#### Foreign Key Indexes
- `products.shop_id`
- `products.category_id`
- `price_history.product_id`
- `deals.product_id`
- `deals.shop_id`
- `deals.category_id`
- `scraper_jobs.shop_id`

#### Composite Indexes
- `(products.is_active, products.last_scraped_at)` - Find stale products
- `(deals.is_active, deals.created_at)` - Recent active deals
- `(price_history.product_id, price_history.recorded_at)` - Time-series queries

#### Partial Indexes
- `deals.ai_score WHERE is_active = true` - Scored active deals only

#### Other Indexes
- `products.brand` - Filter by brand
- `scraper_jobs.status` - Monitor job status
- `search_keywords.last_searched_at` - Trending searches
- `deals.expires_at` - Find expiring deals
- `deals.vote_up` - Sort by popularity

## Data Types

### PostgreSQL-Specific Types

- **UUID**: Native PostgreSQL UUID type for all primary keys
- **JSONB**: Binary JSON storage for flexible metadata
- **Numeric(12, 2)**: Fixed-precision decimal for prices (12 digits, 2 decimal places)
- **Numeric(5, 2)**: For percentages and scores (0-100.00)
- **DateTime(timezone=True)**: Timezone-aware timestamps

### Conventions

- All timestamps use `server_default=func.now()` for consistency
- `updated_at` uses `onupdate=func.now()` for automatic updates
- JSONB columns named `metadata_` to avoid Python keyword conflict
- Boolean fields default to `False` unless otherwise specified
- Integer counters default to 0

## Constraints

### NOT NULL Constraints

Required fields that must always have a value:
- All `id`, `created_at` columns
- Shop: `name`, `name_en`, `slug`, `base_url`, `adapter_type`
- Product: `shop_id`, `title`, `product_url`
- Deal: `product_id`, `shop_id`, `deal_price`, `title`, `deal_url`
- Price History: `product_id`, `price`, `recorded_at`

### Unique Constraints

- Single column: `shops.slug`, `categories.slug`, `search_keywords.keyword`
- Multi-column: `(products.external_id, products.shop_id)`

### Foreign Key Constraints

All foreign keys use standard naming: `<table>_id` references `<table>.id`

#### CASCADE Deletes
- `products.shop_id` → CASCADE (product deleted when shop deleted)
- `price_history.product_id` → CASCADE
- `deals.product_id` → CASCADE
- `deals.shop_id` → CASCADE
- `scraper_jobs.shop_id` → CASCADE

#### SET NULL Deletes
- `products.category_id` → SET NULL (category deletion doesn't delete products)
- `deals.category_id` → SET NULL

## Query Patterns

### Most Common Queries

1. **Get recent active deals sorted by AI score**
   ```sql
   SELECT * FROM deals
   WHERE is_active = true AND is_expired = false
   ORDER BY ai_score DESC, created_at DESC
   LIMIT 20;
   ```
   Uses: `idx_deals_ai_score_active`, `idx_deals_active_created`

2. **Search products by title**
   ```sql
   SELECT * FROM products
   WHERE title ILIKE '%ryzen%'
   ORDER BY similarity(title, 'ryzen') DESC;
   ```
   Uses: `idx_products_title_trgm`

3. **Get price history for product**
   ```sql
   SELECT * FROM price_history
   WHERE product_id = $1
   ORDER BY recorded_at DESC
   LIMIT 100;
   ```
   Uses: `idx_price_history_product_recorded`

4. **Find deals by category**
   ```sql
   SELECT * FROM deals
   WHERE category_id = $1 AND is_active = true
   ORDER BY ai_score DESC;
   ```
   Uses: `deals.category_id`, `idx_deals_ai_score_active`

5. **Monitor scraper job status**
   ```sql
   SELECT * FROM scraper_jobs
   WHERE shop_id = $1
   ORDER BY created_at DESC
   LIMIT 10;
   ```
   Uses: `scraper_jobs.shop_id`, `scraper_jobs.created_at`
