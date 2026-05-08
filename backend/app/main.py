"""
Production FastAPI application entry point.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.db.database import init_db
from app.api.endpoints import (
    auth, credentials, scanner, graph,
    prediction, propagation, healing,
    dashboard, notifications, chaos, aura,
    drift, rca, finops, security, demo
)
from app.services.websocket_manager import manager as ws_manager
from app.services.monitoring_service import MonitoringService
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

def _setup_observability(app: FastAPI):
    try:
        from app.packages.pkg_observability.instrumentation import setup_observability
        setup_observability(app, "cloud-healing-api", settings.OTLP_ENDPOINT)
        logger.info("Observability and metrics endpoints configured successfully.")
    except Exception as e:
        logger.warning(f"Observability setup failed: {e}")

# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Cloud Healing System Starting ===")

    try:
        from app.core.encryption import validate_encryption_key
        validate_encryption_key()
        logger.info("[Startup] Encryption key validated.")
    except RuntimeError as e:
        logger.critical(f"[Startup] ENCRYPTION_KEY error: {e}")
        raise

    await init_db()
    await ws_manager.startup()
    
    yield

    logger.info("=== Cloud Healing System Shutting Down ===")
    await ws_manager.shutdown()

# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="☁️ AIOps Cloud Healing Platform",
    description="Enterprise-grade Autonomous Self-Healing Multi-Cloud System",
    version="2.0.0",
    lifespan=lifespan,
)

# Rate Limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - Production Hardening
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,           prefix="/api/auth",          tags=["Authentication"])
app.include_router(credentials.router,    prefix="/api/credentials",   tags=["Credentials"])
app.include_router(scanner.router,        prefix="/api/scanner",       tags=["Scanner"])
app.include_router(graph.router,          prefix="/api/graph",         tags=["Graph"])
app.include_router(prediction.router,     prefix="/api/prediction",    tags=["Prediction"])
app.include_router(propagation.router,    prefix="/api/propagation",   tags=["Propagation"])
app.include_router(healing.router,        prefix="/api/healing",       tags=["Healing"])
app.include_router(dashboard.router,      prefix="/api/dashboard",     tags=["Dashboard"])
app.include_router(notifications.router,  prefix="/api/notifications", tags=["Notifications"])
app.include_router(chaos.router,          prefix="",                   tags=["Chaos Engineering"])
app.include_router(aura.router,           prefix="/api/aura",          tags=["Aura AI"])
app.include_router(drift.router,          prefix="/api/drift",         tags=["Drift Detection"])
app.include_router(rca.router,            prefix="/api/rca",           tags=["RCA"])
app.include_router(finops.router,         prefix="/api/finops",        tags=["FinOps"])
app.include_router(security.router,       prefix="/api/security",      tags=["Security"])
app.include_router(demo.router,                                         tags=["Demo Scenarios"])

# ── Observability ──────────────────────────────────────────────────────────────
_setup_observability(app)

@app.get("/api/health", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health_check():
    # Database Check
    from app.db.database import engine
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2.0)
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    # Redis Check
    redis_status = "ok"
    try:
        if ws_manager._redis:
            await asyncio.wait_for(ws_manager._redis.ping(), timeout=2.0)
        else:
            redis_status = "fallback_memory"
    except Exception as e:
        redis_status = f"error: {e}"

    # Kafka Check
    kafka_status = "ok"
    try:
        from confluent_kafka.admin import AdminClient
        admin = AdminClient({'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS})
        # list_topics is blocking, offload to thread
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: admin.list_topics(timeout=2.0))
    except Exception as e:
        kafka_status = f"error: {e}"

    # General System Health
    is_healthy = db_status == "ok" and redis_status in ["ok", "fallback_memory"] and kafka_status == "ok"

    return {
        "status": "healthy" if is_healthy else "degraded",
        "database": db_status,
        "redis": redis_status,
        "kafka": kafka_status,
        "websocket_connections": len(ws_manager.active_connections),
    }

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(websocket, client_id)
    try:
        # Keep the connection alive by draining incoming client messages.
        # All outbound data (metrics, alerts, resource events) is pushed
        # through ws_manager.broadcast() from the monitoring loop —
        # which uses a SINGLE Redis pub/sub listener, NOT one loop per client.
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error for {client_id}: {e}")
    finally:
        await ws_manager.disconnect(websocket, client_id)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENV == "dev",
        workers=int(os.getenv("UVICORN_WORKERS", "1")),
        log_level="info",
    )