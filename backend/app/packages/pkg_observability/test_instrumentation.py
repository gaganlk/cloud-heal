import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.packages.pkg_observability.instrumentation import setup_observability

# Create an ephemeral explicit FastAPI app for testing
app = FastAPI()
setup_observability(app, "test-observability-service")

@app.get("/hello")
def read_hello():
    return {"message": "world"}

client = TestClient(app)

def test_metrics_endpoint_exists():
    """Verify Prometheus hooks are attached."""
    # First hit the actual business endpoint to generate a metric count
    response = client.get("/hello")
    assert response.status_code == 200
    
    # Then pull the metrics to ensure the counter incremented
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    
    text = metrics_response.text
    print("\nPROMETHEUS OUTPUT:")
    print(text)
    assert 'api_requests' in text
