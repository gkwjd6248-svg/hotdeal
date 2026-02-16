# DealHawk API Quick Start Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 16+ with `pg_trgm` extension enabled
- Environment variables configured (see `.env.example`)

## Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file in the backend directory:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://dealhawk:dealhawk_dev@localhost:5432/dealhawk

# Redis (optional, for caching)
REDIS_URL=redis://localhost:6379/0

# App
ENVIRONMENT=development
DEBUG=True

# API Keys (for scrapers)
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret

# Frontend
FRONTEND_URL=http://localhost:3000
```

### 3. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Seed initial data (categories, shops)
python -m app.db.seed
```

### 4. Verify PostgreSQL Extensions

Connect to your database and ensure `pg_trgm` is enabled:

```sql
-- Connect to PostgreSQL
psql -U dealhawk -d dealhawk

-- Enable trigram extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verify
\dx
```

## Running the API

### Development Server

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- Base URL: http://localhost:8000
- API v1: http://localhost:8000/api/v1
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Production Server

```bash
# Using Gunicorn with Uvicorn workers
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

## Testing the API

### 1. Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{
  "status": "ok",
  "database": "ok",
  "services": {
    "database": "ok"
  }
}
```

### 2. List Categories

```bash
curl http://localhost:8000/api/v1/categories
```

### 3. List Shops

```bash
curl http://localhost:8000/api/v1/shops
```

### 4. Get Deals

```bash
# All deals
curl http://localhost:8000/api/v1/deals

# Top deals
curl http://localhost:8000/api/v1/deals/top

# Deals by category
curl "http://localhost:8000/api/v1/deals?category=electronics&sort_by=score"

# Deals by shop
curl "http://localhost:8000/api/v1/deals?shop=naver-shopping&limit=10"
```

### 5. Search

```bash
# Basic search
curl "http://localhost:8000/api/v1/search?q=노트북"

# Advanced search
curl "http://localhost:8000/api/v1/search/advanced?q=아이폰&min_score=70&max_price=1000000"
```

### 6. Trending Keywords

```bash
curl http://localhost:8000/api/v1/trending
```

## Interactive Documentation

Visit http://localhost:8000/docs to access the interactive Swagger UI where you can:
- View all available endpoints
- See request/response schemas
- Test endpoints directly in the browser
- View detailed parameter descriptions

## Common Issues

### 1. Database Connection Error

**Error:** `sqlalchemy.exc.OperationalError: could not connect to server`

**Solution:**
- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Check connection string in `.env`
- Verify user credentials

### 2. pg_trgm Extension Missing

**Error:** `UndefinedObject: type "gtrgm" does not exist`

**Solution:**
```sql
psql -U postgres -d dealhawk
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### 3. Import Errors

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
pip install -r requirements.txt
```

### 4. Migration Issues

**Error:** `alembic.util.exc.CommandError: Can't locate revision identified by 'xxxx'`

**Solution:**
```bash
# Reset migrations (WARNING: drops all data)
alembic downgrade base
alembic upgrade head

# Or start fresh
dropdb dealhawk
createdb dealhawk
alembic upgrade head
python -m app.db.seed
```

## API Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/deals` | GET | List deals |
| `/deals/top` | GET | Top AI-scored deals |
| `/deals/{id}` | GET | Get deal details |
| `/deals/{id}/vote` | POST | Vote on deal |
| `/categories` | GET | List categories |
| `/categories/{slug}/deals` | GET | Get category deals |
| `/shops` | GET | List shops |
| `/shops/{slug}` | GET | Get shop details |
| `/shops/{slug}/deals` | GET | Get shop deals |
| `/products` | GET | List products |
| `/products/{id}` | GET | Get product details |
| `/products/{id}/price-history` | GET | Get price history |
| `/products/{id}/price-statistics` | GET | Get price stats |
| `/search` | GET | Search deals |
| `/search/advanced` | GET | Advanced search |
| `/trending` | GET | Trending keywords |
| `/trending/recent` | GET | Recent searches |

## Next Steps

1. **Populate Data**: Run scrapers to populate deals
   ```bash
   python -m app.scrapers.run naver
   ```

2. **Background Jobs**: Set up periodic scraping
   ```bash
   python -m app.scheduler
   ```

3. **Monitor**: Check logs and database growth
   ```bash
   tail -f logs/dealhawk.log
   ```

4. **Optimize**: Add caching, indexes as needed

## Development Workflow

1. Make code changes
2. Server auto-reloads (if using `--reload`)
3. Test via Swagger UI or curl
4. Check logs for errors
5. Commit changes

## Production Deployment

See `backend/DEPLOYMENT.md` for production deployment instructions including:
- Docker containerization
- Nginx reverse proxy
- SSL/TLS configuration
- Monitoring and logging
- Scaling and load balancing

## Support

For issues or questions:
- Check documentation in `backend/app/api/README.md`
- Review service layer docs in `backend/app/services/README.md`
- Check database schema in `backend/app/db/SCHEMA_DIAGRAM.md`
