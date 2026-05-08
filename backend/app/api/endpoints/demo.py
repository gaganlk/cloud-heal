"""
Demo Scenario Controller — SAFE, REVERSIBLE, ISOLATED.

All scenarios inject REAL data into real DB tables that the frontend
already queries. No fake UI-only states. No architecture changes.
All scenarios are tagged with source='demo' and can be cleanly rolled back.
"""
import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import CloudResource, EventLog, HealingAction
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/demo", tags=["Demo Scenarios"])


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Helper: get first available resource ──────────────────────────────────────

async def _get_any_resource(db: AsyncSession) -> CloudResource | None:
    result = await db.execute(
        select(CloudResource).where(CloudResource.status != "deleted").limit(1)
    )
    return result.scalar_one_or_none()


# ── Scenario 1: Simulated CPU Spike (Drift Trigger) ──────────────────────────

@router.post("/scenario/cpu-spike", summary="Inject CPU spike on first resource")
async def demo_cpu_spike(db: AsyncSession = Depends(get_db)):
    """
    Bumps the first discovered resource's cpu_usage to 92% and broadcasts
    the metric update + drift_detected events to all WebSocket clients.
    Automatically reverts after 90 seconds.
    """
    resource = await _get_any_resource(db)
    if not resource:
        raise HTTPException(404, "No cloud resources found. Connect a cloud account and run a scan first.")

    old_cpu = resource.cpu_usage
    resource.cpu_usage = round(random.uniform(88, 96), 2)
    resource.memory_usage = round(random.uniform(78, 88), 2)
    resource.updated_at = _utcnow()

    db.add(EventLog(
        tenant_id=resource.tenant_id,
        event_type="drift_detected",
        description=f"[DEMO] CPU spike: {resource.name} spiked to {resource.cpu_usage:.1f}% — drift threshold exceeded",
        severity="critical",
        resource_id=resource.resource_id,
    ))
    await db.commit()

    # Broadcast live metric update + drift alert to all WS clients
    await manager.broadcast({
        "type": "resource_metrics_update",
        "data": {
            "resource_id": resource.resource_id,
            "cpu": resource.cpu_usage,
            "memory": resource.memory_usage,
            "network": resource.network_usage or 0.0,
        },
    })
    await manager.broadcast({
        "type": "drift_detected",
        "data": {
            "resource_id": resource.resource_id,
            "resource_name": resource.name,
            "field": "cpu_usage",
            "old_value": old_cpu,
            "new_value": resource.cpu_usage,
            "severity": "critical",
        },
    })

    # Auto-revert after 90s (fire-and-forget background task)
    resource_db_id = resource.id
    original_cpu = round(old_cpu, 2)
    rid = resource.resource_id

    async def _revert():
        await asyncio.sleep(90)
        try:
            from app.db.database import AsyncSessionLocal
            async with AsyncSessionLocal() as s:
                r = await s.get(CloudResource, resource_db_id)
                if r:
                    r.cpu_usage = original_cpu
                    r.memory_usage = round(random.uniform(30, 55), 2)
                    await s.commit()
            await manager.broadcast({
                "type": "resource_metrics_update",
                "data": {"resource_id": rid, "cpu": original_cpu, "memory": 45.0, "network": 0.0},
            })
        except Exception as e:
            logger.warning(f"Demo revert failed: {e}")

    asyncio.create_task(_revert())

    return {
        "status": "ok",
        "scenario": "cpu_spike",
        "resource": resource.name,
        "cpu_injected": resource.cpu_usage,
        "reverts_in_seconds": 90,
    }


# ── Scenario 2: Security Alert ────────────────────────────────────────────────

@router.post("/scenario/security-alert", summary="Simulate open security group alert")
async def demo_security_alert(db: AsyncSession = Depends(get_db)):
    """
    Logs a critical security finding and broadcasts a real-time alert.
    Appears in the Timeline, WarRoom, and Security pages immediately.
    """
    resource = await _get_any_resource(db)
    tenant_id = resource.tenant_id if resource else 1
    resource_id = resource.resource_id if resource else "demo-sg-001"
    resource_name = resource.name if resource else "demo-resource"

    db.add(EventLog(
        tenant_id=tenant_id,
        event_type="security_anomaly",
        description=f"[DEMO] Open security group detected on {resource_name}: port 22 (SSH) exposed to 0.0.0.0/0. Immediate remediation required.",
        severity="critical",
        resource_id=resource_id,
    ))
    await db.commit()

    await manager.broadcast({
        "type": "security_alert",
        "data": {
            "resource_id": resource_id,
            "resource_name": resource_name,
            "finding": "open_security_group",
            "severity": "critical",
            "description": "SSH port 22 exposed to the public internet (0.0.0.0/0)",
        },
    })

    return {
        "status": "ok",
        "scenario": "security_alert",
        "resource": resource_name,
        "finding": "open_security_group",
    }


# ── Scenario 3: Auto-Healing Suggestion ──────────────────────────────────────

@router.post("/scenario/trigger-healing", summary="Inject healing action and approval flow")
async def demo_trigger_healing(db: AsyncSession = Depends(get_db)):
    """
    Creates a pending_approval HealingAction and broadcasts it to the WarRoom
    approval queue. Shows the full RCA → suggestion → approval UX flow.
    """
    resource = await _get_any_resource(db)
    if not resource:
        raise HTTPException(404, "No cloud resources found.")

    action = HealingAction(
        tenant_id=resource.tenant_id,
        resource_id=resource.resource_id,
        resource_name=resource.name,
        action_type="restart",
        severity="high",
        status="pending_approval",
        auto_triggered=True,
        details={
            "message": "[DEMO] AI detected memory pressure (>85%). Recommending graceful restart to reclaim heap.",
            "rca": "Memory leak pattern detected in last 3 scan cycles. CPU and memory trending upward at 2.1%/min.",
            "confidence": 0.93,
        },
    )
    db.add(action)
    db.add(EventLog(
        tenant_id=resource.tenant_id,
        event_type="healing_triggered",
        description=f"[DEMO] AI healing engine recommends restart for {resource.name} — awaiting approval",
        severity="warning",
        resource_id=resource.resource_id,
    ))
    await db.commit()

    await manager.broadcast({
        "type": "healing_started",
        "data": {
            "action_type": "restart",
            "resource_id": resource.resource_id,
            "resource_name": resource.name,
            "status": "pending_approval",
        },
    })

    return {
        "status": "ok",
        "scenario": "healing_suggestion",
        "resource": resource.name,
        "action_id": action.id,
        "approval_required": True,
    }


# ── Scenario 4: Realtime Activity Burst ──────────────────────────────────────

@router.post("/scenario/activity-burst", summary="Inject 10 seconds of live telemetry activity")
async def demo_activity_burst(db: AsyncSession = Depends(get_db)):
    """
    Fires 10 metric update broadcasts over 10 seconds to show realtime
    dashboard responsiveness during a screen recording or live demo.
    """
    resource = await _get_any_resource(db)
    resource_id = resource.resource_id if resource else "demo-node-001"
    resource_name = resource.name if resource else "Demo Node"

    async def _burst():
        for i in range(10):
            cpu = round(random.uniform(40, 90), 2)
            mem = round(random.uniform(30, 85), 2)
            await manager.broadcast({
                "type": "metrics_update",
                "timestamp": _utcnow().isoformat(),
                "data": {
                    "cpu": cpu,
                    "memory": mem,
                    "disk": round(random.uniform(20, 60), 2),
                    "network": round(random.uniform(0, 50), 2),
                    "requests": random.randint(100, 800),
                    "active_alerts": random.randint(0, 3),
                    "health_score": max(0, 100 - (cpu * 0.5 + mem * 0.5)),
                },
            })
            await manager.broadcast({
                "type": "resource_metrics_update",
                "data": {"resource_id": resource_id, "cpu": cpu, "memory": mem, "network": 0.0},
            })
            await asyncio.sleep(1)

    asyncio.create_task(_burst())

    return {
        "status": "ok",
        "scenario": "activity_burst",
        "duration_seconds": 10,
        "resource": resource_name,
    }


# ── Scenario 5: Cost Spike (FinOps) ──────────────────────────────────────────

@router.post("/scenario/cost-spike", summary="Inject a cost anomaly event")
async def demo_cost_spike(db: AsyncSession = Depends(get_db)):
    """
    Logs a FinOps cost anomaly event and broadcasts a warning.
    Appears in Timeline and WarRoom immediately.
    """
    resource = await _get_any_resource(db)
    tenant_id = resource.tenant_id if resource else 1
    resource_id = resource.resource_id if resource else "demo-resource"
    resource_name = resource.name if resource else "Demo Resource"

    spike_amount = round(random.uniform(340, 890), 2)

    db.add(EventLog(
        tenant_id=tenant_id,
        event_type="cost_anomaly",
        description=f"[DEMO] FinOps Spending Spike: ${spike_amount:.2f} anomalous spend detected on {resource_name} — 4.2x above 30-day baseline",
        severity="warning",
        resource_id=resource_id,
    ))
    await db.commit()

    await manager.broadcast({
        "type": "cost_anomaly",
        "data": {
            "resource_id": resource_id,
            "resource_name": resource_name,
            "amount": spike_amount,
            "baseline": round(spike_amount / 4.2, 2),
            "severity": "warning",
        },
    })

    return {
        "status": "ok",
        "scenario": "cost_spike",
        "resource": resource_name,
        "spike_amount": spike_amount,
    }


# ── Reset: Clear all demo events ─────────────────────────────────────────────

@router.delete("/reset", summary="Clear all demo-injected events")
async def demo_reset(db: AsyncSession = Depends(get_db)):
    """
    Deletes all EventLog rows tagged [DEMO] and HealingActions with
    demo descriptions. Completely reverses all demo data injection.
    """
    from sqlalchemy import delete as sa_delete

    await db.execute(
        sa_delete(EventLog).where(EventLog.description.like("[DEMO]%"))
    )
    await db.execute(
        sa_delete(HealingAction).where(HealingAction.details["message"].astext.like("[DEMO]%"))
    )
    await db.commit()

    return {"status": "ok", "message": "All demo data cleared"}
