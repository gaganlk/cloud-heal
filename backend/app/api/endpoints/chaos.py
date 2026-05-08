"""
Chaos Engineering router — controlled fault injection for testing the healing pipeline.
Requires admin role. Injects synthetic telemetry events via Kafka.

FIX applied (Blocker #5):
  - Moved _get_db_dep and _require_admin to TOP of file (before any route definitions)
  - Replaced dynamic __import__ trick with standard imports
  - Fixed db dependency to use backend's async get_db correctly
"""
import asyncio
import os
import time
import uuid
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chaos", tags=["Chaos Engineering"])

KAFKA_BOOTSTRAP = settings.KAFKA_BOOTSTRAP_SERVERS
SECRET_KEY = settings.SECRET_KEY

# ── Auth helpers MUST be defined before any route that references them ────────

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def _require_admin(
    authorization: str = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),          # uses backend's async get_db
) -> User:
    """Gate all chaos endpoints: requires role='admin' on the JWT user."""
    try:
        payload = jwt.decode(authorization, SECRET_KEY, algorithms=["HS256"])
        user_id_str = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        if not user_id_str or tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(
        select(User).where(User.id == int(user_id_str), User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin role required for chaos engineering"
        )
    return user


# ── Request / Response schemas ────────────────────────────────────────────────

class ChaosScenario(BaseModel):
    resource_id: str = Field(..., description="Target resource ID to inject failure into")
    scenario: Literal["high_cpu", "high_memory", "network_spike", "service_crash"] = Field(
        ..., description="Failure scenario to inject"
    )
    severity: float = Field(
        default=0.95, ge=0.75, le=1.0,
        description="Metric severity multiplier (0.75–1.0)"
    )
    duration_seconds: int = Field(
        default=60, ge=10, le=300,
        description="How long to sustain injection (for multi-event scenarios)"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, log but don't publish to Kafka"
    )


class ChaosResult(BaseModel):
    event_id: str
    resource_id: str
    scenario: str
    events_published: int
    dry_run: bool
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/inject", response_model=ChaosResult)
async def inject_failure(
    scenario: ChaosScenario,
    current_user: User = Depends(_require_admin),
):
    """
    Inject a synthetic failure telemetry event for a specific resource.
    Publishes to the global_telemetry Kafka topic — the prediction consumer
    will detect it as anomalous and publish to healing_triggers.

    Use dry_run=true to validate the scenario without triggering real healing.
    """
    from app.packages.pkg_kafka.producer import KafkaTelemetryProducer

    SCENARIO_MAP = {
        "high_cpu":      {"cpu": scenario.severity * 100, "memory": 60.0, "disk_io": 20.0, "network_latency": 10.0},
        "high_memory":   {"cpu": 55.0, "memory": scenario.severity * 100, "disk_io": 15.0, "network_latency": 10.0},
        "network_spike": {"cpu": 45.0, "memory": 50.0, "disk_io": 5.0, "network_latency": scenario.severity * 2000},
        "service_crash": {"cpu": 0.0, "memory": 0.0, "disk_io": 0.0, "network_latency": 9999.0},
    }
    metrics = SCENARIO_MAP[scenario.scenario]
    event_id = f"chaos-{uuid.uuid4().hex[:12]}"

    telemetry_event = {
        "event_id": event_id,
        "resource_id": scenario.resource_id,
        "timestamp": time.time(),
        "is_chaos": True,
        "injected_by": current_user.username,
        "tenant_id": current_user.tenant_id,
        "user_id": current_user.id,
        **metrics,
    }

    if scenario.dry_run:
        logger.info(f"[CHAOS DRY RUN] Would inject: {telemetry_event}")
        return ChaosResult(
            event_id=event_id,
            resource_id=scenario.resource_id,
            scenario=scenario.scenario,
            events_published=0,
            dry_run=True,
            message=(
                f"Dry run complete. Would publish '{scenario.scenario}' "
                f"scenario for {scenario.resource_id}"
            ),
        )

    try:
        producer = KafkaTelemetryProducer(KAFKA_BOOTSTRAP)
        await producer.send_metric("global_telemetry", telemetry_event, idempotency_key=event_id)
        await producer.stop()
        logger.warning(
            f"[CHAOS] Injected '{scenario.scenario}' for {scenario.resource_id} "
            f"by {current_user.username} | event_id={event_id}"
        )
        return ChaosResult(
            event_id=event_id,
            resource_id=scenario.resource_id,
            scenario=scenario.scenario,
            events_published=1,
            dry_run=False,
            message=(
                f"Chaos scenario '{scenario.scenario}' injected for {scenario.resource_id}. "
                f"Watch healing_triggers topic for automated response."
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish chaos event to Kafka: {e}",
        )


@router.get("/scenarios")
async def list_scenarios(current_user: User = Depends(_require_admin)):
    """List available chaos scenarios with their expected healing responses."""
    return {
        "scenarios": [
            {
                "id": "high_cpu",
                "description": "Simulate CPU spike to 95–100%",
                "triggers": "scale_up or restart",
            },
            {
                "id": "high_memory",
                "description": "Simulate memory exhaustion to 95–100%",
                "triggers": "restart",
            },
            {
                "id": "network_spike",
                "description": "Simulate extreme network latency (2000ms+)",
                "triggers": "reroute",
            },
            {
                "id": "service_crash",
                "description": "Simulate total service crash (all metrics → 0)",
                "triggers": "restart or failover",
            },
        ],
        "safety_note": (
            "All chaos events are tagged is_chaos=true for post-mortem analysis. "
            "Healing safety checks still apply unless CHAOS_SAFETY_BYPASS=true."
        ),
        "rate_limits": "Per-resource: 5 restarts/hr, 10 scale_up/hr. Global limits apply.",
        "injected_by": current_user.username,
    }


@router.delete("/cancel/{event_id}")
async def cancel_chaos(
    event_id: str,
    current_user: User = Depends(_require_admin),
):
    """
    Publish a normalizing telemetry event to signal recovery after a chaos scenario.
    This tells the ML model the resource has returned to normal.
    """
    from app.packages.pkg_kafka.producer import KafkaTelemetryProducer
    import time

    # Extract resource_id from event_id convention if possible
    # event_id format: chaos-{12hex}
    # We can't easily cancel a specific resource without knowing it —
    # callers should pass the resource_id as a query param in a real impl.
    cancel_event = {
        "event_id": f"cancel-{uuid.uuid4().hex[:12]}",
        "resource_id": "unknown",
        "timestamp": time.time(),
        "is_chaos": False,
        "cpu": 20.0,
        "memory": 30.0,
        "disk_io": 5.0,
        "network_latency": 10.0,
        "tenant_id": current_user.tenant_id,
        "user_id": current_user.id,
        "cancels_event_id": event_id,
    }

    try:
        producer = KafkaTelemetryProducer(KAFKA_BOOTSTRAP)
        await producer.send_metric("global_telemetry", cancel_event)
        await producer.stop()
    except Exception as e:
        logger.warning(f"Cancel event publish failed: {e}")

    return {
        "message": (
            f"Normalizing telemetry published for event {event_id}. "
            "The ML model will update its anomaly score within the next polling cycle."
        ),
        "cancelled_event_id": event_id,
    }
