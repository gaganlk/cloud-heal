"""
Prediction router — production fix.

FIXES applied:
  - Replaced sync Session with AsyncSession throughout
  - /resource/{resource_id} now fetches real MetricHistory from DB via
    get_real_metric_history() instead of using random-generated fake data
  - /all endpoint uses async queries
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.database import get_db
from app.db.models import CloudCredential, CloudResource, User
from app.services.prediction_engine import (
    predict_failure,
    batch_predict,
    get_real_metric_history,
)
from app.api.endpoints.auth import get_current_user

router = APIRouter()


@router.get("/resource/{resource_id}")
async def get_resource_prediction(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return failure prediction for a specific resource.
    Uses real MetricHistory data from PostgreSQL (last 24h).
    """
    # Find the resource owned by this user
    creds_result = await db.execute(
        select(CloudCredential).where(CloudCredential.user_id == current_user.id)
    )
    creds = creds_result.scalars().all()

    resource = None
    for cred in creds:
        r_result = await db.execute(
            select(CloudResource).where(
                CloudResource.credential_id == cred.id,
                CloudResource.resource_id == resource_id,
            )
        )
        r = r_result.scalar_one_or_none()
        if r:
            resource = r
            break

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Fetch real metric history from DB (replaces random-generated fake data)
    history = await get_real_metric_history(db, resource.id, hours=24)

    return predict_failure(
        {
            "resource_id": resource.resource_id,
            "name": resource.name,
            "resource_type": resource.resource_type,
            "provider": resource.provider,
            "cpu_usage": resource.cpu_usage,
            "memory_usage": resource.memory_usage,
            "network_usage": resource.network_usage,
            "status": resource.status,
        },
        history=history,
    )


@router.get("/all")
async def get_all_predictions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return predictions for all resources owned by the current user.
    Uses current metric snapshot (no per-resource history for batch efficiency).
    For per-resource history, use /resource/{id}.
    """
    creds_result = await db.execute(
        select(CloudCredential).where(
            CloudCredential.user_id == current_user.id,
            CloudCredential.is_active == True,
        )
    )
    creds = creds_result.scalars().all()

    all_resources = []
    for cred in creds:
        r_result = await db.execute(
            select(CloudResource).where(CloudResource.credential_id == cred.id)
        )
        for r in r_result.scalars().all():
            all_resources.append({
                "resource_id": r.resource_id,
                "name": r.name,
                "resource_type": r.resource_type,
                "provider": r.provider,
                "cpu_usage": r.cpu_usage,
                "memory_usage": r.memory_usage,
                "network_usage": r.network_usage,
                "status": r.status,
            })

    if not all_resources:
        return []

    return batch_predict(all_resources)
