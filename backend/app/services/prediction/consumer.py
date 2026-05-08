"""
Kafka consumer for the prediction service.
Fixes:
  1. Enables the healing_triggers publish (was commented out)
  2. Adds Redis-based event deduplication (idempotency)
  3. Adds dead-letter queue routing on processing failure
  4. Uses real FailurePredictorML (IsolationForest)
"""
import asyncio
import logging
import os

import redis.asyncio as aioredis
from faststream import FastStream, Logger
from faststream.kafka import KafkaBroker
from pydantic import BaseModel, ConfigDict

from app.services.prediction.ml_engine import FailurePredictorML

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DEGRADATION_THRESHOLD = float(os.getenv("DEGRADATION_THRESHOLD", "0.75"))
DEDUP_TTL_SECONDS = int(os.getenv("DEDUP_TTL_SECONDS", "3600"))

broker = KafkaBroker(KAFKA_BOOTSTRAP)
app = FastStream(broker)

ml_predictor = FailurePredictorML()

# Redis client for idempotency checks (initialized at startup)
_redis: aioredis.Redis = None


@app.on_startup
async def startup():
    global _redis
    _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info(f"Prediction consumer connected to Redis at {REDIS_URL}")
    logger.info(f"Listening for telemetry on Kafka: {KAFKA_BOOTSTRAP}")


@app.on_shutdown
async def shutdown():
    if _redis:
        await _redis.aclose()


@broker.subscriber("global_telemetry")
async def analyze_telemetry_for_failure(msg: "TelemetryEvent", logger: Logger):
    """
    Subscribes to raw telemetry stream, runs ML anomaly detection,
    and publishes to healing_triggers topic when degradation is critical.
    """
    telemetry_data = msg.model_dump()
    event_id = msg.event_id

    # ── Idempotency guard ─────────────────────────────────────────────────
    cache_key = f"telemetry:processed:{event_id}"
    if _redis and await _redis.exists(cache_key):
        logger.info(f"Duplicate event {event_id} — skipping")
        return
    if _redis:
        await _redis.setex(cache_key, DEDUP_TTL_SECONDS, "1")

    # ── ML Inference ──────────────────────────────────────────────────────
    try:
        score = ml_predictor.predict_degradation(telemetry_data)
    except Exception as e:
        logger.error(f"ML inference failed for event {event_id}: {e}")
        # Route to DLQ
        await _route_to_dlq(telemetry_data, str(e))
        return

    # ── Decision & Routing ───────────────────────────────────────────────
    if score > DEGRADATION_THRESHOLD:
        logger.warning(
            f"CRITICAL: Resource {msg.resource_id} degraded! "
            f"Score={score:.3f} (threshold={DEGRADATION_THRESHOLD})"
        )
        healing_trigger = {
            "resource_id": msg.resource_id,
            "score": score,
            "trigger_event_id": event_id,
            "cpu": msg.cpu,
            "memory": msg.memory,
            "timestamp": msg.timestamp,
            "is_chaos": telemetry_data.get("is_chaos", False),
            # Propagate tenant context so healing consumer doesn't default to user_id=1
            "tenant_id": msg.tenant_id,
            "user_id": msg.user_id,
        }
        # ✅ FIX: This was previously commented out — now enabled
        await broker.publish(healing_trigger, topic="healing_triggers")
        logger.info(f"Published healing trigger for {msg.resource_id}")
    else:
        logger.info(
            f"Resource {msg.resource_id} is healthy. Score={score:.3f}"
        )


@broker.subscriber("healing_triggers")
async def log_healing_trigger(msg: dict, logger: Logger):
    """
    Secondary consumer for healing triggers.
    Logs the trigger and can be extended to update DB status.
    Primary healing execution happens in the healing service consumer.
    """
    logger.info(
        f"Healing trigger received: resource={msg.get('resource_id')} "
        f"score={msg.get('score', 0):.3f}"
    )


async def _route_to_dlq(original_msg: dict, error: str):
    """Send failed messages to dead-letter queue for manual inspection."""
    try:
        await broker.publish(
            {"original_msg": original_msg, "error": error},
            topic="dead_letter_queue",
        )
    except Exception as e:
        logger.error(f"Failed to route to DLQ: {e}")


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    resource_id: str
    cpu: float
    memory: float
    timestamp: float
    disk_io: float = 0.0
    network_latency: float = 0.0
    is_chaos: bool = False
    # Propagated from monitoring service so healing consumer can attribute records
    tenant_id: int = 1
    user_id: int = 1


if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run())
