# DealHawk Setup Guide

Complete setup guide for the DealHawk backend and infrastructure.

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Git

## Quick Start (5 minutes)

```bash
# 1. Start PostgreSQL and Redis
cd infra
docker-compose up -d postgres redis

# 2. Set up environment variables
cd ../backend
cp .env.example .env
# Edit .env and add your API credentials (at minimum, add Naver API keys)

# 3. Run database migrations
alembic upgrade head

# 4. Seed base data
cd ..
python scripts/seed_all.py

# 5. Verify setup
python scripts/verify_setup.py

# 6. Start backend
cd backend
uvicorn app.main:app --reload

# 7. Test scraper (in another terminal)
python scripts/run_scraper.py --shop naver --limit 5
```

Visit http://localhost:8000/docs to see the API documentation.

## Detailed Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd shopping
```

### 2. Backend Setup

#### Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

Or use a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Configure Environment Variables

```bash
cd backend
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
# Database (if using Docker Compose, these defaults work)
DATABASE_URL=postgresql+asyncpg://dealhawk:dealhawk_dev@localhost:5432/dealhawk
REDIS_URL=redis://localhost:6379/0

# Naver Shopping API (required for testing)
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
```

**Get Naver API Credentials**:
1. Go to https://developers.naver.com/
2. Register an application
3. Add "Shopping API" to your application
4. Copy Client ID and Client Secret to your `.env`

### 3. Database Setup

#### Start PostgreSQL with Docker

```bash
cd infra
docker-compose up -d postgres
```

Wait for PostgreSQL to start (about 10 seconds):

```bash
docker-compose ps
# Should show dealhawk-postgres as "healthy"
```

#### Run Migrations

```bash
cd backend
alembic upgrade head
```

This creates all database tables, indexes, and constraints.

#### Verify Database Extensions

```bash
# Connect to database
docker exec -it dealhawk-postgres psql -U dealhawk -d dealhawk

# Check extensions
\dx

# Should show:
# - pg_trgm (for text search)
# - uuid-ossp (for UUIDs)

# Exit
\q
```

### 4. Seed Data

```bash
# From project root
python scripts/seed_all.py
```

This seeds:
- **10 product categories** (PC/Hardware, Games, Electronics, etc.)
- **18 shopping platforms** (Naver, Coupang, 11st, Amazon, etc.)

### 5. Verify Setup

```bash
python scripts/verify_setup.py
```

This checks:
- ✅ Database connection
- ✅ PostgreSQL extensions
- ✅ Database tables
- ✅ Seeded data
- ⚠️ API credentials (optional, but recommended)

All required checks should pass.

### 6. Start Services

#### Option A: Backend Only (Recommended for Development)

Run PostgreSQL/Redis in Docker, backend locally:

```bash
# Terminal 1: Database services
cd infra
docker-compose up postgres redis

# Terminal 2: Backend
cd backend
uvicorn app.main:app --reload
```

#### Option B: Full Docker Stack

Run everything in Docker:

```bash
cd infra
docker-compose up
```

### 7. Test the Setup

#### Check API Documentation

Visit: http://localhost:8000/docs

You should see the Swagger UI with all endpoints.

#### Test Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

#### Run a Test Scraper

```bash
python scripts/run_scraper.py --shop naver --limit 5
```

This should fetch 5 deals from Naver Shopping and display them.

## Project Structure

```
shopping/
├── backend/               # FastAPI backend application
│   ├── app/
│   │   ├── api/          # API endpoints (future)
│   │   ├── models/       # SQLAlchemy models
│   │   ├── scrapers/     # Web scraper adapters
│   │   │   ├── adapters/ # Shop-specific scrapers
│   │   │   └── utils/    # Proxy, rate limiting, etc.
│   │   ├── db/           # Database session, migrations
│   │   └── config.py     # Settings
│   ├── alembic/          # Database migrations
│   ├── requirements.txt  # Python dependencies
│   └── .env.example      # Environment template
├── infra/                # Docker Compose & deployment
│   ├── docker-compose.yml
│   ├── init-db.sql       # PostgreSQL initialization
│   └── README.md         # Infrastructure docs
├── scripts/              # Utility scripts
│   ├── seed_all.py       # Seed all data
│   ├── seed_shops.py     # Seed shops
│   ├── seed_categories.py # Seed categories
│   ├── run_scraper.py    # Test scrapers
│   ├── verify_setup.py   # Verify setup
│   └── README.md         # Scripts documentation
└── SETUP.md              # This file
```

## Common Issues

### Port Already in Use

```
Error: port 5432 is already allocated
```

**Solution**: Stop your local PostgreSQL
```bash
# On Windows
net stop postgresql-x64-16

# On macOS
brew services stop postgresql

# On Linux
sudo systemctl stop postgresql
```

### Database Connection Failed

```
Could not connect to server: Connection refused
```

**Solutions**:
1. Make sure PostgreSQL is running:
   ```bash
   docker-compose ps
   ```

2. Wait for health check to pass (10-15 seconds after starting)

3. Check connection string in `.env`:
   ```bash
   # Use localhost for local development
   DATABASE_URL=postgresql+asyncpg://dealhawk:dealhawk_dev@localhost:5432/dealhawk

   # Use postgres for Docker container connections
   DATABASE_URL=postgresql+asyncpg://dealhawk:dealhawk_dev@postgres:5432/dealhawk
   ```

### pg_trgm Extension Not Found

```
ERROR: type "pg_trgm" does not exist
```

**Solution**: Recreate database with init script
```bash
cd infra
docker-compose down -v
docker-compose up -d postgres
# Wait 10 seconds
cd ../backend
alembic upgrade head
```

### Import Error in Scripts

```
ModuleNotFoundError: No module named 'app'
```

**Solution**: Run scripts from project root
```bash
# Wrong (from scripts directory)
cd scripts
python seed_all.py

# Correct (from project root)
cd /path/to/shopping
python scripts/seed_all.py
```

### Alembic Migration Failed

```
Target database is not up to date
```

**Solution**: Run migrations
```bash
cd backend
alembic upgrade head
```

### Naver API Error

```
ValueError: Naver API credentials not configured
```

**Solution**: Add credentials to `.env`
```bash
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
```

Get them from: https://developers.naver.com/

## Next Steps

Once setup is complete:

1. **Explore the API**: http://localhost:8000/docs
2. **Test scrapers**: See `scripts/README.md` for details
3. **Read the docs**:
   - `backend/app/db/README.md` - Database documentation
   - `backend/app/db/SCHEMA_DIAGRAM.md` - Schema reference
   - `infra/README.md` - Infrastructure docs
   - `scripts/README.md` - Scripts documentation

## Development Workflow

### Daily Development

```bash
# Start databases
docker-compose up -d postgres redis

# Run backend with hot reload
cd backend
uvicorn app.main:app --reload
```

### Adding a New Scraper

1. Create adapter: `backend/app/scrapers/adapters/myshop.py`
2. Implement `BaseAdapter` interface
3. Register in `scripts/run_scraper.py`
4. Test: `python scripts/run_scraper.py --shop myshop`

### Database Changes

```bash
# Create migration
cd backend
alembic revision --autogenerate -m "Add new_table"

# Review migration in alembic/versions/

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

## Production Deployment

See `infra/railway.toml` for Railway deployment configuration.

Key changes for production:

1. **Use strong passwords** (not `dealhawk_dev`)
2. **Set up SSL** for PostgreSQL connections
3. **Configure backups** for PostgreSQL
4. **Use environment variables** for all secrets
5. **Enable monitoring** and logging
6. **Set resource limits** on containers
7. **Use a CDN** for static assets
8. **Configure rate limiting** properly

## Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Run verification: `python scripts/verify_setup.py`
3. Read documentation in each directory's README.md
4. Check the project plan: `project_plan.md`

## Appendix: Full Environment Variables

See `backend/.env.example` for the complete list of environment variables.

Required:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string

Optional (for scrapers):
- `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` - Naver Shopping API
- `COUPANG_ACCESS_KEY` / `COUPANG_SECRET_KEY` - Coupang Partners API
- `ELEVEN_ST_API_KEY` - 11st API
- `ALIEXPRESS_APP_KEY` / `ALIEXPRESS_APP_SECRET` - AliExpress API
- `AMAZON_ACCESS_KEY` / `AMAZON_SECRET_KEY` / `AMAZON_PARTNER_TAG` - Amazon PA-API
- `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` - eBay API
- `PROXY_LIST` - Comma-separated proxy URLs for scraping
