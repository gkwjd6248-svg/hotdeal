-- PostgreSQL extensions required for DealHawk schema
-- Run this script as a superuser or database owner before running Alembic migrations

-- Enable UUID generation (standard in modern PostgreSQL, but ensure it's available)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable trigram similarity matching for fuzzy text search
-- Required for GIN indexes on product.title and deal.title
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verify extensions are installed
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('uuid-ossp', 'pg_trgm')
ORDER BY extname;
