"""
Circuit Breaker pattern for cloud SDK calls, Redis, and Kafka.

States:
  CLOSED   → normal operation, calls pass through
  OPEN     → failure threshold exceeded, calls rejected immediately
  HALF_OPEN → cooldown elapsed, one probe call allowed to test recovery

Usage:
    breaker = CircuitBreaker("aws-ec2", failure_threshold=5, reset_timeout=30)
    result = await breaker.call(boto3_async_fn, *args)
"""
import asyncio
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitOpenError(Exception):
    def __init__(self, name: str):
        super().__init__(f"Circuit '{name}' is OPEN — call rejected to protect downstream")
        self.circuit_name = name


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout

        self._state = "CLOSED"       # CLOSED | OPEN | HALF_OPEN
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        # Auto-transition OPEN → HALF_OPEN after cooldown
        if self._state == "OPEN":
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.reset_timeout:
                return "HALF_OPEN"
        return self._state

    def _record_success(self):
        self._failure_count = 0
        self._state = "CLOSED"

    def _record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            if self._state != "OPEN":
                logger.warning(
                    f"[CircuitBreaker] '{self.name}' OPEN after {self._failure_count} failures"
                )
            self._state = "OPEN"

    async def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            current_state = self.state

        if current_state == "OPEN":
            raise CircuitOpenError(self.name)

        if current_state == "HALF_OPEN":
            logger.info(f"[CircuitBreaker] '{self.name}' probing in HALF_OPEN state")

        try:
            if asyncio.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = await asyncio.get_event_loop().run_in_executor(None, lambda: fn(*args, **kwargs))
            async with self._lock:
                self._record_success()
            if current_state == "HALF_OPEN":
                logger.info(f"[CircuitBreaker] '{self.name}' CLOSED — recovered")
            return result
        except Exception as exc:
            async with self._lock:
                self._record_failure()
            raise


# ── Global registry of circuit breakers ────────────────────────────────────
_registry: dict[str, CircuitBreaker] = {}


def get_breaker(name: str, failure_threshold: int = 5, reset_timeout: float = 30.0) -> CircuitBreaker:
    """Get-or-create a named circuit breaker."""
    if name not in _registry:
        _registry[name] = CircuitBreaker(name, failure_threshold, reset_timeout)
    return _registry[name]
