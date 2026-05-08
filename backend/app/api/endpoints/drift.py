"""
Drift Detection router — REST API for desired state management and drift reports.

FIXES applied (Major M-2):
  - Added get_current_user dependency to ALL endpoints.
    Previously all drift endpoints were publicly accessible with no auth.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.db.database import get_db
from app.db.models import User
from app.api.endpoints.auth import get_current_user
from app.services.drift_engine import DriftDetectionEngine

logger = logging.getLogger(__name__)
router = APIRouter()


class DesiredStateRequest(BaseModel):
    resource_id: str
    state: Dict[str, Any]
    notes: Optional[str] = None


@router.get("/status")
async def drift_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return current drift status for all monitored resources."""
    reports = await DriftDetectionEngine.get_all_drift_reports(db)
    return {
        "total_drifted": len(reports),
        "critical": sum(1 for r in reports if r.get("is_critical")),
        "reports": reports,
    }


@router.post("/snapshot/{resource_id}")
async def snapshot_desired_state(
    resource_id: str,
    req: DesiredStateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save the current state as the 'desired state' baseline for a resource."""
    await DriftDetectionEngine.snapshot_desired_state(db, resource_id, req.state)
    return {"message": f"Desired state saved for {resource_id}"}


@router.get("/snapshot/{resource_id}")
async def get_snapshot(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the stored desired state for a specific resource."""
    state = await DriftDetectionEngine.get_desired_state(db, resource_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail="No desired state found for this resource. "
                   "Run a POST /api/drift/snapshot/{resource_id} first.",
        )
    return {"resource_id": resource_id, "desired_state": state}


@router.post("/scan")
async def trigger_drift_scan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manual trigger for drift scan."""
    reports = await DriftDetectionEngine.get_all_drift_reports(db)
    return {
        "scanned_at": datetime.now(tz=timezone.utc).isoformat(),
        "drifted_resources": len(reports),
        "reports": reports,
    }


@router.get("/history/{resource_id}")
async def get_drift_history(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve historical drift events for a specific resource."""
    from app.db.models import DriftHistory
    try:
        result = await db.execute(
            select(DriftHistory)
            .where(DriftHistory.resource_id == resource_id)
            .order_by(DriftHistory.detected_at.desc())
        )
        history = result.scalars().all()
        return [
            {
                "id": h.id,
                "resource_id": h.resource_id,
                "field": h.field,
                "old_value": h.old_value,
                "new_value": h.new_value,
                "detected_at": h.detected_at.isoformat() if h.detected_at else None,
            }
            for h in history
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/snapshot/{resource_id}")
async def delete_snapshot(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a desired state snapshot (stop monitoring this resource for drift)."""
    await db.execute(
        text("DELETE FROM desired_states WHERE resource_id = :rid"),
        {"rid": resource_id},
    )
    await db.commit()
    return {"message": f"Desired state removed for {resource_id}"}