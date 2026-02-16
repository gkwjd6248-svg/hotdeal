-- Initial database setup for DealHawk
-- This script runs when the PostgreSQL container is first created

-- Enable pg_trgm extension for trigram-based text search
-- This is required for full-text search on product titles and deals
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable uuid-ossp extension for UUID generation (if needed)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Verify extensions are installed
\dx
