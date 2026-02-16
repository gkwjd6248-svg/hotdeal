# Redis Caching Service Documentation

## Overview

The DealHawk caching layer uses Redis to cache API responses, reducing database load and improving response times for frequently accessed endpoints.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Endpoint                           │
│                                                              │
│  1. Generate cache key from request params                  │
│  2. Check Redis cache (get)                                 │
│  3. If HIT: Return cached response                          │
│  4. If MISS: Query database → Cache response → Return       │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
                ┌──────────────────┐
                │  CacheService    │  (app/services/cache_service.py)
                │  - get()         │
                │  - set()         │
                │  - delete()      │
                │  - invalidate()  │
                └─────────┬────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │    Redis    │
                   │  localhost  │
                   │   :6379     │
                   └─────────────┘
```

## Configuration

### Environment Variables

```bash
# .env
REDIS_URL=redis://localhost:6379/0
```

**Supported Redis URLs:**
- `redis://localhost:6379/0` - Local Redis (default)
- `redis://:password@localhost:6379/0` - Password-protected
- `rediss://host:6380/0` - SSL/TLS connection
- `redis://host:6379/1` - Different database number

### Redis Setup

```bash
# Install Redis (Ubuntu/Debian)
sudo apt update
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify Redis is running
redis-cli ping  # Should return "PONG"
```

## CacheService API

### Basic Operations

```python
from app.services.cache_service import get_cache

# Get cache instance
cache = await get_cache()

# Get a value
value = await cache.get("key")  # Returns str or None

# Set a value with TTL
await cache.set("key", "value", ttl=300)  # 300 seconds = 5 minutes

# Delete a key
await cache.delete("key")  # Returns True if deleted

# Delete keys matching pattern
deleted_count = await cache.delete_pattern("deals:*")

# Health check
is_healthy = await cache.health_check()  # Returns bool
```

### Dependency Injection (FastAPI)

```python
from fastapi import APIRouter, Depends
from app.services.cache_service import get_cache, CacheService

router = APIRouter()

@router.get("/endpoint")
async def endpoint(cache: CacheService = Depends(get_cache)):
    cached = await cache.get("mykey")
    if cached:
        return cached
    # ... fetch data ...
    await cache.set("mykey", data, ttl=60)
    return data
```

## Cached Endpoints

### Current Cache Coverage

| Endpoint | Cache Key | TTL | Invalidation |
|----------|-----------|-----|--------------|
| `GET /api/v1/deals` | `deals:p{page}:l{limit}:s{sort}...` | 30s | On deal create/update |
| `GET /api/v1/deals/top` | `deals_top:l{limit}:c{category}` | 60s | On deal create/update |
| `GET /api/v1/categories` | `categories:tree={bool}` | 300s | Manual invalidation |
| `GET /api/v1/shops` | `shops:active_only={bool}` | 300s | Manual invalidation |
| `GET /api/v1/trending` | `trending:limit={limit}` | 120s | Manual invalidation |

### Cache Key Patterns

**Deals Listing:**
```
deals:p1:l20:snewest
deals:p1:l20:snewest:ccategory-slug
deals:p1:l20:snewest:ccategory-slug:shshop-slug
deals:p1:l20:sscore:d10.0
```

**Top Deals:**
```
deals_top:l20
deals_top:l20:cpc-hardware
```

**Categories:**
```
categories:tree=False
categories:tree=True
```

**Shops:**
```
shops:active_only=True
shops:active_only=False
```

**Trending:**
```
trending:limit=10
trending:limit=20
```

## Cache Invalidation

### Automatic Invalidation

When deals are created or updated (via scraper or API):

```python
from app.services.cache_service import invalidate_deals_cache

# Called after deal creation/update
await invalidate_deals_cache()
```

This deletes all keys matching:
- `deals:*`
- `deals_top:*`
- `trending:*`

### Manual Invalidation

```python
from app.services.cache_service import get_cache

cache = await get_cache()

# Delete specific key
await cache.delete("categories:tree=True")

# Delete all category cache
await cache.delete_pattern("categories:*")

# Delete all shop cache
await cache.delete_pattern("shops:*")

# Delete everything (use with caution!)
await cache.delete_pattern("*")
```

### When to Invalidate

- **Deals cache** - Invalidated automatically when deals created/updated
- **Categories cache** - Invalidate when categories added/updated/deleted
- **Shops cache** - Invalidate when shops added/updated/deleted
- **Trending cache** - Invalidated with deals cache (trending depends on searches)

## Cache Key Helper Functions

```python
from app.services.cache_service import (
    cache_key_for_deals,
    cache_key_for_top_deals,
)

# Generate cache key for deals endpoint
key = cache_key_for_deals(
    page=1,
    limit=20,
    category_slug="pc-hardware",
    shop_slug="coupang",
    sort_by="score",
    min_discount=10.0,
    deal_type="flash_sale"
)
# Returns: "deals:p1:l20:sscore:cpc-hardware:shcoupang:d10.0:tflash_sale"

# Generate cache key for top deals
key = cache_key_for_top_deals(limit=20, category_slug="electronics")
# Returns: "deals_top:l20:celectronics"
```

## Performance Metrics

### Expected Cache Hit Rates

- **Homepage deals** (no filters): 80-90% (most users hit the same endpoint)
- **Top deals**: 85-95% (very stable data)
- **Categories**: 95%+ (rarely changes)
- **Shops**: 95%+ (rarely changes)
- **Trending**: 70-80% (changes more frequently)

### Cache Miss Scenarios

1. **First request** - Cold cache, no data yet
2. **TTL expired** - Cache entry expired naturally
3. **Cache invalidated** - Manual or automatic invalidation
4. **Unique query params** - New combination of filters
5. **Redis unavailable** - Graceful degradation (queries database)

## Error Handling

### Graceful Degradation

All cache operations use try/except to prevent cache failures from breaking the API:

```python
try:
    cached = await cache.get(key)
    if cached:
        return cached
except RedisError as e:
    logger.error("cache_get_failed", error=str(e))
    # Continue without cache - fetch from DB
```

**Behavior on Redis Failure:**
- Cache GET returns `None` (cache miss)
- Cache SET returns `False` (silently fails)
- API continues to work (queries database)
- Errors logged for monitoring

### Health Check

```python
# In health endpoint
cache_healthy = await cache.health_check()

if cache_healthy:
    redis_status = "ok"
else:
    redis_status = "error: ping failed"
```

Check health endpoint:
```bash
curl http://localhost:8000/api/v1/health
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "services": {
    "database": "ok",
    "redis": "ok"
  }
}
```

## Monitoring

### Redis CLI Commands

```bash
# Connect to Redis
redis-cli

# Check all keys
KEYS *

# Count total keys
DBSIZE

# Get cache hit rate
INFO stats | grep hits

# Monitor cache operations in real-time
MONITOR

# Check memory usage
INFO memory

# Get TTL of a key
TTL "deals:p1:l20:snewest"

# Get value of a key
GET "deals:p1:l20:snewest"

# Delete all keys (CAUTION!)
FLUSHDB
```

### Cache Statistics

```bash
# Total keys cached
redis-cli DBSIZE

# Keys by pattern
redis-cli KEYS "deals:*" | wc -l
redis-cli KEYS "categories:*" | wc -l

# Memory used
redis-cli INFO memory | grep used_memory_human

# Hit rate
redis-cli INFO stats | grep keyspace
```

## Best Practices

### 1. Choose Appropriate TTLs

- **Short TTL (30-60s)** - Frequently changing data (deals list)
- **Medium TTL (2-5 min)** - Trending/search data
- **Long TTL (5+ min)** - Rarely changing data (categories, shops)

### 2. Cache Key Design

- **Include all query params** - Prevent wrong cache hits
- **Use consistent format** - Makes pattern matching easier
- **Keep keys short** - Reduces memory usage

### 3. Invalidation Strategy

- **Invalidate on write** - Delete cache when data changes
- **Use patterns** - Delete multiple related keys at once
- **Avoid over-invalidation** - Don't delete unrelated caches

### 4. Handle Cache Misses

```python
# Always handle None gracefully
cached = await cache.get(key)
if cached:
    return ApiResponse.model_validate_json(cached)

# Fetch from database
data = await service.get_data()

# Cache response before returning
await cache.set(key, data.model_dump_json(), ttl=60)

return data
```

### 5. Monitor Performance

- Track cache hit rates
- Monitor Redis memory usage
- Log cache errors
- Set up alerts for Redis downtime

## Troubleshooting

### Redis Connection Errors

```
RedisConnectionError: Error connecting to Redis
```

**Solutions:**
1. Check Redis is running: `systemctl status redis-server`
2. Verify REDIS_URL in `.env`
3. Check network connectivity: `redis-cli ping`
4. Review Redis logs: `tail -f /var/log/redis/redis-server.log`

### Cache Not Working

1. **Check health endpoint:**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

2. **Verify Redis is running:**
   ```bash
   redis-cli ping
   ```

3. **Check application logs:**
   ```bash
   tail -f logs/dealhawk.log | grep cache
   ```

4. **Test cache manually:**
   ```bash
   redis-cli SET testkey "testvalue"
   redis-cli GET testkey
   ```

### High Memory Usage

```bash
# Check memory
redis-cli INFO memory

# Check key count
redis-cli DBSIZE

# Find large keys
redis-cli --bigkeys
```

**Solutions:**
- Lower TTLs to expire keys faster
- Delete unnecessary patterns
- Increase Redis max memory limit
- Enable eviction policy (allkeys-lru)

### Stale Cache

**Symptoms:** Users seeing old data even after updates

**Solutions:**
1. Verify invalidation is called after writes
2. Check TTLs aren't too long
3. Manually flush pattern: `await cache.delete_pattern("deals:*")`
4. Restart Redis (last resort): `systemctl restart redis-server`

## Future Enhancements

- [ ] Cache warming on startup
- [ ] Distributed cache (Redis Cluster)
- [ ] Cache versioning (for breaking changes)
- [ ] Compression for large values
- [ ] Cache analytics dashboard
- [ ] Automatic TTL adjustment based on hit rate
- [ ] Read-through / write-through caching
- [ ] Cache stampede prevention (distributed locks)
