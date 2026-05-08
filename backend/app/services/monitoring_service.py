"""
Background monitoring service — production rewrite.

FIXES applied:
  High-severity #8  — Monitoring loop now RE-SCANS cloud providers (every 5 cycles)
                       instead of republishing stale DB values. Fresh MetricHistory
                       rows are written on each scan.
  High-severity #13 — psutil.disk_usage('/') replaced with platform-aware path.
                       Works on both Linux (containers) and Windows (dev machines).

Architecture:
  - Runs as a background asyncio task started in FastAPI lifespan
  - Every 60s: publishes current resource metrics to Kafka global_telemetry topic
  - Every 5 min (5 cycles): re-scans each cloud provider with real SDK calls,
    upserts CloudResource rows, and appends MetricHistory entries
  - broadcast_metrics(): pushes host system metrics to a specific WebSocket client
"""
import asyncio
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

# ── Path bootstrap: allow imports from backend/ and repo root ────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
# Also add backend to path if not present
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.database import AsyncSessionLocal
from app.db.models import CloudResource, CloudCredential, MetricHistory
from app.services.websocket_manager import manager
from app.packages.pkg_kafka.producer import KafkaTelemetryProducer

logger = logging.getLogger(__name__)


def _get_disk_path() -> str:
    """Return a platform-appropriate path for disk usage measurement."""
    if sys.platform == "win32":
        return os.path.abspath(".")     # e.g. C:\
    return "/"


class MonitoringService:

    @staticmethod
    def get_host_metrics() -> dict:
        """Get real-time metrics of the host machine. Safe on all platforms."""
        try:
            import psutil
            disk_path = _get_disk_path()
            return {
                "cpu": psutil.cpu_percent(interval=None),
                "memory": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage(disk_path).percent,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning(f"Host metrics collection failed: {e}")
            return {
                "cpu": 0.0,
                "memory": 0.0,
                "disk": 0.0,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }

    @staticmethod
    async def monitor_cloud_resources():
        """
        Main monitoring loop. Runs forever as a background task.

        Cycle behaviour:
          Every cycle (60s):  publish current resource metrics to Kafka
          Every 5th cycle:    re-scan cloud provider APIs + write MetricHistory
        """
        from app.services.encryption import decrypt_credentials
        from app.services.cloud.aws_scanner import scan_aws_resources
        from app.services.cloud.gcp_scanner import scan_gcp_resources
        from app.services.cloud.azure_scanner import scan_azure_resources

        kafka_producer = KafkaTelemetryProducer(
            os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        )
        cycle = 0

        while True:
            try:
                cycle += 1
                # Rescan every cycle (60s) for better responsiveness
                do_rescan = True 
                
                # Train ML model every 60 cycles (~1 hour)
                do_train_ml = (cycle % 60 == 0) or (cycle == 1)

                async with AsyncSessionLocal() as db:
                    creds_result = await db.execute(
                        select(CloudCredential).where(CloudCredential.is_active == True)
                    )
                    creds = creds_result.scalars().all()

                    async def scan_cred(cred_id):
                        async with AsyncSessionLocal() as session:
                            try:
                                cred = await session.get(CloudCredential, cred_id)
                                if not cred: return

                                # ── Track current resources for deletion detection ──
                                old_res_result = await session.execute(
                                    select(CloudResource).where(CloudResource.credential_id == cred.id)
                                )
                                old_resources = {r.resource_id: r.status for r in old_res_result.scalars().all()}

                                raw_creds = decrypt_credentials(cred.encrypted_data)
                                if cred.provider == "aws":
                                    from app.services.cloud.aws_scanner import scan_aws_resources
                                    fresh = await asyncio.get_running_loop().run_in_executor(
                                        None, scan_aws_resources, raw_creds
                                    )
                                elif cred.provider == "gcp":
                                    from app.services.cloud.gcp_scanner import scan_gcp_resources
                                    fresh = await asyncio.get_running_loop().run_in_executor(
                                        None, scan_gcp_resources, raw_creds
                                    )
                                elif cred.provider == "azure":
                                    from app.services.cloud.azure_scanner import scan_azure_resources
                                    fresh = await asyncio.get_running_loop().run_in_executor(
                                        None, scan_azure_resources, raw_creds
                                    )
                                else:
                                    fresh = []

                                fresh_ids = set()
                                for r in fresh:
                                    fresh_ids.add(r["resource_id"])
                                    # Detect status change
                                    old_status = old_resources.get(r["resource_id"])
                                    new_status = r.get("status", "unknown")
                                    
                                    await _upsert_resource_with_history(session, cred, r)
                                    
                                    if old_status != new_status:
                                        await manager.broadcast({
                                            "type": "resource_state_change",
                                            "data": {
                                                "resource_id": r["resource_id"],
                                                "status": new_status,
                                                "name": r["name"],
                                                "provider": cred.provider
                                            }
                                        })
                                    
                                    # Always broadcast metrics update for live feel
                                    await manager.broadcast({
                                        "type": "resource_metrics_update",
                                        "data": {
                                            "resource_id": r["resource_id"],
                                            "cpu": r.get("cpu_usage", 0.0),
                                            "memory": r.get("memory_usage", 0.0),
                                            "network": r.get("network_usage", 0.0)
                                        }
                                    })

                                # ── Handle Deleted/Terminated Resources ──
                                for rid, status in old_resources.items():
                                    if rid not in fresh_ids and status != "deleted":
                                        # Resource exists in DB but not in Cloud API anymore
                                        res_to_del = await session.execute(
                                            select(CloudResource).where(
                                                CloudResource.resource_id == rid,
                                                CloudResource.credential_id == cred.id
                                            )
                                        )
                                        obj = res_to_del.scalar_one_or_none()
                                        if obj:
                                            # We mark as deleted then eventually remove, or just remove
                                            # For immediate "disappearing" feel, we remove it
                                            await session.delete(obj)
                                            await manager.broadcast({
                                                "type": "resource_deleted",
                                                "data": {"resource_id": rid}
                                            })

                                cred.last_scan = datetime.now(tz=timezone.utc)
                                cred.scan_status = "success"
                                await session.commit()
                            except Exception:
                                logger.exception(f"Re-scan failed for cred {cred_id}")
                                try:
                                    cred.scan_status = "error"
                                    await session.commit()
                                except: pass

                    if do_rescan:
                        await asyncio.gather(*(scan_cred(c.id) for c in creds))

                    for cred in creds:
                        # ── Publish telemetry to Kafka (every cycle) ─────────
                        resources_result = await db.execute(
                            select(CloudResource).where(
                                CloudResource.credential_id == cred.id
                            )
                        )
                        resources = resources_result.scalars().all()

                        for resource in resources:
                            telemetry = {
                                "event_id": str(uuid.uuid4()),
                                "resource_id": resource.resource_id,
                                "cpu": resource.cpu_usage,
                                "memory": resource.memory_usage,
                                "disk_io": 0.0,
                                "network_latency": 0.0,
                                "timestamp": time.time(),
                                "tenant_id": cred.tenant_id,
                                "user_id": cred.user_id,
                            }
                            try:
                                await kafka_producer.send_metric(
                                    "global_telemetry", telemetry
                                )
                            except Exception as kafka_err:
                                logger.warning(
                                    f"Kafka publish failed for {resource.resource_id}: {kafka_err}"
                                )

                    if do_train_ml:
                        try:
                            from app.services.anomaly_detection_engine import AnomalyDetectionEngine
                            # Use tenant 1 for training (default bootstrap tenant)
                            await AnomalyDetectionEngine.train_finops_model(db, 1)
                        except Exception as ml_err:
                            logger.error(f"Periodic ML training failed: {ml_err}")

                    await db.commit()

                # Broadcast host system metrics once per cycle to ALL clients
                # via the single Redis pub/sub fan-out (replaces the removed per-client loop)
                try:
                    import psutil
                    host = MonitoringService.get_host_metrics()
                    net_mb = round(psutil.net_io_counters().bytes_sent / 1_048_576, 2)
                    await manager.broadcast({
                        "type": "metrics_update",
                        "timestamp": host["timestamp"],
                        "data": {
                            "cpu": host["cpu"],
                            "memory": host["memory"],
                            "disk": host["disk"],
                            "network": net_mb,
                            "requests": 0,
                            "active_alerts": 0,
                            "health_score": max(0, 100 - (host["cpu"] * 0.5 + host["memory"] * 0.5)),
                        },
                    })
                except Exception as hm_err:
                    logger.debug(f"Host metrics broadcast failed: {hm_err}")

                # Sleep at the END of the cycle so startup scan is instant
                await asyncio.sleep(60)

            except Exception as loop_err:
                logger.error(f"Monitoring loop error: {loop_err}")
                await asyncio.sleep(10)     # Back-off before retry

    @staticmethod
    async def broadcast_metrics(client_id: str, websocket):
        """Push live host-system metrics to a specific WebSocket client."""
        while True:
            try:
                import psutil
                metrics = MonitoringService.get_host_metrics()

                net_usage = 0.0
                try:
                    net_usage = round(
                        psutil.net_io_counters().bytes_sent / 1024 / 1024, 2
                    )
                except Exception:
                    pass

                data = {
                    "type": "metrics_update",
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "client_id": client_id,
                    "data": {
                        "cpu": metrics["cpu"],
                        "memory": metrics["memory"],
                        "disk": metrics["disk"],
                        "network": net_usage,
                        "requests": 0,
                        "active_alerts": 0,
                        "health_score": max(
                            0,
                            100 - (metrics["cpu"] * 0.5 + metrics["memory"] * 0.5),
                        ),
                    },
                }
                await manager.send_personal_message(data, websocket)
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"Broadcast error for {client_id}: {e}")
                await asyncio.sleep(5)


async def _upsert_resource_with_history(db, cred, r: dict) -> None:
    """
    Upsert a CloudResource row and append a MetricHistory snapshot.
    Uses ON CONFLICT DO UPDATE (PostgreSQL UPSERT) via the unique constraint
    uq_tenant_cred_resource (tenant_id, credential_id, resource_id).
    """
    from app.db.models import CloudResource, MetricHistory
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    now = datetime.now(tz=timezone.utc)

    # ── Upsert resource ───────────────────────────────────────────────────
    is_postgres = "postgresql" in str(db.bind.url)
    
    if is_postgres:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(CloudResource).values(
            tenant_id=cred.tenant_id,
            credential_id=cred.id,
            resource_id=r["resource_id"],
            resource_type=r["resource_type"],
            name=r["name"],
            region=r.get("region"),
            status=r.get("status", "unknown"),
            provider=r["provider"],
            tags=r.get("tags", {}),
            extra_metadata=r.get("extra_metadata", {}),
            cpu_usage=r.get("cpu_usage", 0.0),
            memory_usage=r.get("memory_usage", 0.0),
            network_usage=r.get("network_usage", 0.0),
            updated_at=now,
        ).on_conflict_do_update(
            constraint="uq_tenant_cred_resource",
            set_={
                "status": r.get("status", "unknown"),
                "cpu_usage": r.get("cpu_usage", 0.0),
                "memory_usage": r.get("memory_usage", 0.0),
                "network_usage": r.get("network_usage", 0.0),
                "tags": r.get("tags", {}),
                "extra_metadata": r.get("extra_metadata", {}),
                "updated_at": now,
            },
        ).returning(CloudResource.id)
        result = await db.execute(stmt)
        resource_db_id = result.scalar_one()
    else:
        # Cross-dialect fallback (SQLite/other)
        result = await db.execute(select(CloudResource).where(
            CloudResource.tenant_id == cred.tenant_id,
            CloudResource.credential_id == cred.id,
            CloudResource.resource_id == r["resource_id"]
        ))
        resource = result.scalar_one_or_none()
        if resource:
            resource.status = r.get("status", "unknown")
            resource.cpu_usage = r.get("cpu_usage", 0.0)
            resource.memory_usage = r.get("memory_usage", 0.0)
            resource.network_usage = r.get("network_usage", 0.0)
            resource.updated_at = now
            resource_db_id = resource.id
        else:
            resource = CloudResource(
                tenant_id=cred.tenant_id,
                credential_id=cred.id,
                resource_id=r["resource_id"],
                resource_type=r["resource_type"],
                name=r["name"],
                region=r.get("region"),
                status=r.get("status", "unknown"),
                provider=r["provider"],
                cpu_usage=r.get("cpu_usage", 0.0),
                memory_usage=r.get("memory_usage", 0.0),
                updated_at=now
            )
            db.add(resource)
            await db.flush()
            resource_db_id = resource.id

    # ── Append MetricHistory rows ─────────────────────────────────────────
    for metric_type, value in [
        ("cpu", r.get("cpu_usage", 0.0)),
        ("memory", r.get("memory_usage", 0.0)),
        ("network", r.get("network_usage", 0.0)),
    ]:
        db.add(MetricHistory(
            resource_id=resource_db_id,
            metric_type=metric_type,
            value=value,
            unit="percent",
            timestamp=now,
        ))
