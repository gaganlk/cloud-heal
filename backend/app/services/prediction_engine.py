"""
Failure prediction engine — Block 2 fix.

FIXES applied (Blocker #7 — fake metric history):
  - Removed import random, random.gauss(), random.uniform() entirely
  - generate_metric_history() replaced with get_real_metric_history() which queries
    actual MetricHistory rows from PostgreSQL
  - predict_failure() accepts real history dicts from the DB
  - batch_predict() remains unchanged (no random calls)
  - Heuristic prediction (linear regression) remains as-is — it's not fake,
    it's the actual algorithm. The ONLY fake part was the INPUT DATA.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MetricHistory, CloudResource

logger = logging.getLogger(__name__)

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


# ── Pure-Python helpers (used when numpy absent) ──────────────────────────────

def _mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


def _polyfit1(x, y):
    """Simple linear regression — returns (slope, intercept)."""
    n = len(x)
    if n < 2:
        return 0.0, _mean(y)
    sx = sum(x)
    sy = sum(y)
    sxy = sum(xi * yi for xi, yi in zip(x, y))
    sxx = sum(xi * xi for xi in x)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0, _mean(y)
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _clip(val, lo=0.0, hi=100.0):
    return max(lo, min(hi, val))


# ── Real metric history query ─────────────────────────────────────────────────

async def get_real_metric_history(
    db: AsyncSession,
    resource_db_id: int,
    hours: int = 24,
) -> List[Dict]:
    """
    Fetch real MetricHistory rows from PostgreSQL for a given resource.
    Returns list of [{timestamp, cpu, memory, network}] dicts.
    Falls back to an empty list if no data exists yet.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(MetricHistory)
        .where(
            MetricHistory.resource_id == resource_db_id,
            MetricHistory.timestamp >= cutoff,
        )
        .order_by(MetricHistory.timestamp.asc())
    )
    rows = result.scalars().all()

    if not rows:
        logger.debug(
            f"No MetricHistory for resource_db_id={resource_db_id} "
            f"in the past {hours}h — prediction will use current values only"
        )
        return []

    # Group by timestamp — each timestamp may have cpu/memory/network rows
    ts_map: Dict[str, Dict] = {}
    for row in rows:
        key = row.timestamp.isoformat()
        if key not in ts_map:
            ts_map[key] = {"timestamp": key, "cpu": 0.0, "memory": 0.0, "network": 0.0}
        ts_map[key][row.metric_type] = row.value

    return list(ts_map.values())


async def get_resource_db_id(db: AsyncSession, resource_id: str) -> Optional[int]:
    """Look up the integer PK of a CloudResource by its cloud resource_id string."""
    result = await db.execute(
        select(CloudResource.id).where(CloudResource.resource_id == resource_id)
    )
    return result.scalar_one_or_none()


# ── Prediction logic (unchanged — correct linear regression) ──────────────────

def predict_failure(resource: Dict, history: List[Dict] = None) -> Dict[str, Any]:
    """
    Predict future resource utilisation using linear regression.
    Returns risk level, trend, alert flag and chart series data.

    history: list of {timestamp, cpu, memory} dicts from get_real_metric_history().
             If empty or None, uses current values only (no trend).
    """
    current_cpu = resource.get("cpu_usage", 50.0)
    current_memory = resource.get("memory_usage", 50.0)
    resource_id = resource.get("resource_id", "unknown")
    name = resource.get("name", "unknown")

    if not history:
        # No history available — base prediction on current snapshot only
        history = [
            {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "cpu": current_cpu,
                "memory": current_memory,
                "network": resource.get("network_usage", 0.0),
            }
        ]

    cpu_values = [h["cpu"] for h in history]
    mem_values = [h["memory"] for h in history]
    x = list(range(len(cpu_values)))

    if _HAS_NUMPY:
        import numpy as np
        cpu_coef = np.polyfit(x, cpu_values, 1) if len(x) >= 2 else [0.0, cpu_values[0]]
        mem_coef = np.polyfit(x, mem_values, 1) if len(x) >= 2 else [0.0, mem_values[0]]
        fut_x = list(range(len(cpu_values), len(cpu_values) + 6))
        pred_cpu_series = [float(np.clip(np.polyval(cpu_coef, xi), 0, 100)) for xi in fut_x]
        pred_mem_series = [float(np.clip(np.polyval(mem_coef, xi), 0, 100)) for xi in fut_x]
        slope = float(cpu_coef[0])
    else:
        cpu_slope, cpu_int = _polyfit1(x, cpu_values)
        mem_slope, mem_int = _polyfit1(x, mem_values)
        fut_x = list(range(len(cpu_values), len(cpu_values) + 6))
        pred_cpu_series = [_clip(cpu_slope * xi + cpu_int) for xi in fut_x]
        pred_mem_series = [_clip(mem_slope * xi + mem_int) for xi in fut_x]
        slope = cpu_slope

    predicted_cpu = pred_cpu_series[-1]
    predicted_memory = pred_mem_series[-1]

    if slope > 1.2:
        trend = "rapidly_increasing"
    elif slope > 0.3:
        trend = "increasing"
    elif slope < -0.3:
        trend = "decreasing"
    else:
        trend = "stable"

    risk_score = _calculate_risk_score(current_cpu, current_memory, predicted_cpu, trend)

    if risk_score >= 80:
        risk_level = "critical"
    elif risk_score >= 60:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    alert = risk_score >= 60

    # Chart data — last 12 actual + 6 predicted
    chart_data = []
    for h in history[-12:]:
        ts = h["timestamp"]
        chart_data.append({
            "time": ts[11:16] if len(ts) >= 16 else ts,
            "cpu_actual": round(h["cpu"], 2),
            "memory_actual": round(h["memory"], 2),
            "cpu_predicted": None,
            "memory_predicted": None,
        })
    for i in range(6):
        chart_data.append({
            "time": f"+{i + 1}h",
            "cpu_actual": None,
            "memory_actual": None,
            "cpu_predicted": round(pred_cpu_series[i], 2),
            "memory_predicted": round(pred_mem_series[i], 2),
        })

    return {
        "resource_id": resource_id,
        "resource_name": name,
        "resource_type": resource.get("resource_type", "unknown"),
        "provider": resource.get("provider", "unknown"),
        "current_cpu": round(current_cpu, 2),
        "current_memory": round(current_memory, 2),
        "predicted_cpu": round(predicted_cpu, 2),
        "predicted_memory": round(predicted_memory, 2),
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level,
        "trend": trend,
        "alert": alert,
        "chart_data": chart_data,
        "history_points": len(history),
        "metric_history": history[-12:],
    }


def _calculate_risk_score(cpu: float, memory: float, pred_cpu: float, trend: str) -> float:
    score = (cpu / 100) * 20 + (memory / 100) * 20 + (pred_cpu / 100) * 40
    trend_bonus = {
        "rapidly_increasing": 20,
        "increasing": 12,
        "stable": 5,
        "decreasing": 0,
    }
    score += trend_bonus.get(trend, 5)
    return min(100.0, score)


def batch_predict(resources: List[Dict]) -> List[Dict]:
    """Run predictions for a list of resources (no history — uses current values only)."""
    predictions = [predict_failure(r, history=None) for r in resources]
    return sorted(predictions, key=lambda x: x["risk_score"], reverse=True)
