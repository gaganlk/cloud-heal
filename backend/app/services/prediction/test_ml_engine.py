import pytest
import numpy as np
from app.services.prediction.ml_engine import FailurePredictorML

@pytest.fixture
def ml_model():
    return FailurePredictorML()

def test_heuristic_fallback(ml_model):
    """Validate it maps 0.0 to safe, and 1.0 to guaranteed crash before training."""
    safe_score = ml_model.predict_degradation({"cpu": 40, "memory": 50})
    assert safe_score == 0.0
    
    danger_score = ml_model.predict_degradation({"cpu": 95, "memory": 92})
    assert danger_score == 1.0

def test_trained_model_precision(ml_model):
    """Validate ML dynamically tracks historical features to ground truth scores."""
    # Fake historical training data [cpu, memory, disk_io, network]
    X_history = np.array([
        [10, 20, 5, 2],    # Healthy
        [40, 50, 10, 10],  # Healthy
        [85, 80, 50, 40],  # Warning
        [90, 85, 60, 60],  # Severe Warning
        [99, 95, 90, 80]   # Critical Crash
    ])
    
    # Target ground truth degradation scores
    y_target = np.array([0.0, 0.2, 0.6, 0.8, 1.0])
    
    # Train the model
    ml_model.train(X_history, y_target)
    assert ml_model.is_trained is True

    # Test an intermediate state
    warning_score = ml_model.predict_degradation({"cpu": 80, "memory": 82, "disk_io": 45, "network_latency": 30})
    
    # Validate the score is reasonably bound
    assert 0.4 <= warning_score <= 0.8
