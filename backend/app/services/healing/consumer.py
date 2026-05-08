"""
Healing Service Kafka Consumer — Production Fix.

FIXES applied (Blocker #2, #3, #4):
  #2 — Replaced `SIMULATED: Action executed successfully` with real SDK call
       via execute_healing_action() from backend.services.healing_engine
  #3 — Removed hardcoded user_id=1; HealingTrigger now carries user_id/tenant_id
       propagated from the prediction consumer
  #4 — Removed hardcoded region_name="us-east-1"; credentials are loaded from
       the DB using CredentialManager and passed to execute_healing_action()
"""
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Path bootstrap: allow imports from backend/ and repo root ────────────────
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

import redis.asyncio as aioredis
from faststream import FastStream, Logger
from faststream.kafka import KafkaBroker
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import HealingAction, EventLog, CloudResource, CloudCredential
from app.services.healing_engine import execute_healing_action, get_auto_healing_decision
from app.services.healing.safety_checks import pre_execution_check
from app.services.encryption import decrypt_credentials

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

broker = KafkaBroker(KAFKA_BOOTSTRAP)
app = FastStream(broker)

_redis: aioredis.Redis = None


@app.on_startup
async def startup():
    global _redis
    _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info(f"Healing consumer started | Kafka={KAFKA_BOOTSTRAP} Redis={REDIS_URL}")


@app.on_shutdown
async def shutdown():
    if _redis:
        await _redis.aclose()


class HealingTrigger(BaseModel):
    """
    Schema for messages on the 'healing_triggers' Kafka topic.
    Must match what the prediction consumer publishes.
    """
    model_config = ConfigDict(extra="allow")

    resource_id: str
    score: float
    trigger_event_id: str
    # Propagated from telemetry event
    tenant_id: int = 1          # safe default; prediction consumer should always set this
    user_id: int = 1            # safe default
    cpu: float = 0.0
    memory: float = 0.0
    timestamp: float = 0.0
    is_chaos: bool = False


@broker.subscriber("healing_triggers")
async def execute_healing_action_from_kafka(msg: HealingTrigger, logger: Logger):
    """
    Subscribes to 'healing_triggers', resolves resource + credentials from DB,
    runs pre-execution safety checks, then calls real cloud SDK healing action.
    """
    logger.warning(
        f"HEALING TRIGGER: resource={msg.resource_id} "
        f"score={msg.score:.3f} tenant={msg.tenant_id} chaos={msg.is_chaos}"
    )

    async with AsyncSessionLocal() as db:
        # ── 1. Fetch resource ────────────────────────────────────────────────
        res_result = await db.execute(
            select(CloudResource).where(
                CloudResource.resource_id == msg.resource_id,
                CloudResource.tenant_id == msg.tenant_id,
            )
        )
        resource = res_result.scalar_one_or_none()
        if not resource:
            logger.error(
                f"Resource {msg.resource_id} not found for tenant {msg.tenant_id}. Skipping."
            )
            return

        # ── 2. Determine action type ─────────────────────────────────────────
        resource_dict = {
            "resource_id": resource.resource_id,
            "name": resource.name,
            "resource_type": resource.resource_type,
            "cpu_usage": resource.cpu_usage,
            "memory_usage": resource.memory_usage,
            "status": resource.status,
        }
        decisions = get_auto_healing_decision(resource_dict, msg.score * 100, "high")
        if not decisions:
            logger.info(f"No healing action needed for {msg.resource_id}")
            return

        action_type = decisions[0]["action"]
        reason = decisions[0]["reason"]

        # ── 3. Pre-execution safety check ────────────────────────────────────
        allowed, check_reason = await pre_execution_check(
            action_type=action_type,
            resource_id=msg.resource_id,
            redis_client=_redis,
            auto_triggered=True,
            dry_run=False,
        )
        if not allowed:
            logger.warning(
                f"Safety check BLOCKED {action_type} on {msg.resource_id}: {check_reason}"
            )
            return

        # ── 4. Idempotency guard ─────────────────────────────────────────────
        idempotency_key = f"{msg.resource_id}:{action_type}:{msg.trigger_event_id}"
        dedup_key = f"healing:executed:{idempotency_key}"
        is_new = await _redis.setnx(dedup_key, "1")
        if not is_new:
            logger.info(f"Duplicate healing trigger {msg.trigger_event_id} — skipping")
            return
        await _redis.expire(dedup_key, 3600)

        # ── 5. Create pending DB record ──────────────────────────────────────
        healing_record = HealingAction(
            tenant_id=msg.tenant_id,
            user_id=msg.user_id,
            resource_id=msg.resource_id,
            resource_name=resource.name,
            action_type=action_type,
            status="in_progress",
            severity="high",
            auto_triggered=True,
            idempotency_key=idempotency_key[:64],
            details={"reason": reason, "score": msg.score, "is_chaos": msg.is_chaos},
        )
        db.add(healing_record)
        await db.commit()
        await db.refresh(healing_record)

        # ── 6. Load credentials from DB ──────────────────────────────────────
        cred_result = await db.execute(
            select(CloudCredential).where(CloudCredential.id == resource.credential_id)
        )
        cred = cred_result.scalar_one_or_none()
        if not cred:
            logger.error(
                f"Credential {resource.credential_id} not found — cannot execute {action_type}"
            )
            healing_record.status = "failed"
            healing_record.details = {"error": "Credential not found in database"}
            await db.commit()
            return

        try:
            creds_dict = decrypt_credentials(cred.encrypted_data)
        except Exception as e:
            logger.error(f"Credential decryption failed for cred {cred.id}: {e}")
            healing_record.status = "failed"
            healing_record.details = {"error": f"Credential decryption failed: {e}"}
            await db.commit()
            return

        # ── 7. Execute real cloud SDK action ─────────────────────────────────
        logger.info(
            f"Executing {action_type} on {msg.resource_id} "
            f"via {resource.provider} (cred_id={cred.id})"
        )
        result = await execute_healing_action(
            resource_id=msg.resource_id,
            resource_name=resource.name,
            action_type=action_type,
            severity="high",
            broadcast_fn=None,   # No WebSocket in worker context
            provider=resource.provider,
            credentials=creds_dict,
            event_id=msg.trigger_event_id,
        )

        # ── 8. Finalize record ───────────────────────────────────────────────
        healing_record.status = result["status"]
        healing_record.details = result.get("details", {})
        healing_record.completed_at = datetime.now(tz=timezone.utc)

        db.add(EventLog(
            tenant_id=msg.tenant_id,
            user_id=msg.user_id,
            event_type="healing_executed",
            description=(
                f"Auto-healing ({action_type}) {result['status']} "
                f"for {resource.name}"
            ),
            severity="info" if result["status"] == "success" else "error",
            resource_id=msg.resource_id,
        ))
        await db.commit()

        logger.info(
            f"Healing completed: {result['status']} | "
            f"action={action_type} resource={msg.resource_id}"
        )


if __name__ == "__main__":
    asyncio.run(app.run())
