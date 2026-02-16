# DealHawk

AI-driven E-commerce Deal Aggregator -- finds and scores the best deals across Korean and global shopping platforms.

## Tech Stack

- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS
- **Backend**: Python FastAPI, SQLAlchemy 2.0, Pydantic v2
- **Database**: PostgreSQL 16, Redis 7
- **Scraping**: Playwright, BeautifulSoup4, httpx
- **Infrastructure**: Docker Compose, Railway

## Quick Start

```bash
# 1. Clone and install
make setup

# 2. Start infrastructure (Postgres + Redis + Backend)
make dev-backend

# 3. In another terminal, start the frontend
make dev-frontend

# 4. Run migrations
make migrate
```

## Project Structure

```
shopping/
  backend/        -- FastAPI application
  frontend/       -- Next.js application
  infra/          -- Docker Compose, deployment configs
  docs/           -- Architecture documentation
  scripts/        -- Utility and seeding scripts
```

## Development Commands

Run `make help` to see all available commands.
