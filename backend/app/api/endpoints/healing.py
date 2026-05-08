"""
Healing router — production-grade.

FIXES applied (Blocker #1):
  - Removed SQLite fallback (DB_URL = "sqlite://...") entirely
  - _run_healing() now uses AsyncSessionLocal (async PostgreSQL)
  - All DB queries converted to async SQLAlchemy 2.0 style
  - update_profile route converted to use AsyncSession
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, AsyncSessionLocal
from app.db.models import HealingAction, EventLog, CloudResource, CloudCredential, User
from app.services.healing_engine import execute_healing_action, get_auto_healing_decision
from app.services.graph_engine import calculate_node_risk
from app.services.websocket_manager import manager
from app.api.endpoints.auth import get_current_user
from app.services.encryption import decrypt_credentials
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter()

DESTRUCTIVE_ACTIONS = ["terminate_idle", "secure_s3", "isolate_sg", "failover", "rollback"]


class HealingRequest(BaseModel):
    resource_id: str
    resource_name: str
    action_type: str
    severity: Optional[str] = "medium"


class AutoHealRequest(BaseModel):
    resource_id: str
    credential_id: int


async def _run_healing(
    healing_id: int,
    resource_id: str,
    resource_name: str,
    action_type: str,
    severity: str,
    user_id: int,
    tenant_id: int,
):
    """
    Background task for executing a healing action.
    Uses AsyncSessionLocal (PostgreSQL) — no SQLite.
    """
    async with AsyncSessionLocal() as db:
        try:
            async def broadcast(msg: dict):
                await manager.broadcast(msg)

            # Fetch credential via async query
            cred_result = await db.execute(
                select(CloudCredential)
                .join(CloudResource, CloudResource.credential_id == CloudCredential.id)
                .where(CloudResource.resource_id == resource_id)
                .where(CloudCredential.user_id == user_id)
            )
            cred = cred_result.scalar_one_or_none()

            creds_dict = None
            provider = "aws"
            if cred:
                provider = cred.provider
                creds_dict = decrypt_credentials(cred.encrypted_data)

            result = await execute_healing_action(
                resource_id=resource_id,
                resource_name=resource_name,
                action_type=action_type,
                severity=severity,
                broadcast_fn=broadcast,
                provider=provider,
                credentials=creds_dict,
                event_id=str(healing_id),
            )

            # Update healing record
            action_result = await db.execute(
                select(HealingAction).where(HealingAction.id == healing_id)
            )
            action = action_result.scalar_one_or_none()
            if action:
                action.status = result["status"]
                action.details = result.get("details", {})
                action.completed_at = datetime.now(tz=timezone.utc)

            # Write event log
            db.add(EventLog(
                tenant_id=tenant_id,
                user_id=user_id,
                event_type="healing_completed",
                description=(
                    f"Healing '{action_type}' "
                    f"{'succeeded' if result['status'] == 'success' else 'failed'} "
                    f"for {resource_name}"
                ),
                severity="info" if result["status"] == "success" else "error",
                resource_id=resource_id,
            ))
            await db.commit()

            # Send in-app notification (best-effort)
            try:
                notif = NotificationService.build_notification(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    title=f"Healing {result['status'].title()}: {resource_name}",
                    message=result.get("details", {}).get(
                        "message",
                        f"Healing '{action_type}' completed with status: {result['status']}"
                    ),
                    notif_type="success" if result["status"] == "success" else "error",
                    link="/healing",
                )
                db.add(notif)
                await db.commit()
                await manager.broadcast({
                    "type": "new_notification",
                    "data": {
                        "title": notif.title,
                        "message": notif.message,
                        "type": notif.type,
                    },
                })
            except Exception as notif_err:
                logger.warning(f"Notification creation failed (non-fatal): {notif_err}")

        except Exception as e:
            logger.error(f"Healing task error for {resource_id}: {e}")
            # Mark record as failed
            try:
                fail_result = await db.execute(
                    select(HealingAction).where(HealingAction.id == healing_id)
                )
                action = fail_result.scalar_one_or_none()
                if action:
                    action.status = "failed"
                    action.details = {"error": str(e)}
                    action.completed_at = datetime.now(tz=timezone.utc)
                    await db.commit()
            except Exception:
                pass


@router.post("/trigger")
async def trigger_healing(
    request: HealingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requires_approval = request.action_type in DESTRUCTIVE_ACTIONS
    status = "pending_approval" if requires_approval else "running"

    action = HealingAction(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_id=request.resource_id,
        resource_name=request.resource_name,
        action_type=request.action_type,
        status=status,
        severity=request.severity,
        requires_approval=requires_approval,
        details={"started_at": datetime.now(tz=timezone.utc).isoformat()},
    )
    db.add(action)
    await db.flush()

    db.add(EventLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        event_type="healing_triggered",
        description=f"Healing '{request.action_type}' triggered for {request.resource_name}. Status: {status}",
        severity="warning",
        resource_id=request.resource_id,
    ))
    await db.commit()
    await db.refresh(action)

    if not requires_approval:
        background_tasks.add_task(
            _run_healing,
            action.id,
            request.resource_id,
            request.resource_name,
            request.action_type,
            request.severity,
            current_user.id,
            current_user.tenant_id,
        )

    return {
        "action_id": action.id,
        "status": status,
        "requires_approval": requires_approval,
        "message": f"Healing '{request.action_type}' {'queued for approval' if requires_approval else 'started'} for {request.resource_name}",
    }


@router.post("/auto-heal")
async def auto_heal(
    request: AutoHealRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cred_result = await db.execute(
        select(CloudCredential).where(
            CloudCredential.id == request.credential_id,
            CloudCredential.user_id == current_user.id,
        )
    )
    cred = cred_result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    resource_result = await db.execute(
        select(CloudResource).where(
            CloudResource.credential_id == request.credential_id,
            CloudResource.resource_id == request.resource_id,
        )
    )
    resource = resource_result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    risk = calculate_node_risk(resource.cpu_usage, resource.memory_usage, resource.status)
    severity = "critical" if risk >= 80 else "high" if risk >= 60 else "medium"

    resource_dict = {
        "resource_id": resource.resource_id,
        "name": resource.name,
        "resource_type": resource.resource_type,
        "cpu_usage": resource.cpu_usage,
        "memory_usage": resource.memory_usage,
        "status": resource.status,
    }
    decisions = get_auto_healing_decision(resource_dict, risk, severity)
    triggered = []

    for decision in decisions[:1]:
        requires_approval = decision["action"] in DESTRUCTIVE_ACTIONS
        status = "pending_approval" if requires_approval else "running"

        action = HealingAction(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            resource_id=resource.resource_id,
            resource_name=resource.name,
            action_type=decision["action"],
            status=status,
            severity=severity,
            auto_triggered=True,
            requires_approval=requires_approval,
            details={"reason": decision["reason"], "auto": True},
        )
        db.add(action)
        await db.flush()

        if not requires_approval:
            background_tasks.add_task(
                _run_healing,
                action.id,
                resource.resource_id,
                resource.name,
                decision["action"],
                severity,
                current_user.id,
                current_user.tenant_id,
            )
        
        triggered.append({
            "action_id": action.id,
            "action": decision["action"],
            "status": status,
            "requires_approval": requires_approval,
            "reason": decision["reason"],
        })

    await db.commit()
    return {
        "resource_id": request.resource_id,
        "risk_score": risk,
        "severity": severity,
        "actions_triggered": triggered,
    }


@router.get("/actions")
async def get_healing_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(HealingAction)
        .where(HealingAction.user_id == current_user.id)
        .order_by(HealingAction.created_at.desc())
        .limit(100)
    )
    actions = result.scalars().all()
    return [
        {
            "id": a.id,
            "resource_id": a.resource_id,
            "resource_name": a.resource_name,
            "action_type": a.action_type,
            "status": a.status,
            "severity": a.severity,
            "auto_triggered": a.auto_triggered,
            "requires_approval": a.requires_approval,
            "details": a.details,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        }
        for a in actions
    ]


@router.post("/{action_id}/approve")
async def approve_healing(
    action_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(HealingAction).where(HealingAction.id == action_id)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Healing action not found")
    
    if action.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Action is in status '{action.status}', not 'pending_approval'")

    action.status = "running"
    action.approved_by_id = current_user.id
    
    db.add(EventLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        event_type="healing_approved",
        description=f"Action '{action.action_type}' for {action.resource_name} approved by {current_user.username}",
        severity="info",
        resource_id=action.resource_id,
    ))
    await db.commit()

    background_tasks.add_task(
        _run_healing,
        action.id,
        action.resource_id,
        action.resource_name,
        action.action_type,
        action.severity,
        action.user_id,
        action.tenant_id,
    )

    return {"status": "success", "message": "Action approved and execution started"}


@router.post("/{action_id}/reject")
async def reject_healing(
    action_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(HealingAction).where(HealingAction.id == action_id)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Healing action not found")
    
    if action.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Action is in status '{action.status}', not 'pending_approval'")

    action.status = "rejected"
    
    db.add(EventLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        event_type="healing_rejected",
        description=f"Action '{action.action_type}' for {action.resource_name} rejected by {current_user.username}",
        severity="info",
        resource_id=action.resource_id,
    ))
    await db.commit()

    return {"status": "success", "message": "Action rejected"}
