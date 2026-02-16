# Database Schema Testing Checklist

Use this checklist to verify the database implementation is working correctly.

## Pre-Migration Checks

### 1. Verify Python Environment
```bash
cd backend
python --version  # Should be 3.11+
pip list | grep -E "(sqlalchemy|alembic|asyncpg)"
```

Expected versions:
- sqlalchemy==2.0.36
- alembic==1.14.1
- asyncpg==0.30.0

### 2. Verify PostgreSQL is Running
```bash
psql -U dealhawk -d dealhawk -c "SELECT version();"
```

Should connect successfully and show PostgreSQL 16+

### 3. Check Database Exists
```bash
psql -U postgres -c "\l" | grep dealhawk
```

If database doesn't exist:
```bash
createdb -U postgres dealhawk
psql -U postgres -d dealhawk -c "CREATE USER dealhawk WITH PASSWORD 'dealhawk_dev';"
psql -U postgres -d dealhawk -c "GRANT ALL PRIVILEGES ON DATABASE dealhawk TO dealhawk;"
```

### 4. Enable Extensions
```bash
psql -U dealhawk -d dealhawk -f app/db/init_extensions.sql
```

Verify:
```bash
psql -U dealhawk -d dealhawk -c "\dx"
```

Should show:
- uuid-ossp
- pg_trgm

## Migration Tests

### 5. Test Model Imports
```bash
python -c "from app.models import Base, Shop, Category, Product, PriceHistory, Deal, ScraperJob, SearchKeyword; print('✓ All models imported')"
```

Should print success message without errors.

### 6. Check Alembic Configuration
```bash
alembic current
```

Should show "No revision" or current revision (if already migrated).

### 7. Generate Initial Migration
```bash
alembic revision --autogenerate -m "Initial schema"
```

Should create file in `app/db/migrations/versions/` like:
`2024_02_16_2230-abc123_initial_schema.py`

### 8. Review Migration File

Open the generated migration and verify:

- [ ] All 7 tables are created: shops, categories, products, price_history, deals, scraper_jobs, search_keywords
- [ ] UUID columns use `sa.UUID()`
- [ ] Timestamp columns use `sa.DateTime(timezone=True)`
- [ ] JSONB columns use `postgresql.JSONB()`
- [ ] Foreign keys are defined with proper ON DELETE behavior
- [ ] Indexes include:
  - [ ] `idx_products_title_trgm` (GIN trigram)
  - [ ] `idx_deals_title_trgm` (GIN trigram)
  - [ ] `idx_deals_ai_score_active` (partial index)
  - [ ] `idx_price_history_product_recorded`
  - [ ] `idx_deals_active_created`
- [ ] Unique constraints:
  - [ ] `shops.slug`
  - [ ] `categories.slug`
  - [ ] `(products.external_id, products.shop_id)`
  - [ ] `search_keywords.keyword`

### 9. Apply Migration
```bash
alembic upgrade head
```

Should output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> abc123, Initial schema
```

### 10. Verify Tables Created
```bash
psql -U dealhawk -d dealhawk -c "\dt"
```

Should list:
- shops
- categories
- products
- price_history
- deals
- scraper_jobs
- search_keywords
- alembic_version

### 11. Verify Indexes
```bash
psql -U dealhawk -d dealhawk -c "\di" | grep -E "(trgm|active|product_recorded)"
```

Should show trigram and other custom indexes.

### 12. Check Foreign Keys
```bash
psql -U dealhawk -d dealhawk -c "
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;
"
```

Should show all foreign key relationships.

## Data Seeding Tests

### 13. Run Seed Script
```bash
python -m app.db.seed
```

Should output:
```
✓ Seeded 7 shops
✓ Seeded 6 top-level categories and 5 subcategories
✅ Database seeding completed successfully!
```

### 14. Verify Shops Created
```bash
psql -U dealhawk -d dealhawk -c "SELECT slug, name, name_en, is_active FROM shops ORDER BY name_en;"
```

Should show:
- 11st
- aliexpress
- amazon-us
- auction
- coupang
- gmarket
- naver

### 15. Verify Categories Created
```bash
psql -U dealhawk -d dealhawk -c "SELECT slug, name_en, parent_id FROM categories ORDER BY sort_order;"
```

Should show 6 top-level + 5 subcategories.

### 16. Test Re-running Seed (Idempotency)
```bash
python -m app.db.seed
```

Should output:
```
Shops already seeded. Skipping...
Categories already seeded. Skipping...
✅ Database seeding completed successfully!
```

## Application Integration Tests

### 17. Test Database Connection from App
```bash
python -c "
import asyncio
from app.db.utils import check_database_health

async def test():
    result = await check_database_health()
    print('Database health:', result)

asyncio.run(test())
"
```

Should print:
```
Database health: {'healthy': True}
```

### 18. Test Creating a Product
```bash
python -c "
import asyncio
import uuid
from decimal import Decimal
from app.db.session import async_session_factory
from app.models import Shop, Product
from sqlalchemy import select

async def test():
    async with async_session_factory() as db:
        # Get first shop
        result = await db.execute(select(Shop).limit(1))
        shop = result.scalar_one()

        # Create test product
        product = Product(
            external_id='TEST-001',
            shop_id=shop.id,
            title='Test Product - AMD Ryzen 5 5600X',
            current_price=Decimal('199.99'),
            currency='KRW',
            product_url='https://example.com/product/1'
        )
        db.add(product)
        await db.commit()
        print(f'✓ Created product: {product.id}')

        # Query it back
        result = await db.execute(select(Product).where(Product.external_id == 'TEST-001'))
        found = result.scalar_one()
        print(f'✓ Found product: {found.title}')

        # Clean up
        await db.delete(found)
        await db.commit()
        print('✓ Deleted test product')

asyncio.run(test())
"
```

Should print:
```
✓ Created product: <uuid>
✓ Found product: Test Product - AMD Ryzen 5 5600X
✓ Deleted test product
```

### 19. Test Relationships
```bash
python -c "
import asyncio
from app.db.session import async_session_factory
from app.models import Shop
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def test():
    async with async_session_factory() as db:
        result = await db.execute(
            select(Shop)
            .options(selectinload(Shop.products))
            .limit(1)
        )
        shop = result.scalar_one()
        print(f'✓ Shop: {shop.name_en}')
        print(f'✓ Products count: {len(shop.products)}')

asyncio.run(test())
"
```

Should print shop name and product count (0 if no products yet).

### 20. Test Trigram Search (Korean)
```bash
python -c "
import asyncio
from app.db.session import async_session_factory
from app.models import Category
from sqlalchemy import select, func

async def test():
    async with async_session_factory() as db:
        # Test similarity search
        search_term = '전자'
        result = await db.execute(
            select(Category)
            .where(Category.name.ilike(f'%{search_term}%'))
            .order_by(func.similarity(Category.name, search_term).desc())
        )
        categories = result.scalars().all()
        print(f'✓ Found {len(categories)} categories matching \"{search_term}\"')
        for cat in categories:
            print(f'  - {cat.name} ({cat.name_en})')

asyncio.run(test())
"
```

Should find "전자제품 (Electronics)".

## Migration Rollback Tests

### 21. Test Downgrade
```bash
alembic downgrade -1
```

Should roll back the migration.

### 22. Verify Tables Dropped
```bash
psql -U dealhawk -d dealhawk -c "\dt"
```

Should only show `alembic_version` table.

### 23. Test Re-upgrade
```bash
alembic upgrade head
```

Should re-create all tables.

### 24. Re-run Seed After Rollback
```bash
python -m app.db.seed
```

Should successfully seed data again.

## Performance Tests

### 25. Test Bulk Insert Performance
```bash
python -c "
import asyncio
import time
from decimal import Decimal
from app.db.session import async_session_factory
from app.models import Shop, Product
from sqlalchemy import select

async def test():
    async with async_session_factory() as db:
        result = await db.execute(select(Shop).limit(1))
        shop = result.scalar_one()

        start = time.time()
        products = []
        for i in range(100):
            products.append(Product(
                external_id=f'PERF-TEST-{i}',
                shop_id=shop.id,
                title=f'Performance Test Product {i}',
                current_price=Decimal('99.99'),
                currency='KRW',
                product_url=f'https://example.com/product/{i}'
            ))
        db.add_all(products)
        await db.commit()
        elapsed = time.time() - start
        print(f'✓ Inserted 100 products in {elapsed:.2f}s')

        # Clean up
        for p in products:
            await db.delete(p)
        await db.commit()
        print('✓ Cleaned up test data')

asyncio.run(test())
"
```

Should complete in < 1 second.

### 26. Test Index Usage (EXPLAIN)
```bash
psql -U dealhawk -d dealhawk -c "
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM products
WHERE title ILIKE '%test%'
ORDER BY created_at DESC
LIMIT 20;
"
```

Should show index scan (not seq scan) once you have data.

## Cleanup

### 27. Drop Test Database (Optional)
```bash
# Only if you want to start fresh
dropdb dealhawk
createdb dealhawk
```

## Checklist Summary

- [ ] PostgreSQL 16+ running
- [ ] Database and user created
- [ ] Extensions enabled (uuid-ossp, pg_trgm)
- [ ] All models import successfully
- [ ] Alembic configured correctly
- [ ] Initial migration generated
- [ ] Migration file reviewed and correct
- [ ] Migration applied successfully
- [ ] All 7 tables created
- [ ] All indexes created (including GIN trigram)
- [ ] Foreign keys working
- [ ] Seed script runs successfully
- [ ] 7 shops seeded
- [ ] 11 categories seeded
- [ ] Database health check passes
- [ ] Can create/read/delete products
- [ ] Relationships load correctly
- [ ] Trigram search works (Korean support)
- [ ] Migration rollback works
- [ ] Migration re-apply works
- [ ] Performance is acceptable

## Common Issues

### Issue: "permission denied for schema public"
**Solution**: Grant permissions to dealhawk user
```bash
psql -U postgres -d dealhawk -c "GRANT ALL ON SCHEMA public TO dealhawk;"
psql -U postgres -d dealhawk -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dealhawk;"
```

### Issue: "extension \"pg_trgm\" does not exist"
**Solution**: Enable as superuser
```bash
psql -U postgres -d dealhawk -c "CREATE EXTENSION pg_trgm;"
```

### Issue: Alembic can't detect changes
**Solution**: Check imports in `env.py` and `__init__.py`

### Issue: AsyncPG connection errors
**Solution**: Check DATABASE_URL format: `postgresql+asyncpg://user:pass@host:port/db`

### Issue: Import errors
**Solution**: Ensure you're in the `backend/` directory and PYTHONPATH is set correctly
