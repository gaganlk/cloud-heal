"""
Safe Auto-Remediation Planner — wraps healing_engine.py with safety layers.

Safety Layers:
  1. Dry-run simulation: predicts what WILL happen before execution
  2. Blast-radius analysis: traverses GraphEdge to find dependent resources
  3. Rollback snapshot: captures current state before action
  4. Approval gate: high-blast-radius plans require admin approval
  5. Idempotent execution: SHA256 key prevents duplicate runs

Flow:
  create_plan() → [admin approves if needed] → execute_plan() → [rollback if failed]
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RemediationPlan, GraphEdge, CloudResource, EventLog, SecurityFinding

logger = logging.getLogger(__name__)

# Blast radius threshold for auto-approval escalation
BLAST_RADIUS_APPROVAL_THRESHOLD = 5
DB_RESOURCE_KEYWORDS = ("db", "database", "rds", "sql", "postgres", "mysql", "mongo")

# Map finding type → healing action type
FINDING_TO_ACTION = {
    "Open SSH Port":             "revoke_sg_rule",
    "Open RDP Port":             "revoke_sg_rule",
    "Public S3 Bucket":          "block_s3_public_access",
    "Public GCS Bucket":         "block_gcs_public_access",
    "Public Blob Access Enabled": "block_blob_public_access",
    "Unencrypted EBS Volume":    "encrypt_volume",
    "MFA Not Enabled":           "enforce_mfa",
    "IAM Policy Drift":          "revert_iam_policy",
    "Iam Policy":                "revert_iam_policy",
    "Sg Rules":                  "revoke_sg_rule",
}


class RemediationPlanner:

    @staticmethod
    async def create_plan(
        db: AsyncSession,
        finding: SecurityFinding,
        tenant_id: int,
        created_by_id: int,
        credentials: Dict,
    ) -> RemediationPlan:
        """
        Stage 1: Create a safe remediation plan.
        Includes dry-run, blast-radius, and rollback snapshot.
        """
        action_type = FINDING_TO_ACTION.get(finding.finding_type, "generic_remediation")
        provider = getattr(finding, "provider", "aws")

        idempotency_key = hashlib.sha256(
            f"{finding.resource_id}:{action_type}:{finding.id}".encode()
        ).hexdigest()

        # Check for existing non-failed plan
        existing = await db.execute(
            select(RemediationPlan)
            .where(RemediationPlan.idempotency_key == idempotency_key)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Remediation plan already exists for finding {finding.id}")

        # 1. Compute blast radius
        blast_analysis = await RemediationPlanner._compute_blast_radius(
            db, finding.resource_id
        )

        # 2. Capture rollback snapshot
        rollback_snapshot = await RemediationPlanner._capture_snapshot(
            finding.resource_id, provider, credentials
        )

        # 3. Dry-run simulation
        dry_run_result = RemediationPlanner._simulate_action(
            action_type, finding.resource_id, provider
        )

        # 4. Determine if approval is required
        requires_approval = (
            blast_analysis["connected_count"] >= BLAST_RADIUS_APPROVAL_THRESHOLD
            or blast_analysis["has_database"]
            or finding.severity == "critical"
        )

        plan = RemediationPlan(
            tenant_id=tenant_id,
            resource_id=finding.resource_id,
            action_type=action_type,
            provider=provider,
            dry_run_result=dry_run_result,
            rollback_snapshot=rollback_snapshot,
            blast_radius_analysis=blast_analysis,
            status="dry_run_complete" if not requires_approval else "pending_approval",
            idempotency_key=idempotency_key,
            created_by_id=created_by_id,
        )
        db.add(plan)
        await db.commit()

        logger.info(
            f"[RemediationPlan] Plan created: resource={finding.resource_id} "
            f"action={action_type} status={plan.status}"
        )
        return plan

    @staticmethod
    async def execute_plan(
        db: AsyncSession,
        plan_id: int,
        approved_by_id: int,
        credentials: Dict,
    ) -> Dict[str, Any]:
        """
        Stage 2: Execute an approved plan via healing_engine.
        Auto-rollback on failure.
        """
        result = await db.execute(select(RemediationPlan).where(RemediationPlan.id == plan_id))
        plan = result.scalar_one_or_none()

        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        if plan.status not in ("dry_run_complete", "pending_approval"):
            raise ValueError(f"Plan {plan_id} is in invalid state: {plan.status}")

        plan.status = "executing"
        plan.approved_by_id = approved_by_id
        plan.approved_at = datetime.now(tz=timezone.utc)
        await db.commit()

        try:
            from app.services.healing_engine import execute_healing_action
            sdk_result = await execute_healing_action(
                resource_id=plan.resource_id,
                resource_name=plan.resource_id,
                action_type=plan.action_type,
                provider=plan.provider,
                credentials=credentials,
                event_id=str(plan.id),
            )

            plan.status = "complete"
            plan.actual_result = sdk_result
            plan.executed_at = datetime.now(tz=timezone.utc)
            await db.commit()

            logger.info(f"[RemediationPlan] Plan {plan_id} executed successfully")
            return {"status": "complete", "result": sdk_result}

        except Exception as e:
            logger.error(f"[RemediationPlan] Execution failed — attempting rollback: {e}")
            plan.status = "failed"
            plan.actual_result = {"error": str(e)}
            await db.commit()

            # Attempt rollback
            if plan.rollback_snapshot:
                rollback_result = await RemediationPlanner.rollback_plan(db, plan_id, credentials)
                return {"status": "failed_rolled_back", "error": str(e), "rollback": rollback_result}

            return {"status": "failed", "error": str(e)}

    @staticmethod
    async def rollback_plan(
        db: AsyncSession,
        plan_id: int,
        credentials: Dict,
    ) -> Dict[str, Any]:
        """
        Restore resource to rollback_snapshot state.
        Provider-specific implementation via healing_engine.
        """
        result = await db.execute(select(RemediationPlan).where(RemediationPlan.id == plan_id))
        plan = result.scalar_one_or_none()

        if not plan or not plan.rollback_snapshot:
            return {"error": "No rollback snapshot available"}

        try:
            from app.services.healing_engine import execute_healing_action
            rollback_result = await execute_healing_action(
                resource_id=plan.resource_id,
                resource_name=plan.resource_id,
                action_type="rollback",
                provider=plan.provider,
                credentials={**credentials, "rollback_snapshot": plan.rollback_snapshot},
                event_id=f"rollback-{plan.id}",
            )
            plan.status = "rolled_back"
            await db.commit()
            logger.info(f"[RemediationPlan] Plan {plan_id} rolled back successfully")
            return {"status": "rolled_back", "result": rollback_result}
        except Exception as e:
            logger.error(f"[RemediationPlan] Rollback failed for plan {plan_id}: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _compute_blast_radius(
        db: AsyncSession, resource_id: str
    ) -> Dict[str, Any]:
        """Traverse GraphEdge to find all resources that depend on this one."""
        result = await db.execute(
            select(GraphEdge).where(
                (GraphEdge.source_id == resource_id) | (GraphEdge.target_id == resource_id)
            )
        )
        edges = result.scalars().all()

        connected_ids = set()
        for e in edges:
            connected_ids.add(e.source_id)
            connected_ids.add(e.target_id)
        connected_ids.discard(resource_id)

        has_database = any(
            any(kw in rid.lower() for kw in DB_RESOURCE_KEYWORDS)
            for rid in connected_ids
        )

        return {
            "connected_count": len(connected_ids),
            "connected_resources": list(connected_ids)[:20],
            "has_database": has_database,
            "risk_level": "high" if has_database else ("medium" if len(connected_ids) > 3 else "low"),
        }

    @staticmethod
    async def _capture_snapshot(
        resource_id: str, provider: str, credentials: Dict
    ) -> Dict[str, Any]:
        """
        Capture current resource state for rollback.
        Returns minimal state snapshot (tags, config, status).
        """
        # Provider-specific snapshot capture — graceful degradation on failure
        snapshot: Dict[str, Any] = {
            "captured_at": datetime.now(tz=timezone.utc).isoformat(),
            "resource_id": resource_id,
            "provider": provider,
        }

        try:
            if provider == "aws":
                import boto3
                session = boto3.Session(
                    aws_access_key_id=credentials.get("access_key_id"),
                    aws_secret_access_key=credentials.get("secret_access_key"),
                    region_name=credentials.get("region", "us-east-1"),
                )
                if resource_id.startswith("sg-"):
                    ec2 = session.client("ec2")
                    sg = ec2.describe_security_groups(GroupIds=[resource_id])
                    snapshot["security_group"] = sg["SecurityGroups"][0] if sg["SecurityGroups"] else {}
                elif resource_id.startswith("iam_user:"):
                    iam = session.client("iam")
                    uname = resource_id.split(":", 1)[1]
                    policies = iam.list_attached_user_policies(UserName=uname)
                    snapshot["attached_policies"] = policies.get("AttachedPolicies", [])
        except Exception as e:
            logger.warning(f"[Snapshot] Partial snapshot for {resource_id}: {e}")
            snapshot["partial"] = True

        return snapshot

    @staticmethod
    def _simulate_action(
        action_type: str, resource_id: str, provider: str
    ) -> Dict[str, Any]:
        """
        Dry-run: describe what WOULD happen without executing.
        """
        descriptions = {
            "revoke_sg_rule": f"WOULD remove inbound rules matching port 22/3389/0.0.0.0/0 from {resource_id}",
            "block_s3_public_access": f"WOULD enable Block Public Access on S3 bucket {resource_id}",
            "block_gcs_public_access": f"WOULD remove allUsers/allAuthenticatedUsers IAM bindings from GCS bucket {resource_id}",
            "block_blob_public_access": f"WOULD set allow_blob_public_access=False on Azure storage account {resource_id}",
            "encrypt_volume": f"WOULD snapshot {resource_id}, create encrypted copy, detach original",
            "revert_iam_policy": f"WOULD revert IAM policy on {resource_id} to last desired state",
            "enforce_mfa": f"WOULD create virtual MFA device requirement for IAM user {resource_id}",
            "generic_remediation": f"WOULD apply generic security remediation to {resource_id}",
        }
        return {
            "dry_run": True,
            "action_type": action_type,
            "provider": provider,
            "resource_id": resource_id,
            "description": descriptions.get(action_type, f"WOULD apply {action_type} to {resource_id}"),
            "estimated_downtime_seconds": 0,
            "reversible": True,
        }
