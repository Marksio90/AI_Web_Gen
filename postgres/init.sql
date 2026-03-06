-- PostgreSQL initialization script
-- Runs once when the container is first created

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for fast ILIKE search
CREATE EXTENSION IF NOT EXISTS "unaccent";  -- for Polish diacritics-insensitive search

-- Create read-only user for analytics/monitoring
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'readonly') THEN
    CREATE ROLE readonly LOGIN PASSWORD 'readonly_pass';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE ai_web_gen TO readonly;
GRANT USAGE ON SCHEMA public TO readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly;

-- Performance tuning (applied at DB level, overrides postgresql.conf)
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '768MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = '0.9';
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = '100';
ALTER SYSTEM SET random_page_cost = '1.1';
ALTER SYSTEM SET effective_io_concurrency = '200';

SELECT pg_reload_conf();
