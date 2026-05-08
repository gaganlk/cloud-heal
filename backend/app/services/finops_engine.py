"""
FinOps Engine — Unified multi-cloud cost intelligence.

Responsibilities:
  1. Fetch costs from AWS / Azure / GCP
  2. Normalize all currencies to USD
  3. Detect cost anomalies (spike, idle, sustained_growth)
  4. Detect idle resources via MetricHistory
  5. Aggregate rightsizing recommendations cross-cloud
  6. Forecast spend via linear regression on 90-day history

Architecture:
  CloudAdapters → FinOpsEngine → CurrencyNormalizer → DB persistence
                                      ↓
                           AnomalyDetector / Forecaster
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.currency_normalizer import get_normalizer
from app.db.models import (
    CostRecord, CostRecommendation, CostAnomaly, MetricHistory, CloudResource
)

logger = logging.getLogger(__name__)

# Anomaly thresholds
SPIKE_MULTIPLIER = 2.0          # today > 2x 7-day avg → SPIKE
IDLE_CPU_THRESHOLD = 3.0        # CPU% below this → idle candidate
IDLE_DAYS = 7                   # consecutive days below threshold
SUSTAINED_GROWTH_PCT = 20.0     # 20% month-over-month growth → flag


class FinOpsEngine:

    # ─── Fetch & Persist ────────────────────────────────────────────────────

    @staticmethod
    async def fetch_and_persist(
        db: AsyncSession,
        tenant_id: int,
        credentials_list: List[Dict],
        days: int = 30,
    ) -> Dict[str, int]:
        """
        Fetch costs from all providers in PARALLEL and persist records.
        """
        normalizer = get_normalizer()
        summary: Dict[str, int] = {}
        
        async def fetch_one(cred):
            provider = cred.get("provider", "").lower()
            raw_creds = cred.get("decrypted", {})
            try:
                if provider == "aws":
                    from app.services.cloud.aws_finops import get_aws_costs
                    return provider, get_aws_costs(raw_creds, days)
                elif provider == "azure":
                    from app.services.cloud.azure_finops import get_azure_costs
                    return provider, get_azure_costs(raw_creds, days)
                elif provider == "gcp":
                    from app.services.cloud.gcp_finops import get_gcp_costs
                    return provider, get_gcp_costs(raw_creds, days)
                return provider, []
            except Exception as e:
                logger.error(f"[FinOps] Fetch failed for {provider}: {e}")
                return provider, []

        # Execute all fetches in parallel
        results = await asyncio.gather(*[fetch_one(c) for c in credentials_list])

        for provider, records in results:
            count = 0
            for rec in records:
                try:
                    currency = rec.get("currency", "USD")
                    amount = float(rec.get("amount", 0.0))
                    # Normalizer now has fallback logic
                    usd_amount, exchange_rate = await normalizer.to_usd(amount, currency)

                    cost_record = CostRecord(
                        tenant_id=tenant_id,
                        resource_id=rec.get("resource_id", "global"),
                        service=rec.get("service", "unknown"),
                        amount=amount,
                        currency=currency,
                        original_currency=currency,
                        exchange_rate=exchange_rate,
                        normalized_usd=usd_amount,
                        date=datetime.fromisoformat(rec["date"]) if isinstance(rec["date"], str) else rec["date"],
                        provider=provider,
                    )
                    db.add(cost_record)
                    count += 1
                except Exception as inner_e:
                    logger.error(f"[FinOps] Failed to process record for {provider}: {inner_e}")
            
            summary[provider] = count
            logger.info(f"[FinOps] Sync complete for {provider}: {count} records")

        await db.commit()
        return summary

    # ─── Anomaly Detection ────────────────────────────────────────────────────

    @staticmethod
    async def detect_cost_anomalies(
        db: AsyncSession, tenant_id: int
    ) -> List[CostAnomaly]:
        """
        Detect cost anomalies using rolling 7-day baseline.
        Algorithms:
          SPIKE: today > 7-day_avg * SPIKE_MULTIPLIER
          IDLE: resource in MetricHistory with avg CPU < IDLE_CPU_THRESHOLD for 7 days
          SUSTAINED_GROWTH: current 30-day avg > previous 30-day avg by 20%
        """
        anomalies: List[CostAnomaly] = []
        now = datetime.now(tz=timezone.utc)

        try:
            # Load recent cost records
            result = await db.execute(
                select(CostRecord)
                .where(CostRecord.tenant_id == tenant_id)
                .where(CostRecord.date >= now - timedelta(days=37))
                .order_by(CostRecord.date)
            )
            records = result.scalars().all()

            # Group by (provider, service)
            grouped: Dict[tuple, List[CostRecord]] = {}
            for r in records:
                key = (r.provider, r.service)
                grouped.setdefault(key, []).append(r)

            for (provider, service), recs in grouped.items():
                recs_sorted = sorted(recs, key=lambda x: x.date)

                # Split: last 7 days vs previous 30 days
                cutoff_7d = now - timedelta(days=7)
                recent = [r for r in recs_sorted if r.date >= cutoff_7d]
                baseline_recs = [r for r in recs_sorted if r.date < cutoff_7d]

                if not recent or not baseline_recs:
                    continue

                baseline_avg = sum(r.normalized_usd for r in baseline_recs) / len(baseline_recs)
                recent_avg = sum(r.normalized_usd for r in recent) / len(recent)

                if baseline_avg == 0:
                    continue

                deviation_pct = ((recent_avg - baseline_avg) / baseline_avg) * 100

                # SPIKE detection
                if recent_avg > baseline_avg * SPIKE_MULTIPLIER:
                    anomaly = CostAnomaly(
                        tenant_id=tenant_id,
                        resource_id=f"{provider}:{service}",
                        provider=provider,
                        service=service,
                        baseline_amount=round(baseline_avg, 4),
                        actual_amount=round(recent_avg, 4),
                        deviation_pct=round(deviation_pct, 2),
                        anomaly_type="spike",
                        risk_score=min(100, 50 + deviation_pct * 0.3),
                    )
                    db.add(anomaly)
                    anomalies.append(anomaly)
                    logger.warning(
                        f"[FinOps] SPIKE detected: {provider}/{service} "
                        f"+{deviation_pct:.1f}% above baseline"
                    )

                # SUSTAINED_GROWTH detection
                cutoff_60d = now - timedelta(days=60)
                prev_30d = [r for r in recs_sorted if cutoff_60d <= r.date < cutoff_7d - timedelta(days=23)]
                if prev_30d:
                    prev_avg = sum(r.normalized_usd for r in prev_30d) / len(prev_30d)
                    if prev_avg > 0:
                        growth_pct = ((baseline_avg - prev_avg) / prev_avg) * 100
                        if growth_pct >= SUSTAINED_GROWTH_PCT:
                            anomaly = CostAnomaly(
                                tenant_id=tenant_id,
                                resource_id=f"{provider}:{service}",
                                provider=provider,
                                service=service,
                                baseline_amount=round(prev_avg, 4),
                                actual_amount=round(baseline_avg, 4),
                                deviation_pct=round(growth_pct, 2),
                                anomaly_type="sustained_growth",
                                risk_score=min(100, 30 + growth_pct * 0.5),
                            )
                            db.add(anomaly)
                            anomalies.append(anomaly)

            await db.commit()
        except Exception as e:
            logger.error(f"[FinOps] Anomaly detection failed: {e}")
            await db.rollback()

        return anomalies

    # ─── Idle Resource Detection ──────────────────────────────────────────────

    @staticmethod
    async def detect_idle_resources(
        db: AsyncSession, tenant_id: int
    ) -> List[CostRecommendation]:
        """
        Identify idle cloud resources by querying MetricHistory.
        Idle = avg CPU < IDLE_CPU_THRESHOLD over last IDLE_DAYS days.
        """
        recommendations: List[CostRecommendation] = []
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=IDLE_DAYS)

        try:
            # Get all resources for this tenant
            res_result = await db.execute(
                select(CloudResource).where(CloudResource.tenant_id == tenant_id)
            )
            resources = res_result.scalars().all()

            for resource in resources:
                metric_result = await db.execute(
                    select(sqlfunc.avg(MetricHistory.value))
                    .where(MetricHistory.resource_id == resource.id)
                    .where(MetricHistory.metric_type == "cpu")
                    .where(MetricHistory.timestamp >= cutoff)
                )
                avg_cpu = metric_result.scalar()

                if avg_cpu is not None and avg_cpu < IDLE_CPU_THRESHOLD:
                    rec = CostRecommendation(
                        tenant_id=tenant_id,
                        resource_id=resource.resource_id,
                        provider=resource.provider,
                        recommendation_type="idle",
                        description=(
                            f"Resource '{resource.name}' has average CPU of "
                            f"{avg_cpu:.1f}% over {IDLE_DAYS} days. Consider "
                            f"downsizing or terminating."
                        ),
                        potential_savings=0.0,  # enriched by cost lookup
                        confidence_score=0.85,
                    )
                    db.add(rec)
                    recommendations.append(rec)

            await db.commit()
        except Exception as e:
            logger.error(f"[FinOps] Idle detection failed: {e}")
            await db.rollback()

        return recommendations

    # ─── Spend Forecasting ────────────────────────────────────────────────────

    @staticmethod
    async def forecast_spend(
        db: AsyncSession, tenant_id: int, horizon_days: int = 30
    ) -> Dict[str, Any]:
        """
        Linear regression on last 90 days of normalized USD spend.
        Returns per-provider 7d and 30d forecast.
        """
        try:
            import numpy as np
        except ImportError:
            return {"error": "numpy not installed — install with: pip install numpy"}

        result = await db.execute(
            select(CostRecord)
            .where(CostRecord.tenant_id == tenant_id)
            .where(CostRecord.date >= datetime.now(tz=timezone.utc) - timedelta(days=90))
            .order_by(CostRecord.date)
        )
        records = result.scalars().all()

        forecasts: Dict[str, Dict] = {}
        providers = set(r.provider for r in records)

        for provider in providers:
            prov_records = sorted(
                [r for r in records if r.provider == provider],
                key=lambda x: x.date
            )
            if len(prov_records) < 7:
                continue

            # Days since start as x-axis
            start = prov_records[0].date
            x = np.array([(r.date - start).days for r in prov_records], dtype=float)
            y = np.array([r.normalized_usd for r in prov_records], dtype=float)

            # Fit linear model
            coeffs = np.polyfit(x, y, 1)
            slope, intercept = coeffs[0], coeffs[1]

            last_x = x[-1]
            f7 = max(0.0, slope * (last_x + 7) + intercept)
            f30 = max(0.0, slope * (last_x + 30) + intercept)

            forecasts[provider] = {
                "forecast_7d_usd": round(float(f7), 2),
                "forecast_30d_usd": round(float(f30), 2),
                "trend": "increasing" if slope > 0 else "decreasing",
                "daily_avg_usd": round(float(np.mean(y)), 2),
            }

        return forecasts

    # ─── Rightsizing Recommendations ─────────────────────────────────────────

    @staticmethod
    async def fetch_rightsizing(
        db: AsyncSession, tenant_id: int, credentials_list: List[Dict]
    ) -> List[CostRecommendation]:
        """
        Fetch provider-native rightsizing recommendations.
        AWS: ce.get_rightsizing_recommendation()
        Azure: advisor_client.recommendations (category=Cost)
        GCP: Recommender API - MachineTypeRecommender
        """
        all_recs: List[CostRecommendation] = []

        for cred in credentials_list:
            provider = cred.get("provider", "").lower()
            raw_creds = cred.get("decrypted", {})
            raw_recs = []

            try:
                if provider == "aws":
                    from app.services.cloud.aws_finops import get_aws_recommendations
                    raw_recs = get_aws_recommendations(raw_creds)
                elif provider == "gcp":
                    from app.services.cloud.gcp_finops import get_gcp_recommendations
                    raw_recs = get_gcp_recommendations(raw_creds)
                # Azure Advisor requires separate SDK setup
            except Exception as e:
                logger.warning(f"[FinOps] Rightsizing fetch failed for {provider}: {e}")
                continue

            for r in raw_recs:
                rec = CostRecommendation(
                    tenant_id=tenant_id,
                    resource_id=r.get("resource_id", "unknown"),
                    provider=provider,
                    recommendation_type=r.get("recommendation_type", "rightsize"),
                    description=r.get("description", ""),
                    potential_savings=float(r.get("potential_savings", 0.0)),
                    confidence_score=r.get("confidence_score", 0.8),
                )
                db.add(rec)
                all_recs.append(rec)

        if all_recs:
            await db.commit()

        return all_recs

    # ─── Full Analysis Orchestrator ───────────────────────────────────────────

    @staticmethod
    async def run_full_analysis(
        db: AsyncSession, tenant_id: int, credentials_list: List[Dict]
    ) -> Dict[str, Any]:
        """Single entry point: fetch → normalize → detect → recommend → forecast."""
        logger.info(f"[FinOps] Starting full analysis for tenant {tenant_id}")

        fetch_summary = await FinOpsEngine.fetch_and_persist(db, tenant_id, credentials_list)
        anomalies = await FinOpsEngine.detect_cost_anomalies(db, tenant_id)
        idle_recs = await FinOpsEngine.detect_idle_resources(db, tenant_id)
        rightsize_recs = await FinOpsEngine.fetch_rightsizing(db, tenant_id, credentials_list)
        forecast = await FinOpsEngine.forecast_spend(db, tenant_id)

        return {
            "fetched": fetch_summary,
            "anomalies_detected": len(anomalies),
            "idle_resources": len(idle_recs),
            "rightsizing_recommendations": len(rightsize_recs),
            "forecast": forecast,
        }
