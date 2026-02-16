# Scripts Directory

This directory contains utility scripts for managing the DealHawk backend database and testing scraper adapters.

## Setup Verification

Before running seed scripts, verify your setup is correct:

```bash
python scripts/verify_setup.py
```

This checks:
- Database connection
- PostgreSQL extensions (pg_trgm)
- Database tables exist
- Environment variables configured

## Database Seeding Scripts

### Quick Start - Seed Everything

```bash
# Seed all base data (categories + shops)
python scripts/seed_all.py
```

This will seed:
- 10 product categories
- 18 shopping platforms

### Individual Seed Scripts

If you need to seed data separately:

```bash
# Seed only categories
python scripts/seed_categories.py

# Seed only shops
python scripts/seed_shops.py
```

All seed scripts are **idempotent** - running them multiple times will not create duplicates.

## Scraper Testing Scripts

### Run a Scraper Manually

Test scraper adapters in isolation without running the full backend:

```bash
# Basic usage - fetch all deals from a shop
python scripts/run_scraper.py --shop naver

# Fetch deals for a specific category
python scripts/run_scraper.py --shop naver --category pc-hardware

# Limit the number of displayed deals
python scripts/run_scraper.py --shop naver --limit 5

# Combine options
python scripts/run_scraper.py --shop naver --category laptop-mobile --limit 20
```

**Available shops** (currently implemented):
- `naver` - Naver Shopping (API-based)

**Available categories**:
- `all` - All categories
- `pc-hardware` - PC/Hardware
- `gift-cards` - Gift Cards/Coupons
- `games-software` - Games/Software
- `laptop-mobile` - Laptop/Mobile
- `electronics-tv` - Electronics/TV
- `living-food` - Living/Food
- `fashion-clothing` - Fashion/Clothing
- `beauty-cosmetics` - Beauty/Cosmetics
- `furniture-interior` - Furniture/Interior

## Prerequisites

Before running any scripts, ensure:

1. **PostgreSQL is running** (via Docker Compose or locally)
   ```bash
   docker-compose up -d postgres
   ```

2. **Environment variables are set** (`.env` file in `backend/`)
   ```bash
   DATABASE_URL=postgresql+asyncpg://dealhawk:dealhawk_dev@localhost:5432/dealhawk
   NAVER_CLIENT_ID=your_naver_client_id
   NAVER_CLIENT_SECRET=your_naver_client_secret
   ```

3. **Database migrations have been run**
   ```bash
   cd backend
   alembic upgrade head
   ```

## Common Workflows

### Initial Setup

```bash
# 1. Start PostgreSQL
docker-compose up -d postgres

# 2. Run migrations
cd backend
alembic upgrade head

# 3. Seed base data
cd ..
python scripts/seed_all.py

# 4. Test a scraper
python scripts/run_scraper.py --shop naver --limit 5
```

### Adding New Test Data

```bash
# Re-run seed scripts (safe, idempotent)
python scripts/seed_all.py
```

### Testing a New Scraper Adapter

1. Implement your adapter in `backend/app/scrapers/adapters/your_shop.py`
2. Add it to the `ADAPTERS` registry in `scripts/run_scraper.py`
3. Test it:
   ```bash
   python scripts/run_scraper.py --shop your_shop --limit 3
   ```

## Seeded Data Details

### Categories (10 total)

| Slug | Korean Name | English Name |
|------|-------------|--------------|
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
- Coupang (쿠팡)
- Naver Shopping (네이버쇼핑)
- 11st (11번가)

**Korean Domestic - Scraper Based (8)**
- Hi-Mart (하이마트)
- Auction (옥션)
- G-Market (지마켓)
- SSG (SSG)
- Lotte ON (롯데온)
- Interpark (인터파크)
- Musinsa (무신사)
- Samsung Fashion (SSF)

**International - API Based (5)**
- AliExpress (알리익스프레스)
- Amazon (아마존)
- eBay (이베이)
- Steam (스팀)
- Newegg (뉴에그)

**International - Scraper Based (2)**
- Taobao (타오바오)
- Qoo10 (큐텐)

## Troubleshooting

### Database Connection Error

```
Error: could not connect to server
```

**Solution**: Make sure PostgreSQL is running
```bash
docker-compose up -d postgres
# Wait 10 seconds for PostgreSQL to start
python scripts/seed_all.py
```

### Import Error

```
ModuleNotFoundError: No module named 'app'
```

**Solution**: Make sure you're running scripts from the project root directory
```bash
# From C:\Users\gkwjd\Downloads\shopping
python scripts/seed_all.py
```

### Naver API Error (run_scraper.py)

```
ValueError: Naver API credentials not configured
```

**Solution**: Set your Naver API credentials in `backend/.env`
```bash
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
```

Get credentials from: https://developers.naver.com/

### Migration Not Run

```
ProgrammingError: relation "shops" does not exist
```

**Solution**: Run Alembic migrations first
```bash
cd backend
alembic upgrade head
```

## File Structure

```
scripts/
├── README.md                # This file
├── seed_all.py             # Run all seed scripts
├── seed_categories.py      # Seed product categories
├── seed_shops.py           # Seed shopping platforms
└── run_scraper.py          # Manual scraper testing tool
```

## Development Notes

- All seed scripts use `async_session_factory` from `app.db.session`
- Scripts add `backend/` to Python path for module imports
- All scripts are designed to be run from the project root directory
- Seed scripts check for existing records by `slug` to prevent duplicates
- The scraper test script supports adding new adapters via the `ADAPTERS` registry
