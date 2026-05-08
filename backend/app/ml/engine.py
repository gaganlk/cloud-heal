"""
Isolation Forest anomaly detector for cloud resource telemetry.
Replaces naive linear regression prediction with proper unsupervised ML.

Key design decisions:
- IsolationForest: works without labeled failure data (unsupervised)
- Contamination=0.05: expects ~5% of telemetry to be anomalous
- Models are persisted with joblib and reloaded on startup
- Thread-safe: predict_degradation uses only read-only model state
- Graceful degradation: falls back to heuristic formula when model not trained
"""
import logging
import os
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Model artifact paths (configurable via env)
# We assume the app is run from the backend directory
_MODEL_DIR = Path("app/ml/models")
MODEL_PATH = _MODEL_DIR / "anomaly_detector.joblib"
SCALER_PATH = _MODEL_DIR / "scaler.joblib"


# Feature order — must match training and inference
FEATURE_NAMES = ["cpu", "memory", "disk_io", "network_latency"]


class FailurePredictorML:
    """
    Isolation Forest-based anomaly detector for cloud resource telemetry.
    Outputs a degradation score in [0.0, 1.0] where 1.0 = highly anomalous.
    """

    def __init__(self):
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self._is_fitted = False
        self._load_or_init()

    def _load_or_init(self):
        """Load persisted model from disk, or initialize with default hyperparameters."""
        if MODEL_PATH.exists() and SCALER_PATH.exists():
            try:
                self.model = joblib.load(MODEL_PATH)
                self.scaler = joblib.load(SCALER_PATH)
                self._is_fitted = True
                logger.info(f"Loaded trained model from {MODEL_PATH}")
                return
            except Exception as e:
                logger.warning(f"Failed to load model from disk: {e}. Re-initializing.")

        # Default hyperparameters — will be fit() before prediction in production
        self.model = IsolationForest(
            n_estimators=100,
            max_samples="auto",
            contamination=0.05,
            max_features=1.0,
            bootstrap=False,
            random_state=42,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()
        self._is_fitted = False
        logger.info("Initialized new untrained IsolationForest model")

    def fit(self, X: np.ndarray) -> None:
        """
        Train the model on historical telemetry data.
        X: shape (n_samples, 4) — [cpu, memory, disk_io, network_latency]
        """
        if X.shape[0] < 100:
            logger.warning(f"Training dataset has only {X.shape[0]} samples. Recommend ≥1000.")

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self._is_fitted = True

        # Persist model artifacts
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.scaler, SCALER_PATH)
        logger.info(f"Model trained on {X.shape[0]} samples and saved to {_MODEL_DIR}")

    def predict_degradation(self, telemetry: Dict) -> float:
        """
        Returns degradation score in [0.0, 1.0].
        1.0 = highly anomalous (likely failing), 0.0 = normal.

        Falls back to heuristic weighting when model is not trained.
        """
        cpu = float(telemetry.get("cpu", 0.0))
        memory = float(telemetry.get("memory", 0.0))
        disk_io = float(telemetry.get("disk_io", 0.0))
        latency = float(telemetry.get("network_latency", 0.0))

        if not self._is_fitted:
            # Heuristic fallback: weighted combination of metrics
            score = (cpu / 100.0) * 0.45 + (memory / 100.0) * 0.35 + \
                    (min(disk_io, 100.0) / 100.0) * 0.10 + \
                    (min(latency, 1000.0) / 1000.0) * 0.10
            return float(np.clip(score, 0.0, 1.0))

        features = np.array([[cpu, memory, disk_io, latency]])
        X_scaled = self.scaler.transform(features)

        # decision_function: negative = more anomalous, positive = more normal
        # Typical range: [-0.5, 0.5]
        raw_score = self.model.decision_function(X_scaled)[0]

        # Normalize to [0, 1]:
        #   raw_score = -0.5 → normalized = 1.0 (very anomalous)
        #   raw_score = +0.5 → normalized = 0.0 (normal)
        normalized = float(np.clip(0.5 - raw_score, 0.0, 1.0))
        return normalized

    def batch_score(self, telemetry_list: list) -> np.ndarray:
        """Efficiently score a batch of telemetry events."""
        if not telemetry_list:
            return np.array([])

        X = np.array([
            [t.get("cpu", 0), t.get("memory", 0), t.get("disk_io", 0), t.get("network_latency", 0)]
            for t in telemetry_list
        ])

        if not self._is_fitted:
            return np.clip(
                X[:, 0] / 100 * 0.45 + X[:, 1] / 100 * 0.35 +
                np.minimum(X[:, 2], 100) / 100 * 0.10 +
                np.minimum(X[:, 3], 1000) / 1000 * 0.10,
                0, 1
            )

        X_scaled = self.scaler.transform(X)
        raw_scores = self.model.decision_function(X_scaled)
        return np.clip(0.5 - raw_scores, 0.0, 1.0)
