"""
Complete boto3 healing executor with all 6 action types.
Uses ThreadPoolExecutor to bridge sync boto3 calls into async context.
"""
import asyncio
import logging
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor
import boto3

logger = logging.getLogger(__name__)


class CloudHealingExecutor:
    """
    Production AWS healing engine.
    Maps all 6 healing action types to concrete Boto3 API calls.
    """
    def __init__(self, region_name: str = "us-east-1", max_workers: int = 10,
                 access_key_id: str = None, secret_access_key: str = None):
        self.region_name = region_name
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
        )
        self.ec2 = self.session.client("ec2")
        self.rds = self.session.client("rds")
        self.asg = self.session.client("autoscaling")
        self.elbv2 = self.session.client("elbv2")

    async def _run(self, fn, *args, **kwargs):
        """Run a sync boto3 call inside the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, lambda: fn(*args, **kwargs))

    # ── Restart ─────────────────────────────────────────────────────────────
    async def reboot_ec2_instance(self, instance_id: str) -> dict:
        """Hard reboot an EC2 instance via AWS API."""
        try:
            logger.info(f"Issuing reboot for EC2 {instance_id}")
            await self._run(self.ec2.reboot_instances, InstanceIds=[instance_id])
            return {"status": "success", "action": "reboot_ec2", "target": instance_id,
                    "message": f"Reboot signal sent to EC2 {instance_id}"}
        except ClientError as e:
            logger.error(f"Failed to reboot EC2 {instance_id}: {e}")
            return {"status": "failed", "action": "reboot_ec2", "target": instance_id, "error": str(e)}

    # ── Scale Up ────────────────────────────────────────────────────────────
    async def scale_out_asg(self, asg_name: str, increment: int = 1) -> dict:
        """Increase Auto Scaling Group desired capacity."""
        try:
            desc = await self._run(self.asg.describe_auto_scaling_groups,
                                   AutoScalingGroupNames=[asg_name])
            groups = desc.get("AutoScalingGroups", [])
            if not groups:
                raise ValueError(f"ASG '{asg_name}' not found")
            current = groups[0]["DesiredCapacity"]
            max_cap = groups[0]["MaxSize"]
            new_cap = min(current + increment, max_cap)
            if new_cap == current:
                return {"status": "skipped", "action": "scale_out_asg", "target": asg_name,
                        "message": f"Already at max capacity ({max_cap})"}
            await self._run(self.asg.set_desired_capacity,
                            AutoScalingGroupName=asg_name,
                            DesiredCapacity=new_cap,
                            HonorCooldown=True)
            return {"status": "success", "action": "scale_out_asg", "target": asg_name,
                    "message": f"ASG {asg_name}: capacity {current} → {new_cap}",
                    "new_capacity": new_cap}
        except Exception as e:
            logger.error(f"Failed to scale ASG {asg_name}: {e}")
            return {"status": "failed", "action": "scale_out_asg", "target": asg_name, "error": str(e)}

    # ── Reroute ─────────────────────────────────────────────────────────────
    async def reroute_traffic_alb(self, instance_id: str) -> dict:
        """
        Deregister an unhealthy instance from all ALB target groups it belongs to.
        ALB will stop routing new connections to this instance.
        """
        try:
            tgs = await self._run(self.elbv2.describe_target_groups)
            deregistered = []
            for tg in tgs.get("TargetGroups", []):
                tg_arn = tg["TargetGroupArn"]
                health = await self._run(self.elbv2.describe_target_health, TargetGroupArn=tg_arn)
                for thd in health.get("TargetHealthDescriptions", []):
                    if thd["Target"]["Id"] == instance_id:
                        await self._run(self.elbv2.deregister_targets,
                                        TargetGroupArn=tg_arn,
                                        Targets=[{"Id": instance_id}])
                        deregistered.append(tg_arn)
                        logger.info(f"Deregistered {instance_id} from TG {tg_arn}")
            return {"status": "success", "action": "reroute_alb",
                    "message": f"Deregistered {instance_id} from {len(deregistered)} target group(s)",
                    "target_groups": deregistered}
        except ClientError as e:
            return {"status": "failed", "action": "reroute_alb", "target": instance_id, "error": str(e)}

    # ── Isolate ─────────────────────────────────────────────────────────────
    async def isolate_instance(self, instance_id: str, isolation_sg_id: str) -> dict:
        """
        Move instance to an isolation security group with restricted access.
        The isolation_sg_id should be a pre-configured SG with no inbound rules.
        """
        try:
            await self._run(self.ec2.modify_instance_attribute,
                            InstanceId=instance_id,
                            Groups=[isolation_sg_id])
            return {"status": "success", "action": "isolate_sg",
                    "message": f"EC2 {instance_id} moved to isolation SG {isolation_sg_id}"}
        except ClientError as e:
            return {"status": "failed", "action": "isolate_sg", "target": instance_id, "error": str(e)}

    # ── Failover ────────────────────────────────────────────────────────────
    async def restart_rds_cluster(self, cluster_id: str) -> dict:
        """Trigger Aurora cluster failover to a standby replica."""
        try:
            logger.info(f"Initiating RDS failover for cluster {cluster_id}")
            try:
                await self._run(self.rds.failover_db_cluster, DBClusterIdentifier=cluster_id)
                return {"status": "success", "action": "failover_aurora_cluster",
                        "message": f"Aurora cluster {cluster_id} failover initiated"}
            except ClientError as e:
                if "DBClusterNotFoundFault" in str(e):
                    # Single-instance RDS: reboot with failover flag
                    await self._run(self.rds.reboot_db_instance,
                                    DBInstanceIdentifier=cluster_id,
                                    ForceFailover=True)
                    return {"status": "success", "action": "failover_rds_instance",
                            "message": f"RDS instance {cluster_id} rebooted with ForceFailover=True"}
                raise
        except ClientError as e:
            return {"status": "failed", "action": "failover_rds", "target": cluster_id, "error": str(e)}

    # ── Rollback ────────────────────────────────────────────────────────────
    async def create_recovery_snapshot(self, instance_id: str) -> dict:
        """
        Create an AMI from current instance state for potential restore.
        This is a pre-action step; actual restoration requires a new instance launch.
        """
        try:
            from datetime import datetime
            snapshot_name = f"recovery-{instance_id}-{int(datetime.utcnow().timestamp())}"
            resp = await self._run(self.ec2.create_image,
                                   InstanceId=instance_id,
                                   Name=snapshot_name,
                                   NoReboot=True)
            ami_id = resp.get("ImageId")
            logger.info(f"Recovery AMI {ami_id} created from {instance_id}")
            return {"status": "success", "action": "create_recovery_ami",
                    "message": f"Recovery AMI {ami_id} created from {instance_id}",
                    "ami_id": ami_id}
        except ClientError as e:
            return {"status": "failed", "action": "create_recovery_ami",
                    "target": instance_id, "error": str(e)}

    def shutdown(self):
        """Cleanly shut down the thread pool executor."""
        self.executor.shutdown(wait=False)
