# Infrastructure Configuration

This directory contains Docker Compose configuration and deployment setup for the DealHawk project.

## Quick Start

```bash
# Start all services (PostgreSQL, Redis, Backend)
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Services

### PostgreSQL 16

**Container**: `dealhawk-postgres`
**Port**: `5432`
**Image**: `postgres:16-alpine`

Database configuration:
- Database: `dealhawk`
- User: `dealhawk`
- Password: `dealhawk_dev` (change in production!)

**Installed Extensions**:
- `pg_trgm` - Trigram-based text search (required for fuzzy search)
- `uuid-ossp` - UUID generation functions

**Health Check**: Runs `pg_isready` every 10 seconds

**Data Persistence**: Uses Docker volume `postgres_data`

### Redis 7

**Container**: `dealhawk-redis`
**Port**: `6379`
**Image**: `redis:7-alpine`

Used for:
- Rate limiting state
- Caching API responses
- Session storage (future)
- Background job queues (future)

**Health Check**: Runs `redis-cli ping` every 10 seconds

**Data Persistence**: Uses Docker volume `redis_data`

### Backend API

**Container**: `dealhawk-backend`
**Port**: `8000`
**Build Context**: `../backend`

FastAPI application with auto-reload enabled for development.

**Dependencies**:
- Waits for PostgreSQL health check to pass
- Waits for Redis health check to pass

**Environment Variables**:
- Loaded from `../backend/.env`
- Override `DATABASE_URL` and `REDIS_URL` to use container hostnames

## First-Time Setup

### 1. Create Environment File

```bash
cd backend
cp .env.example .env
```

Edit `.env` and add your API credentials:
```bash
# Naver Shopping API
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret

# Other API keys as needed...
```

### 2. Start Database Services

```bash
cd infra
docker-compose up -d postgres redis
```

Wait for health checks to pass (about 10-15 seconds):
```bash
docker-compose ps
```

You should see both services as "healthy".

### 3. Run Database Migrations

```bash
cd backend
alembic upgrade head
```

This creates all database tables and indexes.

### 4. Seed Base Data

```bash
cd ..
python scripts/seed_all.py
```

This seeds:
- 10 product categories
- 18 shopping platforms

### 5. Start Backend Service

```bash
cd infra
docker-compose up -d backend
```

Or run the backend locally for development:
```bash
cd backend
uvicorn app.main:app --reload
```

### 6. Verify Setup

Visit:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Common Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f backend
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
```

### Stop Services

```bash
# Stop but keep data
docker-compose stop

# Stop and remove containers (keeps data volumes)
docker-compose down

# Stop and remove everything INCLUDING data volumes
docker-compose down -v
```

### Database Access

```bash
# Connect to PostgreSQL
docker exec -it dealhawk-postgres psql -U dealhawk -d dealhawk

# Useful psql commands:
# \dt          - List tables
# \d+ shops    - Describe shops table
# \dx          - List installed extensions
# \q           - Quit
```

### Redis Access

```bash
# Connect to Redis CLI
docker exec -it dealhawk-redis redis-cli

# Useful Redis commands:
# KEYS *           - List all keys
# GET key          - Get value
# FLUSHDB          - Clear current database
# exit             - Quit
```

### Rebuild Backend Image

```bash
# Rebuild after Dockerfile or dependency changes
docker-compose up -d --build backend
```

## Development Workflow

### Local Development (Recommended)

Run PostgreSQL and Redis in Docker, but run the backend locally for faster iteration:

```bash
# Terminal 1: Start database services
cd infra
docker-compose up postgres redis

# Terminal 2: Run backend locally
cd backend
uvicorn app.main:app --reload
```

Benefits:
- Faster code reload
- Easier debugging
- Direct access to Python environment

### Full Docker Development

Run everything in Docker for a production-like environment:

```bash
cd infra
docker-compose up
```

The backend volume mount (`../backend:/app`) enables hot-reloading.

## File Structure

```
infra/
├── docker-compose.yml      # Main compose configuration
├── init-db.sql            # PostgreSQL initialization script
├── railway.toml           # Railway deployment config
└── README.md              # This file
```

## Database Initialization

The `init-db.sql` script runs automatically when the PostgreSQL container is first created. It:

1. Enables `pg_trgm` extension (required for trigram search)
2. Enables `uuid-ossp` extension (for UUID generation)
3. Lists installed extensions for verification

**Note**: This script only runs on first container creation. If you need to reset:

```bash
# Stop and remove volumes
docker-compose down -v

# Start fresh (will run init-db.sql again)
docker-compose up -d postgres
```

## Environment Variables

### PostgreSQL

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `dealhawk` | Database name |
| `POSTGRES_USER` | `dealhawk` | Database user |
| `POSTGRES_PASSWORD` | `dealhawk_dev` | Database password |

### Backend

Loaded from `../backend/.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `NAVER_CLIENT_ID` | For Naver scraper | Naver API client ID |
| `NAVER_CLIENT_SECRET` | For Naver scraper | Naver API client secret |
| `COUPANG_ACCESS_KEY` | For Coupang scraper | Coupang Partners API key |
| ... | ... | See `.env.example` for full list |

## Networking

All services run on the `dealhawk-net` bridge network. Services can communicate using container names as hostnames:

- Backend → PostgreSQL: `postgres:5432`
- Backend → Redis: `redis:6379`

## Data Persistence

### Volumes

- `postgres_data` - PostgreSQL data directory
- `redis_data` - Redis persistence files

### Backup PostgreSQL Data

```bash
# Dump database
docker exec dealhawk-postgres pg_dump -U dealhawk dealhawk > backup.sql

# Restore database
docker exec -i dealhawk-postgres psql -U dealhawk dealhawk < backup.sql
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs postgres

# Common issues:
# - Port 5432 already in use (stop local PostgreSQL)
# - Port 6379 already in use (stop local Redis)
```

### PostgreSQL Connection Refused

```bash
# Check if healthy
docker-compose ps

# If not healthy, check logs
docker-compose logs postgres

# Wait for initialization (first startup takes 10-15 seconds)
```

### Backend Can't Connect to Database

1. Check environment variables:
   ```bash
   docker-compose config
   ```

2. Verify DATABASE_URL uses correct hostname:
   ```bash
   # Inside container: postgres
   DATABASE_URL=postgresql+asyncpg://dealhawk:dealhawk_dev@postgres:5432/dealhawk

   # Outside container: localhost
   DATABASE_URL=postgresql+asyncpg://dealhawk:dealhawk_dev@localhost:5432/dealhawk
   ```

### pg_trgm Extension Not Found

```bash
# Connect to database
docker exec -it dealhawk-postgres psql -U dealhawk -d dealhawk

# Check if extension is installed
\dx

# If not found, enable it manually
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Reset Everything

```bash
# Nuclear option: delete all containers, volumes, and data
docker-compose down -v

# Start fresh
docker-compose up -d
cd ../backend
alembic upgrade head
cd ..
python scripts/seed_all.py
```

## Production Deployment

For production, update:

1. **Change passwords**: Don't use `dealhawk_dev` password
2. **Use environment variables**: Don't commit secrets to git
3. **Enable TLS**: Use SSL for PostgreSQL connections
4. **Resource limits**: Add CPU/memory limits to containers
5. **Logging**: Configure proper log aggregation
6. **Backups**: Set up automated database backups
7. **Monitoring**: Add health check monitoring

See `railway.toml` for Railway deployment configuration.

## Resource Requirements

Minimum system requirements:

- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 10 GB for Docker volumes
- **Network**: Reliable internet for scraping

Recommended for production:

- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Disk**: 50+ GB SSD
- **Network**: High bandwidth for concurrent scraping
