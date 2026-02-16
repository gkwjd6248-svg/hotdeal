# Database Schema Documentation

## Overview

The DealHawk database schema is designed for a high-performance deal aggregation platform that scrapes products from multiple e-commerce sites, tracks price history, and scores deals using AI.

## Schema Structure

### Core Tables

#### `shops`
E-commerce platforms/retailers (Coupang, 11st, Naver Shopping, etc.)
- **Purpose**: Configure and track scraping sources
- **Key Fields**: `slug`, `adapter_type`, `scrape_interval_minutes`, `is_active`
- **Relationships**: Has many products, deals, and scraper_jobs

#### `categories`
Product categories with hierarchical support
- **Purpose**: Organize products into browsable taxonomy
- **Key Fields**: `slug`, `parent_id`, `sort_order`
- **Relationships**: Self-referential (parent/children), has many products and deals

#### `products`
Products scraped from shops
- **Purpose**: Track product details, pricing, and availability
- **Key Fields**: `external_id`, `shop_id`, `title`, `current_price`, `original_price`
- **Unique Constraint**: `(external_id, shop_id)` - one product per shop
- **Relationships**: Belongs to shop and category, has many price_history and deals
- **Indexes**: GIN trigram index on `title` for fuzzy text search

#### `price_history`
Historical price tracking
- **Purpose**: Record price changes over time for trend analysis
- **Key Fields**: `product_id`, `price`, `recorded_at`, `source`
- **Indexes**: Compound index on `(product_id, recorded_at)` for efficient time-series queries

#### `deals`
Detected good deals
- **Purpose**: Surface the best deals based on price drops and AI scoring
- **Key Fields**: `product_id`, `deal_price`, `discount_percentage`, `ai_score`, `is_active`
- **Relationships**: Belongs to product, shop, and category
- **Indexes**:
  - Partial index on `ai_score` where `is_active = true`
  - GIN trigram index on `title` for search
  - Index on `(is_active, created_at)` for recent active deals

#### `scraper_jobs`
Scraper execution tracking
- **Purpose**: Monitor scraper health, performance, and errors
- **Key Fields**: `shop_id`, `status`, `items_found`, `items_created`, `error_message`
- **Relationships**: Belongs to shop

#### `search_keywords`
Search analytics
- **Purpose**: Track popular search terms for trending analysis
- **Key Fields**: `keyword`, `search_count`, `last_searched_at`

## PostgreSQL Extensions Required

The schema uses PostgreSQL-specific features that require extensions:

### pg_trgm (Trigram)
Required for fuzzy text search on product and deal titles.

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

This enables GIN indexes with `gin_trgm_ops` operator class for fast similarity searches.

## Migration Workflow

### Initial Setup

1. Ensure PostgreSQL 16+ is running
2. Enable required extensions:
   ```bash
   psql -U dealhawk -d dealhawk -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
   ```
3. Generate initial migration:
   ```bash
   cd backend
   alembic revision --autogenerate -m "Initial schema"
   ```
4. Review the generated migration in `app/db/migrations/versions/`
5. Apply migration:
   ```bash
   alembic upgrade head
   ```

### Making Schema Changes

1. Modify models in `app/models/`
2. Generate migration:
   ```bash
   alembic revision --autogenerate -m "Description of changes"
   ```
3. Review and edit the generated migration if needed
4. Apply migration:
   ```bash
   alembic upgrade head
   ```

### Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base
```

## Design Decisions

### UUIDs vs. Integer IDs
- **Choice**: UUIDs for all primary keys
- **Rationale**:
  - Better for distributed systems
  - No ID enumeration attacks
  - Safe for external API exposure
  - No sequence conflicts in multi-instance deployments

### Denormalization in Deals Table
- **Choice**: `title`, `description`, `image_url` duplicated from products
- **Rationale**:
  - Performance: Avoid JOIN on every deal query
  - Historical accuracy: Deal title preserved even if product title changes
  - Flexibility: Deals can have custom titles/descriptions

### JSONB for Metadata
- **Choice**: `metadata` JSONB columns on shops, products, deals, scraper_jobs
- **Rationale**:
  - Flexible schema for shop-specific scraper config
  - Store raw/unstructured data without schema migrations
  - Can add GIN indexes on JSONB for querying if needed

### Trigram Indexes on Text Fields
- **Choice**: GIN trigram indexes on `products.title` and `deals.title`
- **Rationale**:
  - Fast fuzzy search (e.g., "ryzen 5" matches "AMD Ryzen 5 5600X")
  - Korean text search support
  - Enables `LIKE`, `ILIKE`, and similarity operators

### Partial Indexes
- **Choice**: `ai_score` indexed only where `is_active = true`
- **Rationale**:
  - Smaller index size
  - Faster queries on active deals
  - Most queries filter by `is_active`

### Cascade Deletes
- **Choice**: `CASCADE` on product → price_history, product → deals, shop → products
- **Rationale**:
  - Maintain referential integrity
  - Automatic cleanup of dependent records
  - Prevents orphaned records

## Performance Considerations

### Query Patterns

**Hot queries** (optimize first):
1. Recent active deals sorted by AI score
2. Product search by title
3. Price history for a product over time range
4. Deals by category
5. Scraper job status for monitoring dashboard

**Indexes designed for these queries**:
- `idx_deals_ai_score_active` - Partial index for scored active deals
- `idx_products_title_trgm` - Trigram for product search
- `idx_price_history_product_recorded` - Time-series price queries
- `idx_deals_active_created` - Recent deals listing

### Connection Pooling
- Async SQLAlchemy with asyncpg driver
- Pool size: 20 connections
- Max overflow: 10
- Pre-ping enabled for stale connection detection

## Data Volume Estimates

Based on 10 shops scraped every hour:

- **Products**: ~100K products (stable after initial crawl)
- **Price History**: ~2.4M rows/month (100K products × 24 checks/day)
- **Deals**: ~10K active deals at any time
- **Scraper Jobs**: ~7K jobs/month (10 shops × 24 runs/day)

**Storage estimate**: ~50GB for first year with price history

### Archival Strategy (Future)
- Archive expired deals older than 90 days
- Aggregate price history to hourly/daily averages after 30 days
- Compress scraper job logs older than 30 days
