"""
Kafka producer round-trip test.
Run with: docker exec aiops_backend python scripts/test_kafka_producer.py
"""
import asyncio
import sys
import time
import uuid

sys.path.insert(0, "/app")


async def main():
    from packages.pkg_kafka.producer import KafkaTelemetryProducer

    producer = KafkaTelemetryProducer("kafka:29092")
    event = {
        "event_id": str(uuid.uuid4()),
        "resource_id": "test-i-debug-001",
        "cpu": 72.5,
        "memory": 88.0,
        "disk_io": 12.3,
        "network_latency": 45.0,
        "timestamp": time.time(),
        "source": "debug_test",
    }
    await producer.send_metric("global_telemetry", event)
    await producer.stop()
    print("Message sent to global_telemetry topic")
    print("event_id=" + event["event_id"])
    print("")
    print("Now verify it was received:")
    print("  docker exec aiops_kafka kafka-console-consumer "
          "--bootstrap-server localhost:9092 "
          "--topic global_telemetry --from-beginning --max-messages 5")


asyncio.run(main())
