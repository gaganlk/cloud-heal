"""
AIOps Platform Scheduler — Single-Process Background Supervisor.

This service runs as a dedicated container/process to ensure exactly-once execution
of high-overhead background tasks like monitoring, drift detection, and Kafka retries.
"""
import asyncio
import logging
import os
import signal
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.supervisor import supervise_task
from app.services.monitoring_service import MonitoringService
from app.services.drift_engine import DriftDetectionEngine
from app.services.kafka_retry_queue import retry_queue
from app.core.encryption import validate_encryption_key
from app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] scheduler: %(message)s",
)
logger = logging.getLogger("scheduler")

ML_RECALIBRATION_INTERVAL_HOURS = 6

async def _ml_recalibration_loop():
    """
    Periodically retrain the ML failure prediction model on real MetricHistory data.
    Runs every ML_RECALIBRATION_INTERVAL_HOURS hours. Requires at least 20 data points.
    """
    logger.info("[MLRecalibration] Loop started.")
    while True:
        try:
            from app.db.database import AsyncSessionLocal
            from app.db.models import MetricHistory
            from sqlalchemy import select
            import numpy as np
            from app.services.prediction.consumer import ml_predictor

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(MetricHistory).order_by(MetricHistory.timestamp.desc()).limit(5000)
                )
                rows = result.scalars().all()

            if len(rows) < 20:
                logger.info(f"[MLRecalibration] Insufficient data ({len(rows)} rows). Min 20 required. Skipping.")
            else:
                # Build feature matrix: [cpu, memory, disk_io, network_latency]
                X, y = [], []
                for r in rows:
                    cpu = r.value if r.metric_type == "cpu" else 0.0
                    mem = r.value if r.metric_type == "memory" else 0.0
                    # Simple risk score as label (heuristic ground truth)
                    risk = min(1.0, max(cpu, mem) / 100.0)
                    X.append([cpu, mem, 0.0, 0.0])
                    y.append(risk)
                
                ml_predictor.train(np.array(X), np.array(y))
                logger.info(f"[MLRecalibration] Model trained on {len(rows)} data points.")

        except Exception as e:
            logger.error(f"[MLRecalibration] Training failed: {e}")

        await asyncio.sleep(ML_RECALIBRATION_INTERVAL_HOURS * 3600)

async def run_scheduler():
    logger.info("=== AIOps Background Scheduler Starting ===")
    
    # 1. Environment Validation
    try:
        validate_encryption_key()
        logger.info("[Init] Encryption key validated.")
    except RuntimeError as e:
        logger.critical(f"[Init] ENCRYPTION_KEY error: {e}")
        return

    # 2. DB Connectivity
    await init_db()
    
    # 3. Kafka Retry Queue (Start as a managed task)
    try:
        await retry_queue.startup()
        logger.info("[Init] Kafka retry queue active.")
    except Exception as e:
        logger.warning(f"[Init] Kafka retry queue failed to start: {e}")

    # 4. Define and Supervise Loops
    tasks = [
        asyncio.create_task(supervise_task(
            "MonitoringService", MonitoringService.monitor_cloud_resources
        )),
        asyncio.create_task(supervise_task(
            "DriftDetection", DriftDetectionEngine.start_drift_loop
        )),
        asyncio.create_task(supervise_task(
            "MLRecalibration", _ml_recalibration_loop
        )),
    ]

    # Signal handling for graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    
    def shutdown_signal():
        logger.info("Shutdown signal received...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_signal)

    try:
        # Keep running until stop signal
        await stop_event.wait()
    finally:
        logger.info("Stopping background tasks...")
        for t in tasks:
            t.cancel()
        
        await retry_queue.shutdown()
        logger.info("Scheduler stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        pass
