import pytest
import asyncio
from unittest.mock import AsyncMock
from faststream import TestApp
from app.services.telemetry.consumer import app, handle_telemetry, TelemetryEvent

@pytest.mark.asyncio
async def test_duplicate_idempotency(monkeypatch):
    # Mock redis client
    mock_redis = AsyncMock()
    # Behavior: First call returns True (is_new), second call returns False (duplicate)
    mock_redis.setnx.side_effect = [True, False]
    monkeypatch.setattr("services.telemetry.consumer.redis_client", mock_redis)
    
    event_payload = {
        "event_id": "duplicate-test-1",
        "resource_id": "ec2-alpha",
        "cpu": 95.0,
        "memory": 82.0,
        "timestamp": 123456789.0
    }
    
    # Run the App in testing mode without needing actual Kafka
    async with TestApp(app):
        # We manually call the handler since we want to pass the Pydantic object
        # Alternatively, we can use broker.publish, but testing the raw function is faster here.
        mock_logger = AsyncMock()
        
        event = TelemetryEvent(**event_payload)
        
        # Fire 1 - should process normally
        await handle_telemetry(event, mock_logger)
        mock_logger.info.assert_any_call("Processing telemetry for ec2-alpha (CPU: 95.0 | Mem: 82.0)")
        
        # Fire 2 - Exact same payload, should be caught by idempotency
        await handle_telemetry(event, mock_logger)
        mock_logger.info.assert_any_call("Ignored duplicate event: duplicate-test-1")
        
    assert mock_redis.setnx.call_count == 2
