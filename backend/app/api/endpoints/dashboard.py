"""
Dashboard Router — Production fix.

FIXES applied (Critical C-1, C-2):
  C-1 — Removed random.uniform() metric mutations entirely.
         /metrics now returns real CloudResource rows from DB.
         No DB writes from a GET endpoint.
  C-2 — Removed duplicate WebSocket handler. All WebSocket traffic
         goes through main.py /ws/{client_id} -> MonitoringService.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.db.models import (
    CloudCredential, CloudResource, HealingAction, EventLog, User,
    SecurityFinding, DesiredState
)
from app.api.endpoints.auth import get_current_user

router = APIRouter()


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Optimized Aggregated dashboard statistics.
    Uses a single query to fetch all relevant data to avoid N+1 overhead.
    """
    # 1. Fetch all active credentials for user
    creds_query = await db.execute(select(CloudCredential.id).filter(
        CloudCredential.user_id == current_user.id,
        CloudCredential.is_active == True
    ))
    cred_ids = [c for c in creds_query.scalars().all()]

    if not cred_ids:
        return {
            "total_resources": 0, "total_credentials": 0, "providers": {},
            "resource_types": {}, "critical_resources": 0, "status_summary": {"running": 0, "stopped": 0, "unknown": 0},
            "healing_total": 0, "healing_success": 0, "avg_cpu": 0, "avg_memory": 0,
            "security_findings_critical": 0, "health_score": 100
        }

    # 2. Fetch all resources in one batch
    res_query = await db.execute(select(CloudResource).filter(CloudResource.credential_id.in_(cred_ids)))
    all_resources = res_query.scalars().all()

    # 3. Aggregation Logic
    providers = {}
    resource_types = {}
    critical_count = 0
    status_summary = {"running": 0, "stopped": 0, "unknown": 0}
    
    total_cpu = 0.0
    total_mem = 0.0

    for r in all_resources:
        providers[r.provider] = providers.get(r.provider, 0) + 1
        resource_types[r.resource_type] = resource_types.get(r.resource_type, 0) + 1
        
        cpu = r.cpu_usage or 0.0
        mem = r.memory_usage or 0.0
        total_cpu += cpu
        total_mem += mem

        if cpu > 80 or mem > 85:
            critical_count += 1
            
        st = (r.status or "unknown").lower()
        if any(x in st for x in ["run", "active", "up", "available"]):
            status_summary["running"] += 1
        elif any(x in st for x in ["stop", "terminate", "down", "off"]):
            status_summary["stopped"] += 1
        else:
            status_summary["unknown"] += 1

    # 4. Fetch Healing & Security Stats
    healing_total = await db.scalar(select(func.count(HealingAction.id)).filter(HealingAction.user_id == current_user.id)) or 0
    healing_success = await db.scalar(select(func.count(HealingAction.id)).filter(HealingAction.user_id == current_user.id, HealingAction.status == "success")) or 0
    
    resource_uids = [r.resource_id for r in all_resources]
    security_count = await db.scalar(select(func.count(SecurityFinding.id)).filter(
        SecurityFinding.resource_id.in_(resource_uids),
        SecurityFinding.status == "open",
        SecurityFinding.severity.in_(["critical", "high"])
    )) if resource_uids else 0

    # 5. Calculate Metrics & Health Score
    count = len(all_resources)
    avg_cpu = round(total_cpu / count, 2) if count > 0 else 0
    avg_mem = round(total_mem / count, 2) if count > 0 else 0
    
    deductions = (critical_count * 5) + (security_count * 10)
    if avg_cpu > 80: deductions += 10
    health_score = max(0, 100 - deductions)

    return {
        "total_resources": count,
        "total_credentials": len(cred_ids),
        "providers": providers,
        "resource_types": resource_types,
        "critical_resources": critical_count,
        "status_summary": status_summary,
        "healing_total": healing_total,
        "healing_success": healing_success,
        "avg_cpu": avg_cpu,
        "avg_memory": avg_mem,
        "security_findings_critical": security_count,
        "health_score": health_score,
    }


@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return current resource metrics from DB.
    Values come from the last cloud provider scan (MonitoringService).
    No random mutation — no DB writes on a GET endpoint.
    """
    creds_result = await db.execute(select(CloudCredential).filter(
        CloudCredential.user_id == current_user.id,
        CloudCredential.is_active == True,
    ))
    creds = creds_result.scalars().all()

    result = []
    for cred in creds:
        res_result = await db.execute(
            select(CloudResource).filter(CloudResource.credential_id == cred.id)
        )
        for r in res_result.scalars().all():
            result.append({
                "resource_id": r.resource_id,
                "name": r.name,
                "provider": r.provider,
                "resource_type": r.resource_type,
                "cpu_usage": r.cpu_usage or 0.0,
                "memory_usage": r.memory_usage or 0.0,
                "network_usage": r.network_usage or 0.0,
                "status": r.status,
                "region": r.region,
                "credential_id": cred.id,
                "last_updated": r.updated_at.isoformat() if r.updated_at else None,
            })
    return result


@router.get("/timeline")
async def get_timeline(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the last N event log entries for the current user."""
    events_result = await db.execute(
        select(EventLog)
        .filter(EventLog.user_id == current_user.id)
        .order_by(EventLog.created_at.desc())
        .limit(limit)
    )
    events = events_result.scalars().all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "description": e.description,
            "severity": e.severity,
            "resource_id": e.resource_id,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.post("/clear-cache")
async def clear_metric_cache(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Best-effort cache flush. Invalidates Redis-cached stats for this user.
    Frontend calls this from Settings → Flush Metric Cache.
    """
    try:
        from app.db.database import get_redis
        redis = await get_redis()
        if redis:
            pattern = f"stats:{current_user.id}:*"
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
            return {"flushed": len(keys), "status": "ok"}
    except Exception as e:
        pass  # Redis might not be available — non-fatal
    return {"flushed": 0, "status": "ok", "note": "Redis unavailable; cache is in-memory only"}