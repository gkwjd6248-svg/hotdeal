# Docker Compose & Seed Scripts - Implementation Summary

This document summarizes the Docker Compose configuration and seed data scripts created for the DealHawk project.

## Files Created

### Infrastructure Configuration

1. **`infra/docker-compose.yml`** (Updated)
   - Added volume mount for `init-db.sql`
   - All services configured with health checks
   - Proper networking and dependencies

2. **`infra/init-db.sql`** (New)
   - Enables `pg_trgm` extension for trigram text search
   - Enables `uuid-ossp` extension for UUID generation
   - Runs automatically on first PostgreSQL container creation

3. **`infra/README.md`** (New)
   - Comprehensive infrastructure documentation
   - Service descriptions and configuration
   - Common commands and troubleshooting
   - Development workflows

### Seed Scripts

4. **`scripts/seed_shops.py`** (New)
   - Seeds 18 shopping platforms into the database
   - Covers Korean domestic shops (Coupang, Naver, 11st, etc.)
   - Covers international platforms (Amazon, AliExpress, eBay, etc.)
   - Idempotent - safe to run multiple times

5. **`scripts/seed_categories.py`** (New)
   - Seeds 10 product categories
   - Includes Korean and English names
   - Icon identifiers for frontend use
   - Idempotent - safe to run multiple times

6. **`scripts/seed_all.py`** (New)
   - Master script to run all seed scripts in order
   - Clear progress output and error handling
   - Helpful next steps after completion

### Testing & Verification

7. **`scripts/run_scraper.py`** (New)
   - Manual scraper adapter testing tool
   - Supports category filtering and output limiting
   - Formatted output with pricing and discounts
   - Extensible adapter registry

8. **`scripts/verify_setup.py`** (New)
   - Comprehensive setup verification
   - Checks database connection, extensions, tables, seeded data
   - Verifies environment variables and API credentials
   - Provides troubleshooting guidance on failures

### Documentation

9. **`scripts/README.md`** (Updated)
   - Complete scripts documentation
   - Usage examples for all scripts
   - Category and shop listings
   - Troubleshooting guide

10. **`SETUP.md`** (New)
    - Complete setup guide from scratch
    - Quick start (5 minutes) and detailed setup
    - Common issues and solutions
    - Development workflow guidance

11. **`DOCKER_AND_SEEDS_SUMMARY.md`** (This file)
    - Implementation summary
    - What was created and why

## Docker Compose Configuration

### Services

**PostgreSQL 16**
- Container: `dealhawk-postgres`
- Port: `5432`
- Image: `postgres:16-alpine`
- Health check: `pg_isready` every 10s
- Data persistence: `postgres_data` volume
- Init script: `init-db.sql` for extensions

**Redis 7**
- Container: `dealhawk-redis`
- Port: `6379`
- Image: `redis:7-alpine`
- Health check: `redis-cli ping` every 10s
- Data persistence: `redis_data` volume

**Backend API**
- Container: `dealhawk-backend`
- Port: `8000`
- Build: `../backend/Dockerfile`
- Depends on: PostgreSQL + Redis health checks
- Hot reload: Volume mount `../backend:/app`

### Network

- Bridge network: `dealhawk-net`
- Services communicate via container names

### Volumes

- `postgres_data` - PostgreSQL data persistence
- `redis_data` - Redis data persistence

## Seeded Data

### Categories (10 total)

| Slug | Korean | English |
|------|--------|---------|
| `all` | 전체 | All |
| `pc-hardware` | PC/하드웨어 | PC/Hardware |
| `gift-cards` | 상품권/쿠폰 | Gift Cards/Coupons |
| `games-software` | 게임/SW | Games/Software |
| `laptop-mobile` | 노트북/모바일 | Laptop/Mobile |
| `electronics-tv` | 가전/TV | Electronics/TV |
| `living-food` | 생활/식품 | Living/Food |
| `fashion-clothing` | 패션/의류 | Fashion/Clothing |
| `beauty-cosmetics` | 뷰티/화장품 | Beauty/Cosmetics |
| `furniture-interior` | 가구/인테리어 | Furniture/Interior |

### Shops (18 total)

**Korean Domestic - API Based (3)**
1. Coupang (쿠팡) - 30min interval
2. Naver Shopping (네이버쇼핑) - 30min interval
3. 11st (11번가) - 60min interval

**Korean Domestic - Scraper Based (8)**
4. Hi-Mart (하이마트) - 60min interval
5. Auction (옥션) - 60min interval
6. G-Market (지마켓) - 60min interval
7. SSG (SSG) - 60min interval
8. Lotte ON (롯데온) - 60min interval
9. Interpark (인터파크) - 60min interval
10. Musinsa (무신사) - 120min interval
11. Samsung Fashion (SSF) - 120min interval

**International - API Based (5)**
12. AliExpress (알리익스프레스) - 60min interval
13. Amazon (아마존) - 60min interval
14. eBay (이베이) - 60min interval
15. Steam (스팀) - 120min interval
16. Newegg (뉴에그) - 120min interval

**International - Scraper Based (2)**
17. Taobao (타오바오) - 120min interval
18. Qoo10 (큐텐) - 90min interval

## Key Features

### Idempotent Seeding

All seed scripts check for existing data by `slug` before inserting:

```python
result = await session.execute(
    select(Shop).where(Shop.slug == shop_data["slug"])
)
if result.scalar_one_or_none():
    print("Already exists, skipping")
    continue
```

Running seed scripts multiple times is safe and won't create duplicates.

### PostgreSQL Extensions

The `init-db.sql` script automatically enables required extensions:

- **pg_trgm**: Trigram-based text search for fuzzy matching on product titles
- **uuid-ossp**: UUID generation functions

These extensions are critical for the application's search functionality.

### Health Checks

All services have health checks to ensure proper startup order:

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
```

Backend waits for PostgreSQL and Redis to be healthy before starting.

### Scraper Testing

The `run_scraper.py` script allows testing scrapers in isolation:

```bash
python scripts/run_scraper.py --shop naver --category pc-hardware --limit 5
```

Features:
- Category filtering
- Output limiting
- Formatted price display
- Summary statistics (avg discount, deal types)
- Proper error handling and cleanup

### Setup Verification

The `verify_setup.py` script checks all critical components:

1. ✅ Environment variables configured
2. ✅ Database connection working
3. ✅ PostgreSQL extensions installed
4. ✅ Database tables created
5. ✅ Base data seeded
6. ⚠️ API credentials configured (optional)

Returns proper exit codes for CI/CD integration.

## Usage Workflows

### Initial Setup

```bash
# 1. Start database services
cd infra
docker-compose up -d postgres redis

# 2. Configure environment
cd ../backend
cp .env.example .env
# Edit .env with your API credentials

# 3. Run migrations
alembic upgrade head

# 4. Seed data
cd ..
python scripts/seed_all.py

# 5. Verify
python scripts/verify_setup.py

# 6. Test scraper
python scripts/run_scraper.py --shop naver --limit 5
```

### Daily Development

```bash
# Start databases
docker-compose up -d postgres redis

# Run backend locally (hot reload)
cd backend
uvicorn app.main:app --reload
```

### Reset Database

```bash
# Nuclear option: delete everything
docker-compose down -v

# Start fresh
docker-compose up -d postgres redis
cd backend
alembic upgrade head
cd ..
python scripts/seed_all.py
```

## Technical Decisions

### Why SQLAlchemy 2.0 Async?

- Modern async/await patterns
- Better performance for I/O-bound operations
- Required for concurrent scraping workloads

### Why Separate Seed Scripts?

- Modular - can seed categories and shops independently
- Easier to debug and maintain
- Clear single responsibility

### Why Docker Compose?

- Consistent development environment
- Easy setup for new developers
- Production-like infrastructure locally
- Health checks ensure proper startup order

### Why pg_trgm?

- Enables fuzzy text search on product titles
- Critical for Korean text search
- Supports trigram GIN indexes for performance
- Used by `ILIKE` and `similarity()` functions

### Why Idempotent Seeds?

- Safe to run multiple times
- No manual database cleanup needed
- CI/CD friendly
- Developer friendly (can re-run anytime)

## Future Enhancements

### Potential Additions

1. **More scrapers**: Add remaining 17 shop adapters
2. **Background jobs**: APScheduler for periodic scraping
3. **API endpoints**: RESTful API for products, deals, search
4. **Monitoring**: Prometheus metrics, health checks
5. **Testing**: pytest fixtures for database setup
6. **CI/CD**: GitHub Actions with verify_setup.py
7. **Backup script**: Automated PostgreSQL backups
8. **Load testing**: Locust or k6 tests
9. **Documentation**: OpenAPI specs, architecture diagrams

### Script Enhancements

1. **seed_sample_deals.py**: Seed sample deals for testing
2. **benchmark_scrapers.py**: Performance testing for scrapers
3. **export_data.py**: Export deals/products to CSV/JSON
4. **cleanup_old_data.py**: Archive old price history
5. **migrate_data.py**: Data migration utilities

## Files Reference

All created/updated files:

```
C:\Users\gkwjd\Downloads\shopping\
├── infra\
│   ├── docker-compose.yml      # Updated: Added init-db.sql mount
│   ├── init-db.sql             # New: PostgreSQL extensions
│   └── README.md               # New: Infrastructure docs
├── scripts\
│   ├── seed_all.py             # New: Master seed script
│   ├── seed_shops.py           # New: Seed 18 shops
│   ├── seed_categories.py      # New: Seed 10 categories
│   ├── run_scraper.py          # New: Scraper testing tool
│   ├── verify_setup.py         # New: Setup verification
│   └── README.md               # Updated: Scripts documentation
├── SETUP.md                    # New: Complete setup guide
└── DOCKER_AND_SEEDS_SUMMARY.md # New: This file
```

## Testing the Implementation

To verify everything works:

```bash
# 1. Start services
cd infra
docker-compose up -d

# 2. Verify setup
cd ..
python scripts/verify_setup.py

# Expected: All checks pass ✅

# 3. Test scraper
python scripts/run_scraper.py --shop naver --limit 3

# Expected: 3 deals displayed with prices and details

# 4. Check API
curl http://localhost:8000/health

# Expected: {"status": "healthy", ...}
```

## Conclusion

This implementation provides:
- ✅ Complete Docker Compose infrastructure
- ✅ PostgreSQL with required extensions
- ✅ Redis for caching and rate limiting
- ✅ Idempotent database seeding (18 shops, 10 categories)
- ✅ Scraper testing utilities
- ✅ Setup verification tools
- ✅ Comprehensive documentation
- ✅ Developer-friendly workflows

All scripts follow best practices:
- Async/await patterns
- Proper error handling
- Clear output formatting
- Idempotent operations
- Type hints and docstrings

The implementation is production-ready for the seeding and infrastructure layer.
