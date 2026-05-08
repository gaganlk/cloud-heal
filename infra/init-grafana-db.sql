-- Initialization script for PostgreSQL to create the Grafana database and user.
CREATE USER grafana_user WITH PASSWORD 'secure_grafana_password';
CREATE DATABASE grafana_db;
GRANT ALL PRIVILEGES ON DATABASE grafana_db TO grafana_user;
ALTER DATABASE grafana_db OWNER TO grafana_user;
