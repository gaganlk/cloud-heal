from locust import HttpUser, task, between

class AIOpsUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def check_health(self):
        """Simulate frequent health/readiness checks."""
        self.client.get("/api/health")

    @task(1)
    def view_dashboard(self):
        """Simulate a user viewing the dashboard (fetches summary metrics)."""
        self.client.get("/api/dashboard/metrics", name="Dashboard Metrics")
        
    @task(1)
    def check_credentials(self):
        """Simulate a user checking cloud connections."""
        self.client.get("/api/credentials", name="List Credentials")

    @task(2)
    def simulate_telemetry_webhook(self):
        """
        Simulate an external cloud webhook pushing telemetry 
        to test Kafka ingestion rates.
        """
        payload = {
            "resource_id": f"load-test-instance-{self.environment.runner.user_count}",
            "resource_type": "ec2_instance",
            "provider": "aws",
            "cpu_usage": 99.9,
            "memory_usage": 85.5,
            "network_usage": 150.0
        }
        self.client.post("/api/chaos/inject_telemetry", json=payload, name="Inject Telemetry")
