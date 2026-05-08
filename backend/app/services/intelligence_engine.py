import logging
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.db.models import CostRecord, SecurityFinding, CostRecommendation, CloudCredential
from app.services.cloud.aws_finops import get_aws_costs, get_aws_recommendations
from app.services.cloud.aws_security import get_aws_security_findings
from app.services.cloud.azure_finops import get_azure_costs, get_azure_recommendations
from app.services.cloud.azure_security import get_azure_security_findings
from app.services.cloud.gcp_finops import get_gcp_costs, get_gcp_recommendations
from app.services.cloud.gcp_security import get_gcp_security_findings
from app.services.encryption import decrypt_credentials
from app.services.anomaly_detection_engine import AnomalyDetectionEngine
from datetime import datetime

logger = logging.getLogger(__name__)

class IntelligenceEngine:
    """
    Orchestrates FinOps and Security intelligence gathering across all providers.
    """

    @staticmethod
    async def run_intelligence_scan(db: AsyncSession, credential_id: int):
        """
        Main entry point for intelligence scanning.
        Fetches costs, security findings, and recommendations.
        """
        from sqlalchemy import select
        result = await db.execute(select(CloudCredential).where(CloudCredential.id == credential_id))
        cred = result.scalar_one_or_none()
        if not cred:
            logger.error(f"Credential {credential_id} not found for intelligence scan")
            return

        try:
            raw_creds = decrypt_credentials(cred.encrypted_data)
            provider = cred.provider
            tenant_id = cred.tenant_id

            # 1. Fetch Data
            costs = []
            findings = []
            recommendations = []

            if provider == "aws":
                costs = get_aws_costs(raw_creds)
                findings = get_aws_security_findings(raw_creds)
                recommendations = get_aws_recommendations(raw_creds)
            elif provider == "azure":
                costs = get_azure_costs(raw_creds)
                findings = get_azure_security_findings(raw_creds)
                recommendations = get_azure_recommendations(raw_creds)
            elif provider == "gcp":
                costs = get_gcp_costs(raw_creds)
                findings = get_gcp_security_findings(raw_creds)
                recommendations = get_gcp_recommendations(raw_creds)

            # 2. Persist Data
            await IntelligenceEngine._persist_costs(db, tenant_id, provider, costs)
            await IntelligenceEngine._persist_findings(db, tenant_id, provider, findings)
            await IntelligenceEngine._persist_recommendations(db, tenant_id, recommendations)

            await db.commit()
            
            # 3. Run AI Anomaly Detection
            logger.info(f"Running Anomaly Detection for Tenant {tenant_id}")
            await AnomalyDetectionEngine.detect_cost_anomalies(db, tenant_id)
            await AnomalyDetectionEngine.detect_security_anomalies(db, tenant_id)
            
            logger.info(f"Intelligence scan complete for {provider} (Cred: {credential_id})")

        except Exception as e:
            logger.error(f"Intelligence scan failed for Cred {credential_id}: {e}")
            await db.rollback()

    @staticmethod
    async def _persist_costs(db: AsyncSession, tenant_id: int, provider: str, costs: List[Dict]):
        if not costs: return
        
        # In a real system, we would handle updates/duplicates. 
        # For this version, we'll add new records.
        for c in costs:
            record = CostRecord(
                tenant_id=tenant_id,
                resource_id=c.get("resource_id", "provider_total"),
                service=c.get("service", "other"),
                amount=c.get("amount", 0.0),
                currency=c.get("currency", "USD"),
                date=datetime.fromisoformat(c["date"]) if isinstance(c["date"], str) else c["date"],
                provider=provider
            )
            db.add(record)

    @staticmethod
    async def _persist_findings(db: AsyncSession, tenant_id: int, provider: str, findings: List[Dict]):
        if not findings: return
        
        # Clear old findings for this tenant/provider to keep it fresh
        # await db.execute(delete(SecurityFinding).where(SecurityFinding.tenant_id == tenant_id))
        
        for f in findings:
            finding = SecurityFinding(
                tenant_id=tenant_id,
                resource_id=f["resource_id"],
                finding_type=f["finding_type"],
                severity=f["severity"],
                description=f["description"],
                remediation=f.get("remediation"),
                status="open"
            )
            db.add(finding)

    @staticmethod
    async def _persist_recommendations(db: AsyncSession, tenant_id: int, recommendations: List[Dict]):
        if not recommendations: return
        
        for r in recommendations:
            rec = CostRecommendation(
                tenant_id=tenant_id,
                resource_id=r["resource_id"],
                recommendation_type=r["recommendation_type"],
                description=r["description"],
                potential_savings=r["potential_savings"],
                status="pending"
            )
            db.add(rec)
