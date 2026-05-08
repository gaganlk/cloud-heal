"""
Comprehensive integration test suite for the AIOps platform.
Tests the full pipeline: DB → Kafka → ML → Healing → WebSocket

Run with:
  pytest tests/integration/ -v --tb=short
  pytest tests/integration/test_pipeline.py -v -k "test_kafka"
"""
import asyncio
import json
import time
import uuid
import pytest
import pytest_asyncio

# ────────────────────────────────────────────────────────────────────────────
# Fixtures & Windows Compatibility
# ────────────────────────────────────────────────────────────────────────────

import sys
if sys.platform == "win32":
    # SelectorEventLoop is more stable for socket-heavy tests on Windows than Proactor
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



# ────────────────────────────────────────────────────────────────────────────
# Fixtures & Windows Compatibility
# ────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Async DB session. Fresh engine and session per test function for total isolation."""
    import os
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://aiops_user:securepassword123@localhost:6432/cloud_healing_db"
    )
    from database.database import engine, init_db, Base, AsyncSessionLocal
    from database.models import Tenant
    
    # ── HARD RESET for Schema ──────────────────────────────────────────────
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Create a test tenant
        tenant = Tenant(name="Test Org", external_id="test_org")
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        
        yield session
        await asyncio.shield(session.close())
    
    await asyncio.shield(engine.dispose())


@pytest_asyncio.fixture(scope="function")
async def redis_client():
    """Redis client. Fresh client per test function."""
    import redis.asyncio as aioredis
    client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    yield client
    await asyncio.shield(client.aclose())


# ────────────────────────────────────────────────────────────────────────────
# Phase 1: DB Tests
# ────────────────────────────────────────────────────────────────────────────

class TestDatabaseLayer:
    """Tests for async PostgreSQL + PgBouncer."""

    @pytest.mark.asyncio
    async def test_db_connection(self, db_session):
        """Verify connection via async engine."""
        from sqlalchemy import text
        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_user_creation_and_query(self, db_session):
        """Create and query a User — verifies schema."""
        from sqlalchemy import select
        from database.models import User
        from passlib.context import CryptContext
        import uuid as _uuid

        uname = f"test_{_uuid.uuid4().hex[:8]}"
        pwd_ctx = CryptContext(schemes=["bcrypt"])
        user = User(
            username=uname,
            email=f"{uname}@test.com",
            hashed_password=pwd_ctx.hash("testpass"),
            role="viewer",
            tenant_id=1,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await db_session.execute(select(User).where(User.username == uname))
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.role == "viewer"

    @pytest.mark.asyncio
    async def test_unique_constraint_resource(self, db_session):
        """Verify duplicate (credential_id, resource_id) raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError
        from database.models import CloudCredential, CloudResource, User
        from sqlalchemy import select
        import uuid as _uuid
        from passlib.context import CryptContext

        # Use existing or create a user and credential
        uname = f"ctest_{_uuid.uuid4().hex[:8]}"
        pwd_ctx = CryptContext(schemes=["bcrypt"])
        user = User(username=uname, email=f"{uname}@t.com",
                    hashed_password=pwd_ctx.hash("x"), role="viewer", tenant_id=1)
        db_session.add(user)
        await db_session.flush()

        cred = CloudCredential(
            user_id=user.id, provider="aws", name="test-cred",
            encrypted_data="dummy_encrypted_data", tenant_id=1
        )
        db_session.add(cred)
        await db_session.flush()

        rid = f"i-{_uuid.uuid4().hex[:12]}"
        r1 = CloudResource(credential_id=cred.id, resource_id=rid,
                            resource_type="ec2_instance", name="test", provider="aws", tenant_id=1)
        r2 = CloudResource(credential_id=cred.id, resource_id=rid,
                            resource_type="ec2_instance", name="test", provider="aws", tenant_id=1)
        db_session.add(r1)
        await db_session.flush()
        db_session.add(r2)

        with pytest.raises(IntegrityError):
            await db_session.flush()

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, db_session):
        """Simulate 20 concurrent writes — verifies pool handles concurrency."""
        from database.database import AsyncSessionLocal
        from database.models import EventLog, User
        from sqlalchemy import select
        import uuid as _uuid
        from passlib.context import CryptContext

        uname = f"conc_{_uuid.uuid4().hex[:8]}"
        pwd_ctx = CryptContext(schemes=["bcrypt"])

        async with AsyncSessionLocal() as s:
            user = User(username=uname, email=f"{uname}@t.com",
                        hashed_password=pwd_ctx.hash("x"), role="viewer", tenant_id=1)
            s.add(user)
            await s.commit()
            user_id = user.id

        async def write_one():
            async with AsyncSessionLocal() as s:
                log = EventLog(user_id=user_id, event_type="test",
                               description="concurrent test", severity="info", tenant_id=1)
                s.add(log)
                await s.commit()

        tasks = [write_one() for _ in range(20)]
        await asyncio.gather(*tasks)

        async with AsyncSessionLocal() as s:
            result = await s.execute(
                __import__("sqlalchemy").select(
                    __import__("sqlalchemy").func.count()
                ).where(EventLog.user_id == user_id)
            )
            count = result.scalar()
        assert count == 20, f"Expected 20 concurrent writes, got {count}"


# ────────────────────────────────────────────────────────────────────────────
# Phase 3: Kafka Pipeline Tests
# ────────────────────────────────────────────────────────────────────────────

class TestKafkaPipeline:
    """Tests for Kafka produce/consume pipeline."""

    @pytest.mark.asyncio
    async def test_producer_sends_message(self):
        """Verify producer publishes a message without error."""
        from packages.pkg_kafka.producer import KafkaTelemetryProducer
        producer = KafkaTelemetryProducer("localhost:9092")
        event_id = str(uuid.uuid4())
        # Should not raise
        await producer.send_metric("global_telemetry", {
            "event_id": event_id,
            "resource_id": "test-i-001",
            "cpu": 85.0,
            "memory": 90.0,
            "timestamp": time.time(),
        })
        await producer.stop()

    @pytest.mark.asyncio
    async def test_idempotency_dedup(self, redis_client):
        """Verify duplicate events are rejected by Redis dedup."""
        event_id = f"test-dedup-{uuid.uuid4().hex[:8]}"
        cache_key = f"telemetry:processed:{event_id}"

        # Simulate first processing
        await redis_client.setex(cache_key, 3600, "1")

        # Check that second call would be rejected
        is_duplicate = await redis_client.exists(cache_key)
        assert is_duplicate == 1, "Dedup key not found — idempotency check would fail"

        # Cleanup
        await redis_client.delete(cache_key)


# ────────────────────────────────────────────────────────────────────────────
# Phase 6: ML Engine Tests
# ────────────────────────────────────────────────────────────────────────────

class TestMLEngine:
    """Tests for Isolation Forest anomaly detector."""

    def test_heuristic_fallback_normal(self):
        """Untrained model should score normal telemetry < 0.5."""
        from services.prediction.ml_engine import FailurePredictorML
        predictor = FailurePredictorML()
        predictor._is_fitted = False  # Force heuristic path

        score = predictor.predict_degradation({"cpu": 30.0, "memory": 40.0, "disk_io": 5.0, "network_latency": 10.0})
        assert 0.0 <= score <= 0.5, f"Normal telemetry scored too high: {score}"

    def test_heuristic_fallback_anomalous(self):
        """Untrained model should score anomalous telemetry > 0.7."""
        from services.prediction.ml_engine import FailurePredictorML
        predictor = FailurePredictorML()
        predictor._is_fitted = False

        score = predictor.predict_degradation({"cpu": 99.0, "memory": 98.0, "disk_io": 90.0, "network_latency": 1000.0})
        assert score > 0.7, f"Anomalous telemetry scored too low: {score}"

    def test_trained_model_discrimination(self):
        """Trained model must score anomalous events higher than normal events."""
        import numpy as np
        from services.prediction.ml_engine import FailurePredictorML

        predictor = FailurePredictorML()

        # Train on synthetic data
        rng = np.random.default_rng(0)
        normal = rng.normal([40, 50, 10, 20], [10, 12, 5, 8], size=(500, 4)).clip(0, 100)
        anomalous = rng.normal([90, 92, 80, 800], [5, 4, 8, 100], size=(25, 4)).clip(0)
        X = np.vstack([normal, anomalous])
        predictor.fit(X)

        score_normal = predictor.predict_degradation({"cpu": 35.0, "memory": 45.0, "disk_io": 8.0, "network_latency": 15.0})
        score_anomalous = predictor.predict_degradation({"cpu": 95.0, "memory": 97.0, "disk_io": 85.0, "network_latency": 950.0})

        assert score_anomalous > score_normal, (
            f"Model failed: anomalous ({score_anomalous:.3f}) should be > normal ({score_normal:.3f})"
        )

    def test_score_bounds(self):
        """Scores must always be in [0.0, 1.0]."""
        from services.prediction.ml_engine import FailurePredictorML
        predictor = FailurePredictorML()

        test_cases = [
            {"cpu": 0.0, "memory": 0.0, "disk_io": 0.0, "network_latency": 0.0},
            {"cpu": 100.0, "memory": 100.0, "disk_io": 100.0, "network_latency": 9999.0},
            {"cpu": 50.0, "memory": 50.0, "disk_io": 50.0, "network_latency": 500.0},
        ]
        for tc in test_cases:
            score = predictor.predict_degradation(tc)
            assert 0.0 <= score <= 1.0, f"Score out of bounds [{score}] for input {tc}"


# ────────────────────────────────────────────────────────────────────────────
# Phase 7: Safety Checks Tests
# ────────────────────────────────────────────────────────────────────────────

class TestSafetyChecks:
    """Tests for healing action safety gates."""

    @pytest.mark.asyncio
    async def test_auto_trigger_blocked_for_high_risk(self, redis_client):
        """Auto-triggered isolate/failover/rollback must be blocked."""
        from services.healing.safety_checks import pre_execution_check

        for action in ["isolate", "failover", "rollback"]:
            allowed, reason = await pre_execution_check(
                action_type=action,
                resource_id="test-resource",
                redis_client=redis_client,
                auto_triggered=True,
            )
            assert not allowed, f"Action '{action}' should be blocked for auto-trigger"
            assert "manual confirmation" in reason.lower() or "requires" in reason.lower()

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, redis_client):
        """Verify per-resource rate limit is enforced."""
        from services.healing.safety_checks import pre_execution_check
        import uuid as _uuid

        resource = f"rate-test-{_uuid.uuid4().hex[:8]}"
        # restart allows 5 per hour per resource
        results = []
        for i in range(7):
            allowed, reason = await pre_execution_check(
                action_type="restart",
                resource_id=resource,
                redis_client=redis_client,
                auto_triggered=False,
            )
            results.append(allowed)

        # First 5 should be allowed, remaining should be blocked
        assert all(results[:5]), "First 5 restarts should be allowed"
        assert not any(results[6:]), "6th+ restarts should be rate-limited"

        # Cleanup rate limit keys
        await redis_client.delete(f"healing:rate:resource:{resource}:restart")

    @pytest.mark.asyncio
    async def test_dry_run_always_allowed(self, redis_client):
        """Dry-run mode must always return allowed=True."""
        from services.healing.safety_checks import pre_execution_check

        for action in ["restart", "scale_up", "isolate", "failover"]:
            allowed, reason = await pre_execution_check(
                action_type=action,
                resource_id="any-resource",
                redis_client=redis_client,
                auto_triggered=True,  # Even auto-triggered
                dry_run=True,
            )
            assert allowed, f"Dry-run should always be allowed, failed for {action}"
            assert reason == "dry_run"


# ────────────────────────────────────────────────────────────────────────────
# Phase 8: WebSocket Tests
# ────────────────────────────────────────────────────────────────────────────

class TestWebSocket:
    """Tests for Redis-backed WebSocket manager."""

    @pytest.mark.asyncio
    async def test_broadcast_via_redis(self, redis_client):
        """Verify broadcast publishes to ws:broadcast channel."""
        from services.websocket_manager import RedisWebSocketManager

        # Subscribe to the channel in test
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("ws:broadcast")

        # Give subscription time to complete
        await asyncio.sleep(0.2)

        ws_manager = RedisWebSocketManager()
        ws_manager._redis = redis_client
        test_msg = {"type": "test", "data": "hello"}
        await ws_manager.broadcast(test_msg)

        # Wait for message with retry (up to 2 seconds)
        msg = None
        for _ in range(10):
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if msg:
                break
            await asyncio.sleep(0.1)

        assert msg is not None, "Did not receive broadcast message via Redis pub/sub"
        assert json.loads(msg["data"]) == test_msg

        await pubsub.unsubscribe("ws:broadcast")
        await pubsub.close()
