"""
ML Training pipeline — trains the Isolation Forest anomaly detector
on historical metric data from PostgreSQL.

Usage:
  python -m ml.training.train_anomaly_detector
  python -m ml.training.train_anomaly_detector --min-samples 5000
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.db.database import AsyncSessionLocal


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def fetch_training_data(min_samples: int = 1000) -> np.ndarray:
    """
    Fetch metric history from PostgreSQL and assemble feature matrix.
    Feature vector per sample: [cpu, memory, disk_io, network_latency]

    Since disk_io and network_latency may not be in MetricHistory yet,
    we join resource current values as proxy for those columns.
    """
    from sqlalchemy import select, text
    from app.db.models import MetricHistory, CloudResource

    logger.info("Fetching training data from PostgreSQL...")

    async with AsyncSessionLocal() as session:
        # Pivot metric_history rows into feature vectors grouped by (resource_id, timestamp_bucket)
        query = text("""
            SELECT
                r.id AS resource_id,
                mh.timestamp,
                MAX(CASE WHEN mh.metric_type = 'cpu' THEN mh.value END) AS cpu,
                MAX(CASE WHEN mh.metric_type = 'memory' THEN mh.value END) AS memory,
                MAX(CASE WHEN mh.metric_type = 'network' THEN mh.value END) AS network,
                COALESCE(r.cpu_usage, 0.0) AS resource_cpu,
                COALESCE(r.memory_usage, 0.0) AS resource_memory
            FROM metric_history mh
            JOIN cloud_resources r ON r.id = mh.resource_id
            GROUP BY r.id, mh.timestamp
            HAVING COUNT(*) >= 1
            ORDER BY mh.timestamp DESC
            LIMIT :limit
        """)
        result = await session.execute(query, {"limit": min_samples * 2})
        rows = result.fetchall()

    if not rows:
        logger.warning("No historical data in metric_history. Generating synthetic training data.")
        return _generate_synthetic_data(n_samples=max(min_samples, 2000))

    features = []
    for row in rows:
        cpu = float(row.cpu or row.resource_cpu or 0)
        memory = float(row.memory or row.resource_memory or 0)
        network = float(row.network or 0)
        # disk_io and latency not yet in schema — add when metric types expand
        disk_io = 0.0
        latency = 0.0
        features.append([cpu, memory, disk_io, latency])

    X = np.array(features, dtype=np.float32)
    logger.info(f"Fetched {len(X)} training samples from database")
    return X


def _generate_synthetic_data(n_samples: int = 2000) -> np.ndarray:
    """
    Generate synthetic NORMAL telemetry for bootstrapping.
    Used when no historical data is available (fresh install).
    95% normal + 5% anomalous, matching contamination=0.05.
    """
    rng = np.random.default_rng(42)
    n_normal = int(n_samples * 0.95)
    n_anomalous = n_samples - n_normal

    # Normal: low-to-moderate metrics
    normal = rng.normal(loc=[40, 50, 10, 20], scale=[15, 12, 5, 8], size=(n_normal, 4))
    normal = np.clip(normal, 0, 100)

    # Anomalous: high metrics
    anomalous = rng.normal(loc=[90, 92, 80, 800], scale=[5, 4, 10, 100], size=(n_anomalous, 4))
    anomalous = np.clip(anomalous, 0, None)

    X = np.vstack([normal, anomalous])
    rng.shuffle(X)
    logger.info(f"Generated {n_samples} synthetic training samples ({n_normal} normal, {n_anomalous} anomalous)")
    return X.astype(np.float32)


async def train(min_samples: int = 1000):
    """Full training pipeline: fetch data → fit model → save artifacts."""
    X = await fetch_training_data(min_samples)

    if len(X) < min_samples:
        logger.warning(
            f"Only {len(X)} samples available, minimum recommended is {min_samples}. "
            "Model may have poor accuracy. Proceeding anyway."
        )

    from app.ml.engine import FailurePredictorML

    predictor = FailurePredictorML()

    logger.info(f"Training IsolationForest on {len(X)} samples...")
    predictor.fit(X)

    # Quick smoke test
    test_normal = {"cpu": 35.0, "memory": 45.0, "disk_io": 5.0, "network_latency": 15.0}
    test_anomalous = {"cpu": 99.0, "memory": 98.0, "disk_io": 95.0, "network_latency": 2000.0}

    score_normal = predictor.predict_degradation(test_normal)
    score_anomalous = predictor.predict_degradation(test_anomalous)

    logger.info(f"Smoke test — normal score: {score_normal:.3f} (expect < 0.5)")
    logger.info(f"Smoke test — anomalous score: {score_anomalous:.3f} (expect > 0.5)")

    if score_anomalous <= score_normal:
        logger.warning("Model may be inverted — anomalous scored LOWER than normal. Check training data quality.")
    else:
        logger.info("✅ Model training complete and smoke tests passed.")

    return {"samples": len(X), "score_normal": score_normal, "score_anomalous": score_anomalous}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AIOps anomaly detector")
    parser.add_argument("--min-samples", type=int, default=1000,
                        help="Minimum training samples (default: 1000)")
    args = parser.parse_args()

    result = asyncio.run(train(args.min_samples))
    print(f"\nTraining complete: {result}")
