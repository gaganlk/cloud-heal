# ── Build Stage: Backend ──────────────────────────────────────────────────────
FROM python:3.12-slim AS backend-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ python3-dev libpq-dev libssl-dev libffi-dev curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel --default-timeout=200 --retries 10
RUN pip install --no-cache-dir -r requirements.txt --default-timeout=200 --retries 10



# ── Production Image ──────────────────────────────────────────────────────────
FROM backend-base AS production

WORKDIR /app

# Copy application source (backend/app -> /app/app)
COPY backend/app/ /app/app/
COPY backend/app/alembic.ini /app/alembic.ini

# Non-root user for security
RUN groupadd --gid 1001 aiops && \
    useradd --uid 1001 --gid aiops --no-create-home aiops && \
    chown -R aiops:aiops /app

USER aiops

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start with prestart script
CMD ["sh", "-c", "python app/prestart.py && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"]
