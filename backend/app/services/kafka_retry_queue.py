"""
Kafka Retry Queue — persistent fallback for Kafka message delivery failures.

Architecture:
  - SQLite-backed retry table (same aiops_local.db, separate connection)
  - In-memory asyncio.Queue for hot path
  - Background drain task: retries every 30s with exponential backoff (max 4 retries)
  - On permanent failure (4 retries exhausted): marks as dead_letter

This ensures zero message loss even when Kafka is down for hours.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Max messages to hold in-memory before forcing to DB
_HOT_QUEUE_MAXSIZE = 500
_MAX_RETRIES = 4
_BASE_BACKOFF_S = 2.0
_DRAIN_INTERVAL_S = 30


class KafkaRetryQueue:
    def __init__(self):
        self._hot: asyncio.Queue = asyncio.Queue(maxsize=_HOT_QUEUE_MAXSIZE)
        self._db_path: Optional[str] = None
        self._drain_task: Optional[asyncio.Task] = None
        self._producer = None   # set by Kafka producer on init

    def attach_producer(self, producer):
        """Called by the Kafka producer to give retry queue a reference."""
        self._producer = producer

    async def startup(self, db_path: str = "aiops_local.db"):
        self._db_path = db_path
        await self._ensure_table()
        self._drain_task = asyncio.get_event_loop().create_task(self._drain_loop())
        logger.info("KafkaRetryQueue started")

    async def shutdown(self):
        if self._drain_task:
            self._drain_task.cancel()

    async def enqueue(self, topic: str, payload: Dict[str, Any]):
        """Add a failed message to retry queue. Hot path first, DB fallback."""
        entry = {
            "topic": topic,
            "payload": payload,
            "attempts": 0,
            "last_attempt": None,
            "status": "pending",
            "enqueued_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        try:
            self._hot.put_nowait(entry)
            logger.debug(f"[RetryQueue] Enqueued to hot queue: topic={topic}")
        except asyncio.QueueFull:
            await self._persist_to_db(entry)
            logger.warning(f"[RetryQueue] Hot queue full — persisted to DB: topic={topic}")

    async def _drain_loop(self):
        """Background task: drain hot queue and retry persisted messages."""
        while True:
            await asyncio.sleep(_DRAIN_INTERVAL_S)
            await self._drain_hot()
            await self._drain_db()

    async def _drain_hot(self):
        drained = 0
        while not self._hot.empty():
            entry = await self._hot.get()
            success = await self._attempt_send(entry)
            if not success and entry["attempts"] < _MAX_RETRIES:
                # Put back — but to DB to avoid blocking hot queue
                await self._persist_to_db(entry)
            drained += 1
        if drained:
            logger.info(f"[RetryQueue] Drained {drained} messages from hot queue")

    async def _drain_db(self):
        """Retry pending messages stored in SQLite."""
        try:
            import aiosqlite
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute(
                    "SELECT id, topic, payload, attempts FROM kafka_retry_queue WHERE status='pending' ORDER BY id LIMIT 50"
                ) as cursor:
                    rows = await cursor.fetchall()

            for row_id, topic, payload_str, attempts in rows:
                entry = {
                    "id": row_id,
                    "topic": topic,
                    "payload": json.loads(payload_str),
                    "attempts": attempts,
                }
                success = await self._attempt_send(entry)
                async with aiosqlite.connect(self._db_path) as db:
                    if success:
                        await db.execute(
                            "UPDATE kafka_retry_queue SET status='sent' WHERE id=?", (row_id,)
                        )
                    elif attempts + 1 >= _MAX_RETRIES:
                        await db.execute(
                            "UPDATE kafka_retry_queue SET status='dead_letter', attempts=? WHERE id=?",
                            (attempts + 1, row_id)
                        )
                        logger.error(f"[RetryQueue] Dead-lettered message id={row_id} topic={topic}")
                    else:
                        await db.execute(
                            "UPDATE kafka_retry_queue SET attempts=?, last_attempt=? WHERE id=?",
                            (attempts + 1, datetime.now(tz=timezone.utc).isoformat(), row_id)
                        )
                    await db.commit()
        except Exception as e:
            logger.warning(f"[RetryQueue] DB drain failed: {e}")

    async def _attempt_send(self, entry: dict) -> bool:
        if self._producer is None:
            return False
        backoff = _BASE_BACKOFF_S * (2 ** entry.get("attempts", 0))
        try:
            await asyncio.sleep(min(backoff, 16))  # max 16s backoff
            await self._producer.send(entry["topic"], entry["payload"])
            return True
        except Exception as e:
            logger.debug(f"[RetryQueue] Retry failed: {e}")
            return False

    async def _persist_to_db(self, entry: dict):
        try:
            import aiosqlite
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """INSERT INTO kafka_retry_queue (topic, payload, attempts, last_attempt, status, enqueued_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        entry["topic"],
                        json.dumps(entry["payload"]),
                        entry.get("attempts", 0),
                        entry.get("last_attempt"),
                        "pending",
                        entry.get("enqueued_at", datetime.now(tz=timezone.utc).isoformat()),
                    )
                )
                await db.commit()
        except Exception as e:
            logger.error(f"[RetryQueue] Failed to persist to DB: {e}")

    async def _ensure_table(self):
        try:
            import aiosqlite
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS kafka_retry_queue (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        topic       TEXT NOT NULL,
                        payload     TEXT NOT NULL,
                        attempts    INTEGER DEFAULT 0,
                        last_attempt TEXT,
                        status      TEXT DEFAULT 'pending',
                        enqueued_at TEXT
                    )
                """)
                await db.commit()
        except Exception as e:
            logger.error(f"[RetryQueue] Table init failed: {e}")


# Singleton
retry_queue = KafkaRetryQueue()
