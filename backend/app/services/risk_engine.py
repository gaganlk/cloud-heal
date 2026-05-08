"""
Risk Engine — Dynamic, multi-factor risk scoring.

NOT static thresholds. Three-factor weighted model:
  1. severity_score    (40%) — based on finding severity label
  2. asset_criticality (30%) — production tag, healing history, resource type
  3. exposure_level    (30%) — network exposure, public access, finding category

Final score: 0-100 float. Above 80 = critical zone.

Also produces:
  - Per-tenant risk matrix for heatmap
  - Risk breakdown by provider and category
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Scoring Tables ─────────────────────────────────────────────────────────────

SEVERITY_SCORES = {
    "critical": 95.0,
    "high":     75.0,
    "medium":   45.0,
    "low":      15.0,
}

# Finding types with inherent network exposure (public-facing = 1.0)
EXPOSURE_MAP = {
    "Public S3 Bucket":             1.0,
    "Public GCS Bucket":            1.0,
    "Public Blob Access Enabled":   1.0,
    "Open SSH Port":                0.9,
    "Open RDP Port":                0.9,
    "Open Telnet Port":             0.95,
    "Storage HTTP Allowed":         0.6,
    "IAM Policy Drift":             0.7,
    "Iam Policy":                   0.7,
    "Over-Privileged Service Account": 0.75,
    "Key Vault Soft Delete Disabled": 0.5,
    "Key Vault Purge Protection Disabled": 0.4,
    "Unencrypted EBS Volume":       0.45,
    "MFA Not Enabled":              0.65,
    "Sg Rules":                     0.8,
    "Security Group Rule Drift":    0.8,
}

# Resource type criticality modifiers
TYPE_CRITICALITY = {
    "db":      1.4,
    "database": 1.4,
    "rds":     1.4,
    "sql":     1.35,
    "k8s":     1.25,
    "kubernetes": 1.25,
    "secret":  1.4,
    "vault":   1.4,
    "prod":    1.2,
    "production": 1.2,
    "lambda":  1.1,
    "function": 1.1,
    "cosmos":  1.35,
    "dynamo":  1.35,
    "bigquery": 1.35,
}

class RiskEngine:

    @staticmethod
    def score_finding(
        finding_type: str,
        severity: str,
        resource_tags: Optional[dict] = None,
        resource_type: Optional[str] = None,
        has_healing_history: bool = False,
    ) -> float:
        """
        Compute dynamic risk score for a single finding.
        """
        severity_score = SEVERITY_SCORES.get(severity.lower(), 15.0)
        exposure_level = EXPOSURE_MAP.get(finding_type, 0.4)
        asset_criticality = 1.0

        # Boost criticality for production resources (expanded tag detection)
        tags = {k.lower(): v.lower() for k, v in (resource_tags or {}).items() if isinstance(v, str)}
        prod_keys = ["environment", "env", "stage", "target", "tier", "deployment"]
        prod_values = ["prod", "production", "live", "stable", "critical"]
        
        for pk in prod_keys:
            if tags.get(pk) in prod_values:
                asset_criticality *= 1.3
                break

        # Boost for known critical resource types
        rtype = (resource_type or "").lower()
        for keyword, multiplier in TYPE_CRITICALITY.items():
            if keyword in rtype:
                asset_criticality = max(asset_criticality, multiplier)

        # Boost for unstable resources
        if has_healing_history:
            asset_criticality *= 1.15

        # Weighted combination
        raw_score = (
            severity_score * 0.40
            + exposure_level * 100 * 0.30
            + min(asset_criticality * 33.3, 100) * 0.30
        )

        return round(min(100.0, raw_score), 2)

    @staticmethod
    async def compute_tenant_risk_matrix(
        db, tenant_id: int
    ) -> Dict[str, Any]:
        """
        Compute full risk matrix for a tenant:
          - overall_score: weighted avg of all open findings
          - by_provider: {aws: score, azure: score, gcp: score}
          - by_category: {iam: score, network: score, storage: score, encryption: score}
          - heatmap_data: [{resource_id, provider, risk_score, finding_type, label}]
        """
        from sqlalchemy import select
        from app.db.models import SecurityFinding, CloudResource, HealingAction
        from sqlalchemy.ext.asyncio import AsyncSession

        try:
            result = await db.execute(
                select(SecurityFinding)
                .where(SecurityFinding.tenant_id == tenant_id)
                .where(SecurityFinding.status == "open")
            )
            findings = result.scalars().all()

            if not findings:
                return _empty_matrix()

            # Get healing history resource IDs
            h_result = await db.execute(
                select(HealingAction.resource_id)
                .where(HealingAction.tenant_id == tenant_id)
            )
            healed_resources = {r[0] for r in h_result.all()}

            # Get resource type map
            res_result = await db.execute(
                select(CloudResource.resource_id, CloudResource.resource_type, CloudResource.tags)
                .where(CloudResource.tenant_id == tenant_id)
            )
            resource_map = {r[0]: (r[1], r[2]) for r in res_result.all()}

            scores_by_provider: Dict[str, List[float]] = {}
            scores_by_category: Dict[str, List[float]] = {}
            heatmap: List[Dict] = []

            for f in findings:
                rtype, rtags = resource_map.get(f.resource_id, ("unknown", {}))
                has_history = f.resource_id in healed_resources

                score = RiskEngine.score_finding(
                    finding_type=f.finding_type,
                    severity=f.severity,
                    resource_tags=rtags,
                    resource_type=rtype,
                    has_healing_history=has_history,
                )

                # Update finding risk_score in DB
                f.risk_score = score

                provider = getattr(f, "provider", "aws")
                scores_by_provider.setdefault(provider, []).append(score)

                category = _categorize(f.finding_type)
                scores_by_category.setdefault(category, []).append(score)

                heatmap.append({
                    "resource_id": f.resource_id,
                    "provider": provider,
                    "risk_score": score,
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "compliance_id": f.compliance_id,
                })

            await db.commit()

            overall = sum(
                s for lst in scores_by_provider.values() for s in lst
            ) / max(1, sum(len(lst) for lst in scores_by_provider.values()))

            return {
                "overall_score": round(overall, 2),
                "by_provider": {
                    p: round(sum(s) / len(s), 2)
                    for p, s in scores_by_provider.items()
                },
                "by_category": {
                    c: round(sum(s) / len(s), 2)
                    for c, s in scores_by_category.items()
                },
                "heatmap_data": sorted(heatmap, key=lambda x: x["risk_score"], reverse=True),
                "total_findings": len(findings),
            }

        except Exception as e:
            logger.error(f"[RiskEngine] Matrix computation failed: {e}")
            return _empty_matrix()


def _categorize(finding_type: str) -> str:
    """Map finding type to high-level category."""
    ft = finding_type.lower()
    if any(k in ft for k in ("iam", "permission", "role", "service account", "mfa")):
        return "iam"
    if any(k in ft for k in ("ssh", "rdp", "port", "nsg", "firewall", "sg", "telnet")):
        return "network"
    if any(k in ft for k in ("s3", "blob", "bucket", "gcs", "storage")):
        return "storage"
    if any(k in ft for k in ("encrypt", "ebs", "volume", "disk", "key vault")):
        return "encryption"
    return "other"


def _empty_matrix() -> Dict[str, Any]:
    return {
        "overall_score": 0.0,
        "by_provider": {},
        "by_category": {},
        "heatmap_data": [],
        "total_findings": 0,
    }
