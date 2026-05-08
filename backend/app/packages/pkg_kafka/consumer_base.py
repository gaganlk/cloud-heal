"""
Base Kafka consumer with Dead-Letter Queue (DLQ) support, retry logic,
and structured logging. All consumers should inherit from this class.
"""
import asyncio
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

DLQ_TOPIC = "dead_letter_queue"


class BaseConsumer:
    """
    Base class for Kafka consumers with:
    - Automatic DLQ routing on processing failure
    - Configurable retry with exponential backoff
    - Structured error logging with event context
    """

    def __init__(self, broker, service_name: str, max_retries: int = 3):
        self.broker = broker
        self.service_name = service_name
        self.max_retries = max_retries

    async def handle_with_dlq(
        self,
        msg: Any,
        handler_fn: Callable[[Any], Awaitable[None]],
        event_id: str = "unknown",
    ) -> None:
        """
        Execute handler_fn(msg) with retry and DLQ routing on permanent failure.
        Retries follow exponential backoff: 1s, 2s, 4s, ...
        """
        last_error: Exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                await handler_fn(msg)
                return  # Success
            except Exception as e:
                last_error = e
                wait = 2 ** (attempt - 1)
                logger.warning(
                    f"[{self.service_name}] attempt {attempt}/{self.max_retries} "
                    f"failed for event {event_id}: {e}. Retrying in {wait}s..."
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(wait)

        # All retries exhausted — route to DLQ
        logger.error(
            f"[{self.service_name}] Event {event_id} permanently failed after "
            f"{self.max_retries} retries. Routing to DLQ."
        )
        await self._publish_to_dlq(msg, last_error, event_id)

    async def _publish_to_dlq(self, msg: Any, error: Exception, event_id: str) -> None:
        """Publish failed message to dead-letter queue topic."""
        try:
            dlq_payload = {
                "service": self.service_name,
                "event_id": event_id,
                "original_msg": msg if isinstance(msg, dict) else str(msg),
                "error": str(error),
                "error_type": type(error).__name__,
            }
            await self.broker.publish(dlq_payload, topic=DLQ_TOPIC)
            logger.info(f"[{self.service_name}] Event {event_id} routed to DLQ")
        except Exception as dlq_error:
            logger.critical(
                f"[{self.service_name}] CRITICAL: Failed to route event {event_id} "
                f"to DLQ: {dlq_error}. Message may be lost!"
            )
