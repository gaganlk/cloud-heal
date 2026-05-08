"""
Enterprise AWS Multi-Region Scanner.
Automatically discovers resources across all active AWS regions.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)

boto_config = Config(
    retries = dict(
        max_attempts = 5,
        mode = 'standard'
    )
)

_CLOUDWATCH_PERIOD = 300
_CLOUDWATCH_LOOKBACK = 10

def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)

def _cloudwatch_average(cw_client, namespace: str, metric_name: str, dimensions: List[Dict]) -> float:
    try:
        end = _utcnow()
        start = end - timedelta(minutes=_CLOUDWATCH_LOOKBACK)
        response = cw_client.get_metric_statistics(
            Namespace=namespace, MetricName=metric_name, Dimensions=dimensions,
            StartTime=start, EndTime=end, Period=_CLOUDWATCH_PERIOD, Statistics=["Average"],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints: return 0.0
        datapoints.sort(key=lambda d: d["Timestamp"], reverse=True)
        return round(datapoints[0]["Average"], 2)
    except Exception as e:
        logger.debug(f"CloudWatch metric fetch failed for {metric_name} on {dimensions}: {e}")
        return 0.0

def _get_ec2_metrics(session: boto3.Session, instance_id: str, region: str) -> Dict[str, float]:
    cw = session.client("cloudwatch", region_name=region, config=boto_config)
    dim = [{"Name": "InstanceId", "Value": instance_id}]
    cpu = _cloudwatch_average(cw, "AWS/EC2", "CPUUtilization", dim)
    # Network
    net_in = _cloudwatch_average(cw, "AWS/EC2", "NetworkIn", dim)
    net_mb = round(min(net_in / 1_048_576, 100.0), 2) if net_in else 0.0
    return {"cpu_usage": cpu, "memory_usage": 0.0, "network_usage": net_mb}

async def scan_aws_resources(credentials: dict, broadcast_callback=None) -> List[Dict[str, Any]]:
    """
    Multi-Region AWS Scanner.
    Discovers resources across all available regions with real-time streaming.
    """
    session = boto3.Session(
        aws_access_key_id=credentials.get("access_key_id"),
        aws_secret_access_key=credentials.get("secret_access_key"),
    )

    async def _emit(res):
        if broadcast_callback:
            try:
                await broadcast_callback({
                    "type": "resource_discovered",
                    "data": {**res, "id": None}
                })
            except Exception as e:
                logger.debug(f"AWS emit callback failed (non-fatal): {e}")

    resources: List[Dict[str, Any]] = []

    
    # 1. Discover active regions
    try:
        ec2_client = session.client("ec2", region_name="us-east-1", config=boto_config)
        regions = [r["RegionName"] for r in ec2_client.describe_regions()["Regions"]]
    except Exception as e:
        logger.error(f"Failed to list AWS regions: {e}")
        regions = [credentials.get("region", "us-east-1")]

    # 2. Global Services (S3)
    try:
        s3 = session.client("s3", config=boto_config)
        for bucket in s3.list_buckets().get("Buckets", []):
            bname = bucket["Name"]
            res = {
                "resource_id": bname,
                "resource_type": "s3_bucket",
                "name": bname,
                "region": "global",
                "status": "running",
                "provider": "aws",
                "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
            }
            resources.append(res)
            await _emit(res)
    except Exception as e:
        logger.warning(f"S3 scan failed: {e}")

    # 3. Regional Services (EC2, RDS)
    for region in regions:
        # --- EC2 ---
        try:
            ec2 = session.client("ec2", region_name=region, config=boto_config)
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for res in page.get("Reservations", []):
                    for inst in res.get("Instances", []):
                        if inst["State"]["Name"] == "terminated": continue
                        iid = inst["InstanceId"]
                        name = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), iid)
                        metrics = _get_ec2_metrics(session, iid, region)
                        res = {
                            "resource_id": iid,
                            "resource_type": "ec2_instance",
                            "name": name,
                            "region": region,
                            "status": inst["State"]["Name"],
                            "provider": "aws",
                            "tags": {t["Key"]: t["Value"] for t in inst.get("Tags", [])},
                            "extra_metadata": {"instance_type": inst.get("InstanceType"), "availability_zone": inst.get("Placement", {}).get("AvailabilityZone")},
                            **metrics
                        }
                        resources.append(res)
                        await _emit(res)
        except ClientError as ce:
            if ce.response["Error"]["Code"] == "AuthFailure":
                logger.error(f"AWS AuthFailure in region {region}: {ce}")
                raise ce # Fail fast on credential issues
            logger.warning(f"EC2 scan failed in region {region}: {ce}")
        except Exception as e:
            logger.warning(f"EC2 scan failed in region {region}: {e}")

        # --- RDS ---
        try:
            rds = session.client("rds", region_name=region, config=boto_config)
            paginator = rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for db in page.get("DBInstances", []):
                    db_id = db["DBInstanceIdentifier"]
                    res = {
                        "resource_id": db_id,
                        "resource_type": "rds_instance",
                        "name": db_id,
                        "region": region,
                        "status": db["DBInstanceStatus"],
                        "provider": "aws",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    }
                    resources.append(res)
                    await _emit(res)
        except Exception as e:
            logger.warning(f"RDS scan failed in region {region}: {e}")

        # --- Lambda ---
        try:
            lambda_client = session.client("lambda", region_name=region, config=boto_config)
            paginator = lambda_client.get_paginator("list_functions")
            for page in paginator.paginate():
                for fn in page.get("Functions", []):
                    res = {
                        "resource_id": fn["FunctionArn"],
                        "resource_type": "lambda_function",
                        "name": fn["FunctionName"],
                        "region": region,
                        "status": "running",
                        "provider": "aws",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    }
                    resources.append(res)
                    await _emit(res)
        except Exception as e:
            logger.warning(f"Lambda scan failed in region {region}: {e}")

        # --- ECS ---
        try:
            ecs = session.client("ecs", region_name=region, config=boto_config)
            paginator = ecs.get_paginator("list_clusters")
            for page in paginator.paginate():
                for cluster_arn in page.get("clusterArns", []):
                    resources.append({
                        "resource_id": cluster_arn,
                        "resource_type": "ecs_cluster",
                        "name": cluster_arn.split("/")[-1],
                        "region": region,
                        "status": "running",
                        "provider": "aws",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    })
        except Exception as e:
            logger.warning(f"ECS scan failed in region {region}: {e}")

        # --- SQS ---
        try:
            sqs = session.client("sqs", region_name=region, config=boto_config)
            paginator = sqs.get_paginator("list_queues")
            for page in paginator.paginate():
                for q_url in page.get("QueueUrls", []):
                    resources.append({
                        "resource_id": q_url,
                        "resource_type": "sqs_queue",
                        "name": q_url.split("/")[-1],
                        "region": region,
                        "status": "running",
                        "provider": "aws",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    })
        except Exception as e:
            logger.warning(f"SQS scan failed in region {region}: {e}")

        # --- SNS ---
        try:
            sns = session.client("sns", region_name=region, config=boto_config)
            paginator = sns.get_paginator("list_topics")
            for page in paginator.paginate():
                for topic in page.get("Topics", []):
                    resources.append({
                        "resource_id": topic["TopicArn"],
                        "resource_type": "sns_topic",
                        "name": topic["TopicArn"].split(":")[-1],
                        "region": region,
                        "status": "running",
                        "provider": "aws",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    })
        except Exception as e:
            logger.warning(f"SNS scan failed in region {region}: {e}")

        # --- ELBv2 ---
        try:
            elbv2 = session.client("elbv2", region_name=region, config=boto_config)
            paginator = elbv2.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page.get("LoadBalancers", []):
                    resources.append({
                        "resource_id": lb["LoadBalancerArn"],
                        "resource_type": "load_balancer",
                        "name": lb["LoadBalancerName"],
                        "region": region,
                        "status": lb["State"]["Code"],
                        "provider": "aws",
                        "cpu_usage": 0.0, "memory_usage": 0.0, "network_usage": 0.0,
                    })
        except Exception as e:
            logger.warning(f"ELBv2 scan failed in region {region}: {e}")


    logger.info(f"Multi-region AWS scan complete: {len(resources)} resources discovered")
    return resources

def validate_aws_credentials(credentials: dict) -> bool:
    try:
        session = boto3.Session(
            aws_access_key_id=credentials.get("access_key_id"),
            aws_secret_access_key=credentials.get("secret_access_key"),
        )
        sts = session.client("sts")
        sts.get_caller_identity()
        return True
    except ClientError as ce:
        logger.error(f"AWS Credential validation failed: {ce}")
        return False
    except Exception as e:
        logger.error(f"AWS Credential validation unexpected error: {e}")
        return False
