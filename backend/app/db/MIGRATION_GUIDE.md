# Database Migration Quick Reference

## Prerequisites

Ensure PostgreSQL extensions are installed:

```bash
# Connect to your database
psql -U dealhawk -d dealhawk

# Or use the SQL script
psql -U dealhawk -d dealhawk -f app/db/init_extensions.sql
```

## Common Commands

### Generate Initial Migration

```bash
# From backend/ directory
alembic revision --autogenerate -m "Initial schema"
```

This will create a new migration file in `app/db/migrations/versions/` with:
- All table definitions
- Indexes
- Foreign keys
- Constraints

### Apply Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply one migration at a time
alembic upgrade +1

# Apply to a specific revision
alembic upgrade <revision_id>
```

### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback all migrations
alembic downgrade base

# Rollback to specific revision
alembic downgrade <revision_id>
```

### Check Migration Status

```bash
# Show current revision
alembic current

# Show migration history
alembic history --verbose

# Show pending migrations
alembic current
alembic heads
```

### Create Empty Migration

```bash
# For data migrations or manual schema changes
alembic revision -m "Add default categories"
```

Then edit the generated file to add your custom SQL or data changes.

## Adding New Models

1. Create model file in `app/models/` (e.g., `app/models/user.py`)
2. Import model in `app/models/__init__.py`
3. Import model in `app/db/migrations/env.py` (critical!)
4. Generate migration:
   ```bash
   alembic revision --autogenerate -m "Add user model"
   ```
5. Review the generated migration
6. Apply migration:
   ```bash
   alembic upgrade head
   ```

## Modifying Existing Models

1. Edit the model file
2. Generate migration:
   ```bash
   alembic revision --autogenerate -m "Add user email field"
   ```
3. **Review the migration carefully** - Alembic may miss some changes
4. Edit migration if needed (e.g., add data migrations, set defaults)
5. Apply migration:
   ```bash
   alembic upgrade head
   ```

## Common Migration Patterns

### Adding a Non-Nullable Column to Existing Table

```python
def upgrade() -> None:
    # Step 1: Add column as nullable
    op.add_column('products', sa.Column('brand', sa.String(200), nullable=True))

    # Step 2: Populate column with default values
    op.execute("UPDATE products SET brand = 'Unknown' WHERE brand IS NULL")

    # Step 3: Make column non-nullable
    op.alter_column('products', 'brand', nullable=False)

def downgrade() -> None:
    op.drop_column('products', 'brand')
```

### Adding an Index

```python
def upgrade() -> None:
    op.create_index(
        'idx_products_brand',
        'products',
        ['brand']
    )

def downgrade() -> None:
    op.drop_index('idx_products_brand', table_name='products')
```

### Adding Enum Type

```python
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    # Create enum type
    status_enum = postgresql.ENUM('pending', 'running', 'completed', 'failed', name='job_status')
    status_enum.create(op.get_bind())

    # Add column
    op.add_column('scraper_jobs', sa.Column('status', status_enum, nullable=False, server_default='pending'))

def downgrade() -> None:
    op.drop_column('scraper_jobs', 'status')
    op.execute('DROP TYPE job_status')
```

### Data Migration

```python
from alembic import op
from sqlalchemy import orm
from app.models import Category

def upgrade() -> None:
    # Get database connection
    bind = op.get_bind()
    session = orm.Session(bind=bind)

    # Insert seed data
    categories = [
        Category(name="전자제품", name_en="Electronics", slug="electronics"),
        Category(name="패션", name_en="Fashion", slug="fashion"),
    ]
    session.add_all(categories)
    session.commit()

def downgrade() -> None:
    op.execute("DELETE FROM categories WHERE slug IN ('electronics', 'fashion')")
```

## Troubleshooting

### Migration Conflicts

If you have multiple migration heads (branches):

```bash
# See all heads
alembic heads

# Merge branches
alembic merge -m "Merge migrations" <revision1> <revision2>
```

### Reset Database (Development Only)

```bash
# Drop all tables
alembic downgrade base

# Or drop database and recreate
dropdb dealhawk
createdb dealhawk
psql -U dealhawk -d dealhawk -f app/db/init_extensions.sql

# Apply all migrations
alembic upgrade head
```

### Alembic Can't Detect Changes

Check:
1. Model is imported in `app/models/__init__.py`
2. Model is imported in `app/db/migrations/env.py`
3. `target_metadata = Base.metadata` is set in `env.py`
4. You're using `Mapped[]` annotation (SQLAlchemy 2.0 style)

### Database Connection Errors

Check:
1. PostgreSQL is running
2. Database exists: `psql -U dealhawk -l`
3. Environment variables are set correctly
4. `DATABASE_URL` in `app/config.py` is correct

## Production Migration Strategy

### Pre-deployment Checklist

1. Test migration on a copy of production data
2. Estimate migration time (use `EXPLAIN ANALYZE` for large tables)
3. Check for locking operations (adding indexes, columns with defaults)
4. Plan for zero-downtime migration if needed
5. Have rollback plan ready

### Zero-Downtime Migrations

For large tables or high-traffic systems:

1. **Adding nullable columns**: Safe, no locking
2. **Adding indexes**: Use `CONCURRENTLY` (requires raw SQL in migration)
   ```python
   op.execute("CREATE INDEX CONCURRENTLY idx_name ON table (column)")
   ```
3. **Changing column types**: Requires rewrite, use staging column
4. **Dropping columns**: Mark as deprecated first, remove in next release

### Deployment Process

```bash
# 1. Backup database
pg_dump -U dealhawk dealhawk > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Apply migrations
alembic upgrade head

# 3. Verify migration
alembic current

# 4. Test application
curl http://localhost:8000/api/v1/health

# 5. If issues, rollback
alembic downgrade -1
```

## Best Practices

1. **Always review autogenerated migrations** - Alembic isn't perfect
2. **Test migrations on development data** before production
3. **Keep migrations small and focused** - one logical change per migration
4. **Add comments** to complex migrations
5. **Don't modify applied migrations** - create new ones instead
6. **Include both upgrade and downgrade** paths
7. **Test rollback** in development before deploying
8. **Use transactions** for data migrations (default in Alembic)
