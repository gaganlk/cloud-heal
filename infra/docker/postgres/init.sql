-- PostgreSQL initialization script
-- Runs automatically when the postgres container starts for the first time

-- Enable TimescaleDB extension if available (requires timescale/timescaledb-ha image)
-- CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create read-only role for monitoring tools (Prometheus pg_exporter)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'monitoring') THEN
        CREATE ROLE monitoring WITH LOGIN PASSWORD 'monitoring_readonly_2024' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

GRANT pg_monitor TO monitoring;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO monitoring;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO monitoring;

-- Create the application user if not exists (handles cold starts)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aiops_user') THEN
        CREATE USER aiops_user WITH PASSWORD 'securepassword123';
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE cloud_healing_db TO aiops_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aiops_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aiops_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO aiops_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO aiops_user;
