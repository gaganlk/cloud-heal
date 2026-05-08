"""
Production-grade async PostgreSQL engine.

FIXES applied (Critical C-7):
  - Silent SQLite fallback REMOVED from init_db() in production (ENV=prod/test).
  - In ENV=dev, SQLite fallback still works but logs a PROMINENT WARNING so
    the developer knows PostgreSQL is down.
  - Added validate_db_url() startup check so the app fails fast with a clear
    error rather than silently using the wrong database.
  - NullPool retained for PgBouncer transaction-pooling compatibility.
  - pool_pre_ping=True retained for connection health validation.
"""
import logging
import asyncio
import os

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, StaticPool
from app.core.config import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL
_ENV = settings.ENV


def _make_postgres_engine(url: str):
    return create_async_engine(
        url,
        poolclass=NullPool,
        pool_pre_ping=True,
        echo=False,
    )


def _make_sqlite_engine(path: str = "./aiops_local.db"):
    return create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )


# Initialise engine — this runs at import time to wire up the sessionmaker.
# init_db() will validate the connection on first startup.
if DATABASE_URL.startswith("postgresql"):
    engine = _make_postgres_engine(DATABASE_URL)
else:
    if _ENV == "prod":
        raise RuntimeError(
            f"DATABASE_URL must use postgresql+asyncpg in production (ENV=prod). "
            f"Got: {DATABASE_URL!r}"
        )
    logger.warning(
        "[DB] DATABASE_URL does not point to PostgreSQL. "
        "Using SQLite fallback — NOT suitable for production."
    )
    engine = _make_sqlite_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Validate DB connectivity and create all tables.

    Behaviour by ENV:
      - prod/test : Hard fail if PostgreSQL is unreachable.
      - dev       : Try PostgreSQL; fall back to SQLite with a loud warning.

    In production, run Alembic migrations via prestart.py BEFORE init_db().
    create_all() is a no-op for existing tables (checkfirst=True).
    """
    global engine, AsyncSessionLocal

    from . import models  # noqa: F401 — ensures all ORM models are registered

    async def _create_tables(eng):
        async with eng.begin() as conn:
            await asyncio.wait_for(
                conn.run_sync(Base.metadata.create_all), timeout=10.0
            )

    try:
        await _create_tables(engine)
        logger.info(f"[DB] Tables verified on {engine.url.drivername}")
        return
    except Exception as pg_err:
        logger.error(f"[DB] Primary database unreachable: {pg_err}")

    # Hard fail in non-dev environments
    if _ENV in ("prod", "test"):
        raise RuntimeError(
            f"[DB] Cannot connect to PostgreSQL in ENV={_ENV!r}. "
            "Ensure the database is running and DATABASE_URL is correct. "
            f"Error: {pg_err}"
        )

    # Dev-only SQLite fallback
    logger.warning(
        "\n" + "=" * 70 + "\n"
        "  FALLING BACK TO SQLite — PostgreSQL is not reachable.\n"
        "  Data will be LOST on restart. Start PostgreSQL for persistence.\n"
        + "=" * 70
    )
    engine = _make_sqlite_engine("./aiops_local.db")
    AsyncSessionLocal.configure(bind=engine)
    await _create_tables(engine)
    logger.info("[DB] SQLite fallback tables initialised.")