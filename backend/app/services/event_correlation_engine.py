"""
Event Correlation Engine — Elevates isolated alerts to actionable Incidents.

Runs as a background task (every 5 minutes).
Evaluates CORRELATION_RULES against open SecurityFindings, CostAnomalies, and DriftHistory.
When a rule fires: creates an Incident with full timeline and broadcasts via WebSocket.

Deduplication: hash(frozenset(correlated_event_ids)) — prevents duplicate incidents.
"""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SecurityFinding, CostAnomaly, DriftHistory, Incident

logger = logging.getLogger(__name__)

CORRELATION_WINDOW_MINUTES = 60  # Look back 60 minutes for event clustering
CORRELATION_INTERVAL_S = 300     # Run every 5 minutes


# ── Correlation Rules ──────────────────────────────────────────────────────────

CORRELATION_RULES = [
    {
        "name": "Exposed Resource + IAM Escalation",
        "severity": "critical",
        "title": "Active Exploitation Path: Network Exposure + IAM Privilege Escalation Detected",
        "conditions": {
            "security_findings": ["Open SSH Port", "Open RDP Port", "Open Telnet Port"],
            "drift_fields": ["iam_policy"],
        },
        "logic": "ANY_security AND ANY_drift",
    },
    {
        "name": "Cost Spike + Public Storage",
        "severity": "high",
        "title": "Suspected Data Exfiltration: Cost Spike Correlated with Public Storage Exposure",
        "conditions": {
            "cost_anomalies": ["spike"],
            "security_findings": ["Public S3 Bucket", "Public GCS Bucket", "Public Blob Access Enabled"],
        },
        "logic": "ANY_cost AND ANY_security",
    },
    {
        "name": "SG Rule Drift + IAM Drift",
        "severity": "critical",
        "title": "Multi-Vector Configuration Drift: Network + Identity Controls Modified",
        "conditions": {
            "drift_fields": ["sg_rules", "bucket_policy"],
            "drift_fields_2": ["iam_policy"],
        },
        "logic": "ANY_drift AND ANY_drift_2",
    },
    {
        "name": "Sustained Cost Growth + Encryption Missing",
        "severity": "high",
        "title": "Compliance Risk: Sustained Cost Growth with Unencrypted Resources",
        "conditions": {
            "cost_anomalies": ["sustained_growth"],
            "security_findings": ["Unencrypted EBS Volume"],
        },
        "logic": "ANY_cost AND ANY_security",
    },
]


class EventCorrelationEngine:

    @staticmethod
    async def run_correlation_pass(
        db: AsyncSession,
        tenant_id: int,
        broadcast_fn=None,
    ) -> List[Incident]:
        """
        Evaluate all correlation rules against the last 60 minutes of events.
        Returns list of newly created Incident objects.
        """
        created_incidents: List[Incident] = []
        cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=CORRELATION_WINDOW_MINUTES)

        try:
            # Load recent signals
            sf_result = await db.execute(
                select(SecurityFinding)
                .where(SecurityFinding.tenant_id == tenant_id)
                .where(SecurityFinding.status == "open")
                .where(SecurityFinding.created_at >= cutoff)
            )
            open_findings = sf_result.scalars().all()

            ca_result = await db.execute(
                select(CostAnomaly)
                .where(CostAnomaly.tenant_id == tenant_id)
                .where(CostAnomaly.status == "open")
                .where(CostAnomaly.detected_at >= cutoff)
            )
            cost_anomalies = ca_result.scalars().all()

            dh_result = await db.execute(
                select(DriftHistory)
                .where(DriftHistory.detected_at >= cutoff)
            )
            drift_events = dh_result.scalars().all()

            for rule in CORRELATION_RULES:
                incident = await EventCorrelationEngine._evaluate_rule(
                    db, tenant_id, rule, open_findings, cost_anomalies, drift_events
                )
                if incident:
                    created_incidents.append(incident)
                    if broadcast_fn:
                        await broadcast_fn({
                            "type": "incident_created",
                            "data": {
                                "id": incident.id,
                                "title": incident.title,
                                "severity": incident.severity,
                                "rule_matched": incident.rule_matched,
                                "affected_resources": incident.affected_resources,
                            }
                        })

            if created_incidents:
                await db.commit()
                logger.info(f"[Correlation] Created {len(created_incidents)} incident(s) for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"[Correlation] Pass failed: {e}")
            await db.rollback()

        return created_incidents

    @staticmethod
    async def _evaluate_rule(
        db: AsyncSession,
        tenant_id: int,
        rule: Dict,
        findings: List,
        anomalies: List,
        drifts: List,
    ) -> Optional[Incident]:
        """Evaluate a single correlation rule. Returns Incident if matched, else None."""
        conditions = rule.get("conditions", {})
        logic = rule.get("logic", "")

        # --- Collect matching events ---
        matched_findings = [
            f for f in findings
            if f.finding_type in conditions.get("security_findings", [])
        ]
        matched_anomalies = [
            a for a in anomalies
            if a.anomaly_type in conditions.get("cost_anomalies", [])
        ]
        matched_drifts = [
            d for d in drifts
            if d.field in conditions.get("drift_fields", [])
        ]
        matched_drifts2 = [
            d for d in drifts
            if d.field in conditions.get("drift_fields_2", [])
        ]

        # --- Evaluate logic expression ---
        has_security = bool(matched_findings)
        has_cost = bool(matched_anomalies)
        has_drift = bool(matched_drifts)
        has_drift2 = bool(matched_drifts2)

        fired = False
        if logic == "ANY_security AND ANY_drift":
            fired = has_security and has_drift
        elif logic == "ANY_cost AND ANY_security":
            fired = has_cost and has_security
        elif logic == "ANY_drift AND ANY_drift_2":
            fired = has_drift and has_drift2
        else:
            fired = has_security or has_cost or has_drift

        if not fired:
            return None

        # --- Build correlated event IDs ---
        event_ids = {
            "security_findings": [f.id for f in matched_findings],
            "cost_anomalies": [a.id for a in matched_anomalies],
            "drift_events": [d.id for d in matched_drifts + matched_drifts2],
        }
        dedup_key = hashlib.sha256(
            json.dumps(event_ids, sort_keys=True).encode()
        ).hexdigest()

        # --- Deduplication: skip if this exact incident already exists ---
        existing = await db.execute(
            select(Incident)
            .where(Incident.tenant_id == tenant_id)
            .where(Incident.rule_matched == rule["name"])
            .where(Incident.status == "open")
        )
        if existing.scalar_one_or_none():
            return None  # Already have an open incident for this rule

        # --- Collect affected resources ---
        affected = list({
            *[f.resource_id for f in matched_findings],
            *[a.resource_id for a in matched_anomalies],
            *[d.resource_id for d in matched_drifts + matched_drifts2],
        })

        # --- Build timeline ---
        all_events = []
        for f in matched_findings:
            all_events.append({
                "ts": f.created_at.isoformat(),
                "event_type": "security_finding",
                "description": f"{f.finding_type} on {f.resource_id}",
                "severity": f.severity,
            })
        for a in matched_anomalies:
            all_events.append({
                "ts": a.detected_at.isoformat(),
                "event_type": "cost_anomaly",
                "description": f"Cost {a.anomaly_type}: {a.service} +{a.deviation_pct:.1f}%",
                "severity": "high",
            })
        for d in matched_drifts + matched_drifts2:
            all_events.append({
                "ts": d.detected_at.isoformat(),
                "event_type": "config_drift",
                "description": f"Drift detected on {d.resource_id}: field '{d.field}'",
                "severity": "warning",
            })
        all_events.sort(key=lambda x: x["ts"])

        incident = Incident(
            tenant_id=tenant_id,
            title=rule["title"],
            severity=rule["severity"],
            source_types=list(event_ids.keys()),
            correlated_event_ids=event_ids,
            affected_resources=affected,
            timeline=all_events,
            rule_matched=rule["name"],
            status="open",
        )
        db.add(incident)
        await db.flush()
        logger.warning(
            f"[Correlation] INCIDENT CREATED: '{rule['name']}' — "
            f"severity={rule['severity']}, resources={affected}"
        )
        return incident

    @staticmethod
    async def correlation_loop(db_factory, tenant_id: int, broadcast_fn=None):
        """Background task: run correlation pass every 5 minutes."""
        logger.info(f"[Correlation] Background loop started for tenant {tenant_id}")
        while True:
            await asyncio.sleep(CORRELATION_INTERVAL_S)
            try:
                async with db_factory() as db:
                    await EventCorrelationEngine.run_correlation_pass(db, tenant_id, broadcast_fn)
            except Exception as e:
                logger.error(f"[Correlation] Loop iteration failed: {e}")
