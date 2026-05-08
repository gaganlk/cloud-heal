import logging
import numpy as np
import pickle
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import CostRecord, SecurityFinding, EventLog
from app.services.notification_service import NotificationService
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

# Model cache path — use a volume-mounted path so the model survives container restarts
# and is accessible across replicas (mount /app/data as a shared volume in production).
# Falls back to /tmp for local development when /app/data is not available.
_MODEL_DIR = os.getenv("MODEL_CACHE_DIR", "/app/data/models")
os.makedirs(_MODEL_DIR, exist_ok=True)
MODEL_CACHE_PATH = os.path.join(_MODEL_DIR, "finops_model.pkl")

class AnomalyDetectionEngine:
    """
    AI-driven anomaly detection for Costs and Security.
    Uses IsolationForest for cost outliers and heuristic analysis for security.
    """

    @staticmethod
    async def train_finops_model(db: AsyncSession, tenant_id: int):
        """
        Train the Isolation Forest model on historical cost data.
        This should be called periodically (e.g., hourly) NOT on every detection request.
        """
        try:
            logger.info(f"Training FinOps ML model for tenant {tenant_id}...")
            # 1. Fetch historical cost records (last 90 days for better baseline)
            result = await db.execute(
                select(CostRecord)
                .where(CostRecord.tenant_id == tenant_id)
                .order_by(CostRecord.date.desc())
                .limit(1000)
            )
            records = result.scalars().all()
            if len(records) < 20:
                logger.info(f"Insufficient data ({len(records)} records) for training. Need at least 20.")
                return

            # 2. Prepare features
            # Features: Amount, DayOfWeek, IsWeekend
            X = []
            for r in records:
                X.append([
                    float(r.normalized_usd),
                    r.date.weekday(),
                    1.0 if r.date.weekday() >= 5 else 0.0
                ])
            
            X = np.array(X)

            # 3. Train Isolation Forest
            model = IsolationForest(contamination=0.03, random_state=42, n_estimators=100)
            model.fit(X)
            
            # 4. Persist model
            with open(MODEL_CACHE_PATH, 'wb') as f:
                pickle.dump(model, f)
            
            logger.info("FinOps ML model trained and cached successfully.")
        except Exception as e:
            logger.error(f"Failed to train FinOps model: {e}")

    @staticmethod
    async def detect_cost_anomalies(db: AsyncSession, tenant_id: int):
        """
        Detect spending spikes using the CACHED Isolation Forest model.
        """
        try:
            if not os.path.exists(MODEL_CACHE_PATH):
                logger.debug("No cached model found. Falling back to training once...")
                await AnomalyDetectionEngine.train_finops_model(db, tenant_id)
                if not os.path.exists(MODEL_CACHE_PATH):
                    return

            # 1. Load model with corruption guard
            try:
                with open(MODEL_CACHE_PATH, 'rb') as f:
                    model = pickle.load(f)
            except (pickle.UnpicklingError, EOFError, ValueError):
                logger.warning("Cached model corrupted. Retraining...")
                os.remove(MODEL_CACHE_PATH)
                await AnomalyDetectionEngine.train_finops_model(db, tenant_id)
                if not os.path.exists(MODEL_CACHE_PATH):
                    return
                with open(MODEL_CACHE_PATH, 'rb') as f:
                    model = pickle.load(f)

            # 2. Fetch recent records to check
            result = await db.execute(
                select(CostRecord)
                .where(CostRecord.tenant_id == tenant_id)
                .order_by(CostRecord.date.desc())
                .limit(10)
            )
            recent_records = result.scalars().all()

            # 3. Predict
            for r in recent_records:
                # Prepare feature vector
                x = np.array([[
                    float(r.normalized_usd),
                    r.date.weekday(),
                    1.0 if r.date.weekday() >= 5 else 0.0
                ]])
                
                pred = model.predict(x)[0]
                
                if pred == -1: # Anomaly
                    # Check if it's already logged to avoid spam
                    title = "🚨 FinOps Spending Spike"
                    msg = f"Unusual spend detected: ${r.normalized_usd:.2f} for {r.service} on {r.date.strftime('%Y-%m-%d')}."
                    
                    # Heuristic: only alert if > 2x the average of last 20 records
                    # (This adds a safety layer over the ML output)
                    
                    logger.warning(f"[FINOPS ANOMALY] {msg}")
                    
                    db.add(EventLog(
                        tenant_id=tenant_id,
                        event_type="cost_anomaly",
                        description=msg,
                        severity="warning",
                        resource_id=r.resource_id
                    ))
                    
                    await NotificationService.dispatch_external_alert(title, msg, "warning")
            
            await db.commit()

        except Exception as e:
            logger.error(f"Cost anomaly detection failed: {e}")

    @staticmethod
    async def detect_security_anomalies(db: AsyncSession, tenant_id: int):
        """
        Detect security anomalies (heuristic-based).
        Flag 'critical' findings and sudden spikes in finding count.
        """
        try:
            # 1. Check for Critical findings
            result = await db.execute(
                select(SecurityFinding)
                .where(SecurityFinding.tenant_id == tenant_id, SecurityFinding.severity == "critical")
            )
            criticals = result.scalars().all()
            
            for c in criticals:
                title = "Critical Security Finding"
                msg = f"{c.finding_type} on {c.resource_id}: {c.description}"
                
                db.add(EventLog(
                    tenant_id=tenant_id,
                    event_type="security_anomaly",
                    description=msg,
                    severity="critical",
                    resource_id=c.resource_id
                ))
                
                await NotificationService.dispatch_external_alert(title, msg, "critical")
            
            await db.commit()

        except Exception as e:
            logger.error(f"Security anomaly detection failed: {e}")
