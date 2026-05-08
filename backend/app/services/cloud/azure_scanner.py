"""
Enterprise Azure Multi-Region Scanner.
Discovers VMs, Storage Accounts, and SQL Databases across all resource groups and regions.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)

def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)

def _get_azure_metric(monitor_client, resource_id: str, metric_name: str) -> float:
    try:
        end = _utcnow()
        start = end - timedelta(minutes=10)
        metrics_data = monitor_client.metrics.list(
            resource_uri=resource_id,
            timespan=f"{start.isoformat()}/{end.isoformat()}",
            interval="PT5M",
            metricnames=metric_name,
            aggregation="Average",
        )
        for metric in metrics_data.value:
            for ts in metric.timeseries:
                if ts.data:
                    last = [d for d in ts.data if d.average is not None]
                    if last: return round(last[-1].average, 2)
        return 0.0
    except Exception as e:
        logger.debug(f"Azure metric fetch failed for {metric_name} on {resource_id}: {e}")
        return 0.0

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception(lambda e: "429" in str(e) or "Too Many Requests" in str(e))
)
async def scan_azure_resources(credentials: dict, broadcast_callback=None) -> List[Dict[str, Any]]:
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.monitor import MonitorManagementClient
        from azure.mgmt.storage import StorageManagementClient
        from azure.mgmt.sql import SqlManagementClient

        async def _emit(res):
            if broadcast_callback:
                try:
                    await broadcast_callback({
                        "type": "resource_discovered",
                        "data": {**res, "id": None}
                    })
                except: pass

        sub_id = credentials.get("subscription_id")
        az_creds = ClientSecretCredential(
            tenant_id=credentials.get("tenant_id"),
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
        )

        resources: List[Dict[str, Any]] = []


        # --- 1. Virtual Machines ---
        try:
            compute_client = ComputeManagementClient(az_creds, sub_id)
            monitor_client = MonitorManagementClient(az_creds, sub_id)
            for vm in compute_client.virtual_machines.list_all():
                vm_id = vm.id
                cpu = _get_azure_metric(monitor_client, vm_id, "Percentage CPU")
                res = {
                    "resource_id": vm_id,
                    "resource_type": "azure_vm",
                    "name": vm.name,
                    "region": vm.location,
                    "status": "running", # Simplified
                    "provider": "azure",
                    "cpu_usage": cpu, "memory_usage": 0.0, "network_usage": 0.0,
                    "extra_metadata": {"vm_size": vm.hardware_profile.vm_size if vm.hardware_profile else None}
                }
                resources.append(res)
                await _emit(res)
        except Exception as e:
            logger.warning(f"Azure VM scan failed: {e}")

        # --- 2. Storage Accounts ---
        try:
            storage_client = StorageManagementClient(az_creds, sub_id)
            for sa in storage_client.storage_accounts.list():
                res = {
                    "resource_id": sa.id,
                    "resource_type": "azure_storage",
                    "name": sa.name,
                    "region": sa.location,
                    "status": "available",
                    "provider": "azure",
                    "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                }
                resources.append(res)
                await _emit(res)
        except Exception as e:
            logger.warning(f"Azure Storage scan failed: {e}")

        # --- 3. SQL Databases ---
        try:
            sql_client = SqlManagementClient(az_creds, sub_id)
            for server in sql_client.servers.list():
                for db in sql_client.databases.list_by_server(server.id.split("/")[4], server.name):
                    if db.name == "master": continue
                    res = {
                        "resource_id": db.id,
                        "resource_type": "azure_sql",
                        "name": db.name,
                        "region": db.location,
                        "status": db.status or "online",
                        "provider": "azure",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    }
                    resources.append(res)
                    await _emit(res)
        except Exception as e:
            logger.warning(f"Azure SQL scan failed: {e}")

        # --- 4. App Services & Functions ---
        try:
            from azure.mgmt.web import WebSiteManagementClient
            web_client = WebSiteManagementClient(az_creds, sub_id)
            for site in web_client.web_apps.list():
                resources.append({
                    "resource_id": site.id,
                    "resource_type": "azure_app_service" if "functionapp" not in (site.kind or "").lower() else "azure_function",
                    "name": site.name,
                    "region": site.location,
                    "status": site.state.lower() if site.state else "running",
                    "provider": "azure",
                    "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                })
        except: pass

        # --- 5. Service Bus ---
        try:
            from azure.mgmt.servicebus import ServiceBusManagementClient
            sb_client = ServiceBusManagementClient(az_creds, sub_id)
            for ns in sb_client.namespaces.list():
                resources.append({
                    "resource_id": ns.id,
                    "resource_type": "azure_service_bus",
                    "name": ns.name,
                    "region": ns.location,
                    "status": "active",
                    "provider": "azure",
                    "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                })
        except: pass

        # --- 6. Cosmos DB ---
        try:
            from azure.mgmt.cosmosdb import CosmosDBManagementClient
            cosmos_client = CosmosDBManagementClient(az_creds, sub_id)
            for account in cosmos_client.database_accounts.list():
                resources.append({
                    "resource_id": account.id,
                    "resource_type": "azure_cosmos_db",
                    "name": account.name,
                    "region": account.location,
                    "status": account.provisioning_state.lower(),
                    "provider": "azure",
                    "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                })
        except: pass


        logger.info(f"Azure scan complete: {len(resources)} resources discovered")
        return resources
    except Exception as e:
        logger.error(f"Azure global scan failed: {e}")
        return []

def validate_azure_credentials(credentials: dict) -> bool:
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource import SubscriptionClient
        az_creds = ClientSecretCredential(
            tenant_id=credentials["tenant_id"],
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
        )
        sub_client = SubscriptionClient(az_creds)
        list(sub_client.subscriptions.list())
        return True
    except Exception as e:
        logger.error(f"Azure Credential validation failed: {e}")
        return False
