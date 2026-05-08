"""
Security Normalizer — Cross-cloud finding schema unification.

Takes raw findings from AWS / Azure / GCP adapters and converts
to a canonical SecurityFinding model before DB persistence.

Also orchestrates a full cross-cloud scan via the three adapters.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SecurityFinding, CloudCredential
from app.services.compliance_engine import ComplianceEngine
from app.services.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class SecurityNormalizer:

    @staticmethod
    async def run_cross_cloud_scan(
        db: AsyncSession,
        tenant_id: int,
        credentials: List[CloudCredential],
    ) -> Dict[str, int]:
        """
        Run security scan on all active credentials and persist normalized findings.
        Returns count of findings per provider.
        """
        from app.services.encryption import decrypt_credentials

        summary: Dict[str, int] = {}

        for cred in credentials:
            provider = cred.provider.lower()
            try:
                raw_creds = decrypt_credentials(cred.encrypted_data)
            except Exception:
                logger.warning(f"[SecurityNormalizer] Cannot decrypt creds for {provider} — skipping")
                continue

            raw_findings: List[Dict] = []
            try:
                if provider == "aws":
                    from app.services.cloud.aws_security import get_aws_security_findings
                    raw_findings = get_aws_security_findings(raw_creds)
                elif provider == "azure":
                    from app.services.cloud.azure_security import get_azure_security_findings
                    raw_findings = get_azure_security_findings(raw_creds)
                elif provider == "gcp":
                    from app.services.cloud.gcp_security import get_gcp_security_findings
                    raw_findings = get_gcp_security_findings(raw_creds)
            except Exception as e:
                logger.error(f"[SecurityNormalizer] Scan failed for {provider}: {e}")
                summary[provider] = 0
                continue

            count = 0
            for raw in raw_findings:
                normalized = SecurityNormalizer._normalize(raw, provider, tenant_id)
                if normalized:
                    db.add(normalized)
                    count += 1

            await db.flush()
            summary[provider] = count
            logger.info(f"[SecurityNormalizer] {count} findings persisted for {provider}")

        await db.commit()
        return summary

    @staticmethod
    def _normalize(
        raw: Dict[str, Any],
        provider: str,
        tenant_id: int,
    ) -> SecurityFinding:
        """Convert raw adapter output to canonical SecurityFinding model."""
        finding_type = raw.get("finding_type", "Unknown")
        severity = raw.get("severity", "medium").lower()

        # Enrich via ComplianceEngine
        meta = ComplianceEngine.get_compliance_metadata(finding_type, severity)

        # Dynamic risk score
        risk_score = RiskEngine.score_finding(
            finding_type=finding_type,
            severity=severity,
        )

        return SecurityFinding(
            tenant_id=tenant_id,
            resource_id=raw.get("resource_id", "unknown"),
            provider=raw.get("provider", provider),
            finding_type=finding_type,
            severity=severity,
            description=raw.get("description", ""),
            remediation=raw.get("remediation") or meta.get("remediation", ""),
            status="open",
            risk_score=risk_score,
            impact=meta.get("impact"),
            compliance_id=raw.get("compliance_id") or meta.get("compliance_id"),
            iam_user=raw.get("iam_user"),
            policy_arn=raw.get("policy_arn"),
        )
