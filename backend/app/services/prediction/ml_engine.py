import numpy as np
from sklearn.linear_model import LinearRegression
import logging

logger = logging.getLogger(__name__)

class FailurePredictorML:
    def __init__(self):
        self.is_trained = False
        self.model = LinearRegression()
        # Baseline analytical thresholds (Cold-Start Phase)
        self.CPU_SAFE = 50.0
        self.CPU_DANGER = 90.0
        self.MEM_SAFE = 60.0
        self.MEM_DANGER = 90.0

    def train(self, X, y):
        """
        Train the regressor on real historical telemetry features and ground-truth scores.
        """
        try:
            self.model.fit(X, y)
            self.is_trained = True
            logger.info("AIOps ML model recalibrated with live telemetry history.")
        except Exception as e:
            logger.error(f"ML recalibration failed: {e}")
            self.is_trained = False

    def predict_degradation(self, telemetry_data: dict) -> float:
        """
        Predict degradation score (0.0 to 1.0) using live infrastructure telemetry.
        Phase 1: Deterministic Baseline (used during cold-start/low-data scenarios)
        Phase 2: Trained Regression Model (active once telemetry history is sufficient)
        """
        cpu = telemetry_data.get("cpu", 0.0)
        memory = telemetry_data.get("memory", 0.0)
        disk_io = telemetry_data.get("disk_io", 0.0)
        network = telemetry_data.get("network_latency", 0.0)

        if self.is_trained:
            features = np.array([[cpu, memory, disk_io, network]])
            score = self.model.predict(features)[0]
            return float(np.clip(score, 0.0, 1.0))

        # --- Phase 1: Deterministic Baseline Engine ---
        # If any metric is in extreme saturation zone, return peak degradation
        if cpu >= self.CPU_DANGER or memory >= self.MEM_DANGER:
            return 1.0
        
        # If metrics are in safe nominal zone, return 0.0
        if cpu <= self.CPU_SAFE and memory <= self.MEM_SAFE:
            return 0.0
            
        # Analytical interpolation for intermediate states
        cpu_score = max(0, (cpu - self.CPU_SAFE) / (self.CPU_DANGER - self.CPU_SAFE))
        mem_score = max(0, (memory - self.MEM_SAFE) / (self.MEM_DANGER - self.MEM_SAFE))
        
        score = max(cpu_score, mem_score)
        return float(np.clip(score, 0.0, 1.0))
