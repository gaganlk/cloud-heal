"""
Security Router — Full Phase 4 implementation.

Endpoints:
  GET  /api/security/findings        → paginated, filterable findings
  GET  /api/security/posture         → risk matrix + CIS breakdown
  GET  /api/security/iam-risks       → over-permissioned IAM findings
  GET  /api/security/encryption      → unencrypted resource findings
  GET  /api/security/incidents       → correlated security incidents
  POST /api/security/scan            → trigger cross-cloud security scan
  POST /api/security/remediate/{id}  → create safe remediation plan
  POST /api/security/plan/{id}/approve → approve and execute plan
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, desc, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, AsyncSessionLocal
from app.db.models import (
    User, SecurityFinding, CloudCredential, Incident, RemediationPlan
)
from app.api.endpoints.auth import get_current_user, require_role
from app.services.risk_engine import RiskEngine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Security"])


# ── Findings ──────────────────────────────────────────────────────────────────

@router.get("/findings")
async def get_security_findings(
    severity: Optional[str] = Query(None, description="critical | high | medium | low"),
    provider: Optional[str] = Query(None),
    status: str = Query("open"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator", "engineer"])),
):
    """List security findings with optional filters. Sorted by risk_score desc."""
    q = (
        select(SecurityFinding)
        .where(SecurityFinding.tenant_id == current_user.tenant_id)
        .where(SecurityFinding.status == status)
        .order_by(desc(SecurityFinding.risk_score))
        .limit(limit)
    )
    if severity:
        q = q.where(SecurityFinding.severity == severity)
    if provider:
        q = q.where(SecurityFinding.provider == provider)

    result = await db.execute(q)
    findings = result.scalars().all()

    return [
        {
            "id": f.id,
            "resource_id": f.resource_id,
            "provider": getattr(f, "provider", "aws"),
            "finding_type": f.finding_type,
            "severity": f.severity,
            "description": f.description,
            "remediation": f.remediation,
            "risk_score": f.risk_score,
            "impact": f.impact,
            "compliance_id": f.compliance_id,
            "iam_user": getattr(f, "iam_user", None),
            "status": f.status,
            "detected_at": f.created_at.isoformat(),
        }
        for f in findings
    ]


# ── Security Posture ──────────────────────────────────────────────────────────

@router.get("/posture")
async def get_security_posture(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator", "engineer"])),
):
    """
    Full security posture: overall risk score, provider breakdown,
    category breakdown, and heatmap data for D3 visualization.
    """
    matrix = await RiskEngine.compute_tenant_risk_matrix(db, current_user.tenant_id)

    # CIS compliance score per section
    result = await db.execute(
        select(SecurityFinding)
        .where(SecurityFinding.tenant_id == current_user.tenant_id)
        .where(SecurityFinding.status == "open")
    )
    findings = result.scalars().all()

    cis_counts: Dict[str, int] = {}
    for f in findings:
        cis_id = f.compliance_id or "Unknown"
        section = cis_id.split(".")[0] if "." in cis_id else cis_id
        cis_counts[section] = cis_counts.get(section, 0) + 1

    # Severity distribution
    severity_dist: Dict[str, int] = {}
    for f in findings:
        severity_dist[f.severity] = severity_dist.get(f.severity, 0) + 1

    # Top risky resources
    heatmap = matrix.get("heatmap_data", [])
    top_resources = heatmap[:10]

    return {
        **matrix,
        "cis_violation_counts": cis_counts,
        "severity_distribution": severity_dist,
        "top_risky_resources": top_resources,
        "posture_grade": _posture_grade(matrix.get("overall_score", 0)),
    }


# ── IAM Risks ─────────────────────────────────────────────────────────────────

@router.get("/iam-risks")
async def get_iam_risks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
):
    """IAM-specific findings: over-permission, missing MFA, privilege escalation."""
    IAM_FINDING_TYPES = [
        "MFA Not Enabled", "IAM Policy Drift", "Iam Policy",
        "Over-Privileged Service Account",
    ]
    result = await db.execute(
        select(SecurityFinding)
        .where(SecurityFinding.tenant_id == current_user.tenant_id)
        .where(SecurityFinding.finding_type.in_(IAM_FINDING_TYPES))
        .where(SecurityFinding.status == "open")
        .order_by(desc(SecurityFinding.risk_score))
    )
    return result.scalars().all()


# ── Encryption Status ─────────────────────────────────────────────────────────

@router.get("/encryption")
async def get_encryption_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
):
    """Encryption findings: unencrypted volumes, storage, key vault issues."""
    ENCRYPTION_TYPES = [
        "Unencrypted EBS Volume",
        "Storage HTTP Allowed",
        "Key Vault Soft Delete Disabled",
        "Key Vault Purge Protection Disabled",
    ]
    result = await db.execute(
        select(SecurityFinding)
        .where(SecurityFinding.tenant_id == current_user.tenant_id)
        .where(SecurityFinding.finding_type.in_(ENCRYPTION_TYPES))
        .where(SecurityFinding.status == "open")
    )
    findings = result.scalars().all()

    return {
        "total_unencrypted": len(findings),
        "findings": [
            {
                "resource_id": f.resource_id,
                "provider": getattr(f, "provider", "aws"),
                "type": f.finding_type,
                "severity": f.severity,
                "risk_score": f.risk_score,
                "remediation": f.remediation,
            }
            for f in findings
        ],
    }


# ── Incidents ─────────────────────────────────────────────────────────────────

@router.get("/incidents")
async def get_incidents(
    status: str = Query("open"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "operator", "engineer"])),
):
    """List correlated security incidents produced by EventCorrelationEngine."""
    result = await db.execute(
        select(Incident)
        .where(Incident.tenant_id == current_user.tenant_id)
        .where(Incident.status == status)
        .order_by(desc(Incident.created_at))
    )
    incidents = result.scalars().all()

    return [
        {
            "id": i.id,
            "title": i.title,
            "severity": i.severity,
            "rule_matched": i.rule_matched,
            "affected_resources": i.affected_resources,
            "source_types": i.source_types,
            "timeline": i.timeline,
            "status": i.status,
            "created_at": i.created_at.isoformat(),
        }
        for i in incidents
    ]


# ── Remediation ───────────────────────────────────────────────────────────────

@router.post("/remediate/{finding_id}")
async def create_remediation_plan(
    finding_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
):
    """
    Create a safe remediation plan for a finding.
    Includes dry-run result and blast-radius analysis.
    Requires admin approval if blast radius is high.
    """
    from app.services.remediation_planner import RemediationPlanner

    result = await db.execute(
        select(SecurityFinding)
        .where(SecurityFinding.id == finding_id)
        .where(SecurityFinding.tenant_id == current_user.tenant_id)
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    try:
        plan = await RemediationPlanner.create_plan(
            db=db,
            finding=finding,
            tenant_id=current_user.tenant_id,
            created_by_id=current_user.id,
            credentials={},  # Credentials loaded from DB at execution time
        )
        return {
            "plan_id": plan.id,
            "action_type": plan.action_type,
            "status": plan.status,
            "dry_run": plan.dry_run_result,
            "blast_radius": plan.blast_radius_analysis,
            "requires_approval": plan.status == "pending_approval",
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/plan/{plan_id}/approve")
async def approve_and_execute_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Admin-only: approve and immediately execute a remediation plan."""
    from app.services.remediation_planner import RemediationPlanner

    result = await db.execute(
        select(RemediationPlan)
        .where(RemediationPlan.id == plan_id)
        .where(RemediationPlan.tenant_id == current_user.tenant_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    execution_result = await RemediationPlanner.execute_plan(
        db=db,
        plan_id=plan_id,
        approved_by_id=current_user.id,
        credentials={},  # Production: decrypted from CloudCredential
    )
    return execution_result


# ── Security Scan Trigger ─────────────────────────────────────────────────────

@router.post("/scan")
async def trigger_security_scan(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"])),
):
    """Trigger a cross-cloud security scan. Results persisted to security_findings."""
    from app.services.security_normalizer import SecurityNormalizer

    result = await db.execute(
        select(CloudCredential)
        .where(CloudCredential.tenant_id == current_user.tenant_id)
        .where(CloudCredential.is_active == True)
    )
    creds = result.scalars().all()

    if not creds:
        raise HTTPException(status_code=400, detail="No active cloud credentials found")

    async def _scan():
        async with AsyncSessionLocal() as bg_db:
            await SecurityNormalizer.run_cross_cloud_scan(
                bg_db, current_user.tenant_id, creds
            )

    background_tasks.add_task(_scan)

    return {
        "status": "scan_started",
        "providers": list({c.provider for c in creds}),
        "message": "Security scan running in background. Results in ~60s.",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _posture_grade(score: float) -> str:
    if score < 20:  return "A"
    if score < 40:  return "B"
    if score < 60:  return "C"
    if score < 80:  return "D"
    return "F"
