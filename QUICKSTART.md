# DealHawk - Quick Start Guide

Get DealHawk up and running in 5 minutes.

## Prerequisites

- Docker Desktop (running)
- Python 3.11+

## Setup Commands

Copy and paste these commands in order:

### 1. Start Database Services (30 seconds)

```bash
cd infra
docker-compose up -d postgres redis
```

Wait 10 seconds for services to start, then verify:

```bash
docker-compose ps
# Both should show "healthy"
```

### 2. Configure Environment (1 minute)

```bash
cd ../backend
cp .env.example .env
```

Edit `.env` and add your Naver API credentials:
```bash
NAVER_CLIENT_ID=your_client_id_here
NAVER_CLIENT_SECRET=your_client_secret_here
```

Get credentials at: https://developers.naver.com/

### 3. Run Migrations (30 seconds)

```bash
alembic upgrade head
```

### 4. Seed Data (30 seconds)

```bash
cd ..
python scripts/seed_all.py
```

### 5. Verify Setup (30 seconds)

```bash
python scripts/verify_setup.py
```

All checks should pass ✅

### 6. Start Backend (10 seconds)

```bash
cd backend
uvicorn app.main:app --reload
```

### 7. Test (1 minute)

Open a new terminal and run:

```bash
# Test the API
curl http://localhost:8000/health

# Test a scraper
python scripts/run_scraper.py --shop naver --limit 5
```

## Success!

If all steps completed:

- ✅ Database is running with 18 shops and 10 categories
- ✅ Backend API is running at http://localhost:8000
- ✅ API docs are at http://localhost:8000/docs
- ✅ Scrapers are working

## What's Next?

1. **Explore the API**: Visit http://localhost:8000/docs
2. **Test more scrapers**: `python scripts/run_scraper.py --shop naver --category pc-hardware`
3. **Read the docs**: See `SETUP.md` for detailed documentation

## Troubleshooting

### Port 5432 already in use

Stop local PostgreSQL:
```bash
# Windows
net stop postgresql-x64-16

# macOS
brew services stop postgresql

# Linux
sudo systemctl stop postgresql
```

### Database connection failed

Make sure PostgreSQL is running:
```bash
cd infra
docker-compose ps
# Should show "healthy"
```

### Naver API error

Make sure you added credentials to `.env`:
```bash
NAVER_CLIENT_ID=your_actual_client_id
NAVER_CLIENT_SECRET=your_actual_client_secret
```

### Other issues

Run the verification script:
```bash
python scripts/verify_setup.py
```

It will tell you exactly what's wrong and how to fix it.

## Full Documentation

- **Complete Setup Guide**: `SETUP.md`
- **Infrastructure Docs**: `infra/README.md`
- **Scripts Docs**: `scripts/README.md`
- **Database Docs**: `backend/app/db/README.md`

## Development Commands

```bash
# Start databases
docker-compose up -d postgres redis

# Run backend (hot reload)
cd backend
uvicorn app.main:app --reload

# Test scraper
python scripts/run_scraper.py --shop naver

# Verify setup
python scripts/verify_setup.py

# View logs
docker-compose logs -f postgres
```

## One-Liner Setup (Advanced)

If you already have Naver API credentials in `.env`:

```bash
cd infra && docker-compose up -d postgres redis && sleep 10 && cd ../backend && alembic upgrade head && cd .. && python scripts/seed_all.py && python scripts/verify_setup.py
```

Then start the backend:

```bash
cd backend && uvicorn app.main:app --reload
```
