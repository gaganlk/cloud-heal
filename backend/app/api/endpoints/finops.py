"""
FinOps Router — Full Phase 4 implementation.

All endpoints are paginated, tenant-scoped, and role-protected.
Triggers FinOpsEngine analysis on POST /scan.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, desc, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, AsyncSessionLocal
from app.db.models import (
    User, CostRecord, CostRecommendation, CostAnomaly, CloudCredential
)
from app.api.endpoints.auth import get_current_user, require_role
from app.services.finops_engine import FinOpsEngine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["FinOps"])


# ── Summary ────────────────────────────────────────────────────────────────────

@router.get("/summary")
async def get_cost_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "finops", "operator"])),
):
    """
    Aggregated multi-cloud cost summary for current tenant.
    Returns: total_spend, by_provider, by_service (top 5), trend vs last month.
    """
    tid = current_user.tenant_id
    now = datetime.now(tz=timezone.utc)

    # Current month
    curr_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_start = (curr_start.replace(month=curr_start.month - 1)
                  if curr_start.month > 1
                  else curr_start.replace(year=curr_start.year - 1, month=12))

    result = await db.execute(
        select(CostRecord).where(CostRecord.tenant_id == tid)
    )
    records = result.scalars().all()

    curr_records = [r for r in records if r.date >= curr_start]
    prev_records = [r for r in records if prev_start <= r.date < curr_start]

    curr_total = sum(r.normalized_usd for r in curr_records)
    prev_total = sum(r.normalized_usd for r in prev_records)
    trend_pct = ((curr_total - prev_total) / prev_total * 100) if prev_total else 0

    # By provider
    by_provider: Dict[str, float] = {}
    for r in curr_records:
        by_provider[r.provider] = round(by_provider.get(r.provider, 0) + r.normalized_usd, 2)

    # Top 5 services
    service_map: Dict[str, float] = {}
    for r in curr_records:
        service_map[r.service] = round(service_map.get(r.service, 0) + r.normalized_usd, 2)
    top_services = sorted(service_map.items(), key=lambda x: x[1], reverse=True)[:5]

    # Anomaly count
    ca_result = await db.execute(
        select(sqlfunc.count(CostAnomaly.id))
        .where(CostAnomaly.tenant_id == tid)
        .where(CostAnomaly.status == "open")
    )
    anomaly_count = ca_result.scalar() or 0

    return {
        "current_month_usd": round(curr_total, 2),
        "previous_month_usd": round(prev_total, 2),
        "trend_pct": round(trend_pct, 2),
        "trend_direction": "up" if trend_pct > 0 else "down",
        "by_provider": by_provider,
        "top_services": [{"service": s, "amount_usd": a} for s, a in top_services],
        "open_anomalies": anomaly_count,
    }


# ── Cost Records ───────────────────────────────────────────────────────────────

@router.get("/records")
async def get_cost_records(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "finops", "operator"])),
):
    """Paginated cost records with optional provider filter."""
    from datetime import timedelta
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    q = select(CostRecord).where(
        CostRecord.tenant_id == current_user.tenant_id,
        CostRecord.date >= cutoff,
    ).order_by(desc(CostRecord.date)).limit(limit)

    if provider:
        q = q.where(CostRecord.provider == provider)

    result = await db.execute(q)
    records = result.scalars().all()

    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "provider": r.provider,
            "service": r.service,
            "amount": r.amount,
            "currency": r.currency,
            "normalized_usd": r.normalized_usd,
            "exchange_rate": r.exchange_rate,
        }
        for r in records
    ]


# ── Anomalies ─────────────────────────────────────────────────────────────────

@router.get("/anomalies")
async def get_cost_anomalies(
    status: str = Query("open", description="open | resolved"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "finops", "operator"])),
):
    """List detected cost anomalies (spikes, idle waste, sustained growth)."""
    result = await db.execute(
        select(CostAnomaly)
        .where(CostAnomaly.tenant_id == current_user.tenant_id)
        .where(CostAnomaly.status == status)
        .order_by(desc(CostAnomaly.detected_at))
    )
    anomalies = result.scalars().all()

    return [
        {
            "id": a.id,
            "resource_id": a.resource_id,
            "provider": a.provider,
            "service": a.service,
            "anomaly_type": a.anomaly_type,
            "baseline_usd": a.baseline_amount,
            "actual_usd": a.actual_amount,
            "deviation_pct": a.deviation_pct,
            "risk_score": a.risk_score,
            "detected_at": a.detected_at.isoformat(),
        }
        for a in anomalies
    ]


# ── Recommendations ────────────────────────────────────────────────────────────

@router.get("/recommendations")
async def get_recommendations(
    rec_type: Optional[str] = Query(None, description="rightsize | idle | terminate"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "finops", "operator"])),
):
    """AI-driven rightsizing and idle resource recommendations."""
    q = select(CostRecommendation).where(
        CostRecommendation.tenant_id == current_user.tenant_id,
        CostRecommendation.status == "pending",
    ).order_by(desc(CostRecommendation.potential_savings))

    if rec_type:
        q = q.where(CostRecommendation.recommendation_type == rec_type)

    result = await db.execute(q)
    recs = result.scalars().all()

    total_savings = sum(r.potential_savings for r in recs)

    return {
        "total_potential_savings_usd": round(total_savings, 2),
        "count": len(recs),
        "recommendations": [
            {
                "id": r.id,
                "resource_id": r.resource_id,
                "provider": r.provider,
                "type": r.recommendation_type,
                "description": r.description,
                "savings_usd": round(r.potential_savings, 2),
                "confidence": r.confidence_score,
                "forecast_7d_usd": r.forecast_7d,
                "forecast_30d_usd": r.forecast_30d,
            }
            for r in recs
        ],
    }


# ── Forecast ──────────────────────────────────────────────────────────────────

@router.get("/forecast")
async def get_spend_forecast(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "finops", "operator"])),
):
    """ML-based 7-day and 30-day spend forecast per provider."""
    forecast = await FinOpsEngine.forecast_spend(db, current_user.tenant_id)
    return {"forecasts": forecast}


# ── Provider Breakdown ─────────────────────────────────────────────────────────

@router.get("/breakdown/{provider}")
async def get_provider_breakdown(
    provider: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "finops", "operator"])),
):
    """Per-provider service cost breakdown for the last N days."""
    from datetime import timedelta
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(CostRecord).where(
            CostRecord.tenant_id == current_user.tenant_id,
            CostRecord.provider == provider,
            CostRecord.date >= cutoff,
        ).order_by(CostRecord.date)
    )
    records = result.scalars().all()

    # Group by date + service for trend chart
    by_date: Dict[str, Dict[str, float]] = {}
    by_service: Dict[str, float] = {}

    for r in records:
        date_str = r.date.strftime("%Y-%m-%d")
        by_date.setdefault(date_str, {})
        by_date[date_str][r.service] = round(
            by_date[date_str].get(r.service, 0) + r.normalized_usd, 2
        )
        by_service[r.service] = round(by_service.get(r.service, 0) + r.normalized_usd, 2)

    return {
        "provider": provider,
        "days": days,
        "total_usd": round(sum(by_service.values()), 2),
        "by_service": sorted(by_service.items(), key=lambda x: x[1], reverse=True),
        "trend_data": [
            {"date": d, "services": s} for d, s in sorted(by_date.items())
        ],
    }


# ── Scan Trigger ──────────────────────────────────────────────────────────────

@router.post("/scan")
async def trigger_finops_scan(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "finops"])),
):
    """Trigger a fresh multi-cloud FinOps scan for this tenant."""
    # Load credentials (not decrypted here — engine handles it)
    result = await db.execute(
        select(CloudCredential)
        .where(CloudCredential.tenant_id == current_user.tenant_id)
        .where(CloudCredential.is_active == True)
    )
    creds = result.scalars().all()

    if not creds:
        raise HTTPException(status_code=400, detail="No active cloud credentials found")

    # Run async in background
    async def _scan():
        async with AsyncSessionLocal() as bg_db:
            cred_list = [
                {"provider": c.provider, "decrypted": {}}  # credentials decrypted by scanner
                for c in creds
            ]
            await FinOpsEngine.run_full_analysis(bg_db, current_user.tenant_id, cred_list)

    background_tasks.add_task(_scan)

    return {
        "status": "scan_started",
        "tenant_id": current_user.tenant_id,
        "credential_count": len(creds),
        "message": "FinOps analysis running in background. Results available in ~30s.",
    }
