"""
Kafka telemetry producer — production fix.

FIX applied (Blocker #7):
  - producer.poll(0) was a sync call inside async def, blocking the event loop.
  - Now wrapped in loop.run_in_executor(None, ...) to run in thread pool.
  - producer.flush() (used in stop()) also moved to executor.
  - Added configurable bootstrap_servers validation on init.
"""
import asyncio
import json
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


def _delivery_report(err, msg):
    """Called by librdkafka for each message delivery confirmation."""
    if err is not None:
        logger.error(
            f"Kafka delivery FAILED: topic={msg.topic()} "
            f"partition={msg.partition()} error={err}"
        )
    else:
        logger.debug(
            f"Kafka delivery OK: topic={msg.topic()} "
            f"partition={msg.partition()} offset={msg.offset()}"
        )


class KafkaTelemetryProducer:
    def __init__(self, bootstrap_servers: str):
        if not bootstrap_servers:
            raise ValueError("bootstrap_servers must not be empty")

        from confluent_kafka import Producer
        self._bootstrap = bootstrap_servers
        self.producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "acks": "all",                           # Wait for all in-sync replicas
            "compression.type": "gzip",
            "retries": 5,
            "retry.backoff.ms": 500,
            "enable.idempotence": True,              # Exactly-once producer semantics
            "max.in.flight.requests.per.connection": 5,
            "delivery.timeout.ms": 30000,
        })
        logger.info(f"KafkaTelemetryProducer initialized: {bootstrap_servers}")

    async def start(self):
        """No-op — confluent_kafka connects lazily on first produce()."""
        pass

    async def stop(self):
        """
        Flush all pending messages before shutdown.
        Runs in executor to avoid blocking the event loop.
        """
        loop = asyncio.get_running_loop()
        remaining = await loop.run_in_executor(None, self.producer.flush, 10)
        if remaining > 0:
            logger.warning(
                f"Kafka producer shut down with {remaining} messages undelivered"
            )

    async def send_metric(
        self,
        topic: str,
        metric_payload: dict,
        idempotency_key: Optional[str] = None,
    ) -> None:
        """
        Produce a message to Kafka.
        All sync confluent_kafka calls are offloaded to the thread pool executor
        so that the asyncio event loop is never blocked.
        """
        key = idempotency_key or metric_payload.get("event_id", str(uuid.uuid4()))
        value = json.dumps(metric_payload).encode("utf-8")
        key_bytes = key.encode("utf-8")
        headers = {"idempotency_key": key_bytes}

        loop = asyncio.get_running_loop()

        def _produce():
            try:
                self.producer.produce(
                    topic,
                    value=value,
                    key=key_bytes,
                    headers=headers,
                    callback=_delivery_report,
                )
                # poll(0) triggers delivery callbacks — must run in same thread as produce()
                self.producer.poll(0)
            except BufferError:
                # Queue full — drain briefly then retry once
                logger.warning("Kafka producer buffer full — draining before retry")
                self.producer.poll(1.0)
                self.producer.produce(
                    topic,
                    value=value,
                    key=key_bytes,
                    headers=headers,
                    callback=_delivery_report,
                )
                self.producer.poll(0)

        # Run the entire blocking produce+poll sequence in the thread pool
        await loop.run_in_executor(None, _produce)
