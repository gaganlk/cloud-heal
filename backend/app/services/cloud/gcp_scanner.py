"""
Enterprise GCP Multi-Region Scanner.
Discovers GCE Instances, GCS Buckets, and Cloud SQL across the entire project.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)

def _get_gcp_metric(monitoring_client, project_id: str, resource_filter: str, metric_type: str) -> float:
    try:
        from google.cloud.monitoring_v3.types import TimeInterval
        from google.protobuf.timestamp_pb2 import Timestamp

        interval = TimeInterval()
        end = _utcnow()
        start = end - timedelta(minutes=10)

        end_ts = Timestamp()
        end_ts.FromDatetime(end)
        start_ts = Timestamp()
        start_ts.FromDatetime(start)

        interval.end_time = end_ts
        interval.start_time = start_ts

        results = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'metric.type="{metric_type}" AND {resource_filter}',
                "interval": interval,
                "view": "FULL",
            }
        )
        for series in results:
            if series.points:
                # Metrics for CPU are usually 0.0-1.0, convert to %
                val = series.points[0].value.double_value
                if "cpu/utilization" in metric_type:
                    val *= 100
                return round(val, 2)
        return 0.0
    except Exception as e:
        logger.debug(f"GCP metric fetch failed for {metric_type} on {resource_filter}: {e}")
        return 0.0

async def scan_gcp_resources(credentials: dict, broadcast_callback=None) -> List[Dict[str, Any]]:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from google.cloud import monitoring_v3
        import json

        async def _emit(res):
            if broadcast_callback:
                try:
                    await broadcast_callback({
                        "type": "resource_discovered",
                        "data": {**res, "id": None}
                    })
                except Exception as e:
                    logger.debug(f"GCP emit callback failed (non-fatal): {e}")

        project_id = credentials.get("project_id")
        sa_info = credentials.get("service_account_json")
        
        if not project_id or not sa_info:
            return []


        # ── Normalize sa_info ──
        if isinstance(sa_info, str):
            try:
                sa_info = json.loads(sa_info)
            except json.JSONDecodeError:
                pass

        if isinstance(sa_info, dict):
            gcp_creds = service_account.Credentials.from_service_account_info(
                sa_info, 
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        else:
            gcp_creds = service_account.Credentials.from_service_account_file(
                sa_info, 
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

        monitoring = monitoring_v3.MetricServiceClient(credentials=gcp_creds)

        resources: List[Dict[str, Any]] = []

        # --- 1. Compute Engine (All Zones) ---
        try:
            compute = build("compute", "v1", credentials=gcp_creds)
            agg_list = compute.instances().aggregatedList(project=project_id).execute()
            for zone_key, zone_data in agg_list.get("items", {}).items():
                for inst in zone_data.get("instances", []):
                    iid = inst["id"]
                    zone = zone_key.replace("zones/", "")
                    status = inst.get("status", "UNKNOWN").lower()
                    
                    metric_filter = f'resource.labels.instance_id="{iid}"'
                    cpu = _get_gcp_metric(monitoring, project_id, metric_filter, "compute.googleapis.com/instance/cpu/utilization")
                    
                    res = {
                        "resource_id": str(iid),
                        "resource_type": "gce_instance",
                        "name": inst["name"],
                        "region": zone,
                        "status": "running" if status == "running" else status,
                        "provider": "gcp",
                        "cpu_usage": cpu, "memory_usage": 0.0, "network_usage": 0.0,
                        "extra_metadata": {"machine_type": inst.get("machineType", "").split("/")[-1], "zone": zone}
                    }
                    resources.append(res)
                    await _emit(res)
        except Exception as e:
            logger.warning(f"GCP GCE scan partially failed: {e}")

        # --- 2. Cloud Storage (GCS) ---
        try:
            storage = build("storage", "v1", credentials=gcp_creds)
            page_token = None
            while True:
                req = storage.buckets().list(project=project_id, pageToken=page_token)
                buckets = req.execute()
                for bucket in buckets.get("items", []):
                    res = {
                        "resource_id": bucket["id"],
                        "resource_type": "gcs_bucket",
                        "name": bucket["name"],
                        "region": bucket.get("location", "global"),
                        "status": "running",
                        "provider": "gcp",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    }
                    resources.append(res)
                    await _emit(res)
                page_token = buckets.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            logger.warning(f"GCP GCS scan failed: {e}")

        # --- 3. Cloud SQL ---
        try:
            sql = build("sqladmin", "v1beta4", credentials=gcp_creds)
            page_token = None
            while True:
                instances = sql.instances().list(project=project_id, pageToken=page_token).execute()
                for inst in instances.get("items", []):
                    res = {
                        "resource_id": inst["name"],
                        "resource_type": "cloud_sql",
                        "name": inst["name"],
                        "region": inst.get("region", "unknown"),
                        "status": inst.get("state", "unknown").lower(),
                        "provider": "gcp",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    }
                    resources.append(res)
                    await _emit(res)
                page_token = instances.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            logger.warning(f"GCP SQL scan failed: {e}")

        # --- 4. Cloud Run ---
        try:
            run = build("run", "v1", credentials=gcp_creds)
            locations = ["us-central1", "europe-west1", "asia-east1"]
            for loc in locations:
                parent = f"projects/{project_id}/locations/{loc}"
                run_res = run.projects().locations().services().list(parent=parent).execute()
                for s in run_res.get("items", []):
                    resources.append({
                        "resource_id": s["metadata"]["uid"],
                        "resource_type": "cloud_run",
                        "name": s["metadata"]["name"],
                        "status": "running",
                        "provider": "gcp",
                        "region": loc,
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    })
        except Exception as e:
            logger.warning(f"GCP Cloud Run scan failed: {e}")

        # --- 5. Cloud Functions ---
        try:
            cf = build("cloudfunctions", "v1", credentials=gcp_creds)
            parent = f"projects/{project_id}/locations/-"
            page_token = None
            while True:
                funcs = cf.projects().locations().functions().list(
                    parent=parent, pageToken=page_token
                ).execute()
                for f in funcs.get("functions", []):
                    resources.append({
                        "resource_id": f["name"],
                        "resource_type": "cloud_function",
                        "name": f["name"].split("/")[-1],
                        "status": "running" if f.get("status") == "ACTIVE" else "degraded",
                        "provider": "gcp",
                        "region": f["name"].split("/")[3],
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    })
                page_token = funcs.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            logger.warning(f"GCP Cloud Functions scan failed: {e}")

        # --- 6. Pub/Sub Topics ---
        try:
            pubsub = build("pubsub", "v1", credentials=gcp_creds)
            project_path = f"projects/{project_id}"
            page_token = None
            while True:
                topics = pubsub.projects().topics().list(
                    project=project_path, pageToken=page_token
                ).execute()
                for t in topics.get("topics", []):
                    resources.append({
                        "resource_id": t["name"],
                        "resource_type": "pubsub_topic",
                        "name": t["name"].split("/")[-1],
                        "status": "running",
                        "provider": "gcp",
                        "region": "GLOBAL",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    })
                page_token = topics.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            logger.warning(f"GCP Pub/Sub scan failed: {e}")


        logger.info(f"GCP scan complete: {len(resources)} resources discovered")
        return resources
    except Exception as e:
        logger.error(f"GCP global scan failed: {e}")
        return []

def validate_gcp_credentials(credentials: dict) -> bool:
    project_id = credentials.get("project_id")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        import json
        
        sa_info = credentials.get("service_account_json")
        
        logger.info(f"Validating GCP credentials for project: {project_id}")
        
        # ── Normalize sa_info: handle dict, JSON string, or file path ──
        if isinstance(sa_info, str):
            try:
                # Try parsing as JSON string first
                sa_info = json.loads(sa_info)
            except json.JSONDecodeError:
                # If not JSON, assume it's a file path (handled below)
                pass

        if isinstance(sa_info, dict):
            gcp_creds = service_account.Credentials.from_service_account_info(
                sa_info, 
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        else:
            # sa_info is a string but not JSON -> assume file path
            gcp_creds = service_account.Credentials.from_service_account_file(
                sa_info, 
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        
        compute = build("compute", "v1", credentials=gcp_creds)
        # Test call: list zones
        compute.zones().list(project=project_id).execute()
        logger.info(f"GCP Credential validation successful for project: {project_id}")
        return True
    except Exception as e:
        logger.error(f"GCP Credential validation failed for project {project_id}: {type(e).__name__}: {e}")
        return False


