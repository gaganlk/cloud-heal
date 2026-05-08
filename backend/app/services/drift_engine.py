"""
Drift Detection Engine.
Compares current cloud resource state against a stored "desired state" snapshot.
When drift is detected, emits a WebSocket event and optionally triggers auto-remediation.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.compliance_engine import ComplianceEngine

logger = logging.getLogger(__name__)


# Fields that trigger drift alerts if changed
DRIFT_SENSITIVE_FIELDS = {
    "status", "cpu_usage", "memory_usage", "region", "resource_type", "tags",
    "iam_policy", "sg_rules", "bucket_policy"
}


# Thresholds for numeric drift
NUMERIC_DRIFT_THRESHOLDS = {
    "cpu_usage": 30.0,       # Alert if CPU changes by >30%
    "memory_usage": 40.0,    # Alert if memory changes by >40%
}


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class DriftReport:
    def __init__(self, resource_id: str, resource_name: str):
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.drifted_fields: List[Dict] = []
        self.is_critical = False
        self.detected_at = _utcnow()

    def add_drift(self, field: str, desired: Any, current: Any, severity: str = "warning"):
        self.drifted_fields.append({
            "field": field,
            "desired": desired,
            "current": current,
            "severity": severity,
        })
        if severity == "critical":
            self.is_critical = True

    @property
    def has_drift(self) -> bool:
        return len(self.drifted_fields) > 0

    def to_dict(self) -> dict:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "drifted_fields": self.drifted_fields,
            "is_critical": self.is_critical,
            "detected_at": self.detected_at,
            "drift_count": len(self.drifted_fields),
        }


class DriftDetectionEngine:
    @staticmethod
    async def record_drift_history(db: AsyncSession, resource_id: str, field: str, old_val: Any, new_val: Any):
        """Log a drift event to history."""
        from app.db.models import DriftHistory
        try:
            history = DriftHistory(
                resource_id=resource_id,
                field=field,
                old_value=str(old_val),
                new_value=str(new_val)
            )
            db.add(history)
            await db.flush()
        except Exception as e:
            logger.warning(f"Failed to record drift history: {e}")

    @staticmethod
    async def snapshot_desired_state(db: AsyncSession, resource_id: str, state: dict):
        """Save a 'desired state' snapshot for a resource."""
        from app.db.models import DesiredState
        from sqlalchemy import select
        try:
            # Try to find existing (safely use .first() to avoid MultipleRows error)
            result = await db.execute(select(DesiredState).where(DesiredState.resource_id == resource_id))
            obj = result.scalars().first()
            
            if obj:
                obj.desired_state = state
                obj.updated_at = datetime.now(tz=timezone.utc)
            else:
                obj = DesiredState(resource_id=resource_id, desired_state=state)
                db.add(obj)
            
            await db.commit()
            logger.info(f"Desired state snapshotted for {resource_id}")
        except Exception as e:
            logger.warning(f"Desired state snapshot failed: {e}")
            await db.rollback()

    @staticmethod
    async def get_desired_state(db: AsyncSession, resource_id: str) -> Optional[dict]:
        """Retrieve the desired state for a resource."""
        from app.db.models import DesiredState
        from sqlalchemy import select
        try:
            result = await db.execute(select(DesiredState).where(DesiredState.resource_id == resource_id))
            obj = result.scalars().first()
            if obj:
                return obj.desired_state
        except Exception as e:
            logger.debug(f"Desired state lookup failed: {e}")
        return None

    @staticmethod
    async def compare_states(db: AsyncSession, resource_id: str, resource_name: str,
                             desired: dict, current: dict) -> DriftReport:
        """Compare desired vs current state and produce a DriftReport with history."""
        report = DriftReport(resource_id, resource_name)

        # Standard fields to check
        for field in DRIFT_SENSITIVE_FIELDS:
            desired_val = desired.get(field)
            current_val = current.get(field)

            if desired_val is None:
                continue

            # Policy / Rule Comparison (JSON/Dict)
            if isinstance(desired_val, (dict, list)):
                if desired_val != current_val:
                    severity = "critical" if field in ["iam_policy", "bucket_policy", "sg_rules"] else "warning"
                    report.add_drift(field, desired_val, current_val, severity)
                    await DriftDetectionEngine.record_drift_history(db, resource_id, field, desired_val, current_val)
                continue

            # Numeric threshold comparison
            if field in NUMERIC_DRIFT_THRESHOLDS:
                try:
                    d_num = float(desired_val)
                    c_num = float(current_val or 0)
                    delta = abs(c_num - d_num)
                    threshold = NUMERIC_DRIFT_THRESHOLDS[field]
                    if delta > threshold:
                        severity = "critical" if delta > threshold * 1.5 else "warning"
                        report.add_drift(field, desired_val, current_val, severity)
                        # We don't record history for every metric jitter, only major shifts
                        if delta > threshold * 2:
                            await DriftDetectionEngine.record_drift_history(db, resource_id, field, desired_val, current_val)
                except (TypeError, ValueError):
                    pass
                continue

            # String / categorical comparison
            if str(desired_val) != str(current_val or ""):
                # Status change is always critical
                severity = "critical" if field == "status" else "warning"
                report.add_drift(field, desired_val, current_val, severity)
                await DriftDetectionEngine.record_drift_history(db, resource_id, field, desired_val, current_val)

        return report

    @staticmethod
    async def get_all_drift_reports(db: AsyncSession) -> List[dict]:
        """Scan all resources with desired states and return drift reports."""
        from app.db.models import DesiredState, CloudResource
        from sqlalchemy import select

        reports = []
        try:
            # Get all desired states
            result = await db.execute(select(DesiredState))
            desired_states = result.scalars().all()

            if not desired_states:
                return []

            for ds in desired_states:
                # Get current resource state (safely use .first() to avoid MultipleRows error)
                res_result = await db.execute(
                    select(CloudResource).where(CloudResource.resource_id == ds.resource_id)
                )
                resource = res_result.scalars().first()
                if not resource:
                    continue

                # Convert model to dict for comparison
                current = {
                    "resource_id": resource.resource_id,
                    "name": resource.name,
                    "resource_type": resource.resource_type,
                    "status": resource.status,
                    "region": resource.region,
                    "cpu_usage": resource.cpu_usage,
                    "memory_usage": resource.memory_usage,
                    "tags": resource.tags,
                    "iam_policy": resource.extra_metadata.get("iam_policy"),
                    "sg_rules": resource.extra_metadata.get("sg_rules"),
                    "bucket_policy": resource.extra_metadata.get("bucket_policy"),
                }

                report = await DriftDetectionEngine.compare_states(
                    db,
                    ds.resource_id,
                    resource.name,
                    ds.desired_state,
                    current
                )
                if report.has_drift:
                    report_dict = report.to_dict()
                    # Add compliance metadata and risk scoring
                    meta = ComplianceEngine.get_compliance_metadata(
                        report_dict["drifted_fields"][0]["field"].replace("_", " ").title(), # Simplified finding type mapping
                        report_dict["is_critical"] and "critical" or "high"
                    )
                    report_dict.update(meta)
                    reports.append(report_dict)
            
            await db.commit()

        except Exception as e:
            logger.error(f"Drift scan failed: {e}")
            await db.rollback()

        return reports


    @staticmethod
    async def start_drift_loop(interval_seconds: int = 60):
        """Background task: continuously check for drift every N seconds."""
        logger.info(f"Drift detection loop starting (interval={interval_seconds}s)")
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await DriftDetectionEngine._drift_check_cycle()
            except asyncio.CancelledError:
                logger.info("Drift detection loop cancelled")
                break
            except Exception as e:
                logger.error(f"Drift loop error: {e}")
                await asyncio.sleep(10)  # Back-off on error

    @staticmethod
    async def _drift_check_cycle():
        """Execute one drift detection cycle."""
        from app.db.database import AsyncSessionLocal
        from app.services.websocket_manager import manager as ws_manager

        async with AsyncSessionLocal() as db:
            reports = await DriftDetectionEngine.get_all_drift_reports(db)

            for report in reports:
                logger.warning(
                    f"Drift detected: {report['resource_name']} — "
                    f"{report['drift_count']} field(s) drifted"
                )
                # Broadcast to all WebSocket clients
                await ws_manager.broadcast({
                    "type": "drift_detected",
                    "data": report,
                })

                # Auto-remediate critical drifts (Skip for Demo/Legacy resources)
                if report.get("is_critical") and "Legacy" not in report["resource_name"] and "Demo" not in report["resource_name"]:
                    logger.warning(f"CRITICAL drift on {report['resource_name']} — scheduling remediation")
                
                    try:
                        from app.services.healing_engine import execute_healing_action
                        from app.services.encryption import decrypt_credentials
                        from app.db.models import CloudResource, CloudCredential
                        
                        # Get resource info and credentials
                        res_result = await db.execute(
                            select(CloudResource).where(CloudResource.resource_id == report["resource_id"])
                        )
                        res = res_result.scalars().first()
                        if res:
                            cred_result = await db.execute(
                                select(CloudCredential).where(CloudCredential.id == res.credential_id)
                            )
                            cred = cred_result.scalars().first()
                            if cred:
                                raw_creds = decrypt_credentials(cred.encrypted_data)
                                
                                # Use failover for DBs, isolate for others by default
                                action_type = "failover" if "db" in res.resource_type.lower() else "isolate"
                                
                                # Fire and forget remediation
                                asyncio.create_task(execute_healing_action(
                                    resource_id=res.resource_id,
                                    resource_name=res.name,
                                    action_type=action_type,
                                    severity="critical",
                                    provider=res.provider,
                                    credentials=raw_creds,
                                    broadcast_fn=ws_manager.broadcast,
                                    event_id=f"drift-{report['resource_id']}"
                                ))
                                logger.info(f"Auto-remediation task DISPATCHED for drift on {res.name}")
                    except Exception as remediate_err:
                        logger.error(f"Failed to trigger auto-remediation for drift: {remediate_err}")
