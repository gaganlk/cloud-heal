import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class AWSTopologyScanner:
    def __init__(self, access_key: str, secret_key: str, region: str = "us-east-1"):
        """Initialize real Boto3 clients. In production, prefer STS Assumed Roles."""
        self.session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.ec2 = self.session.client('ec2')
        self.rds = self.session.client('rds')
        self.elb = self.session.client('elbv2')

    async def scan_ec2_instances(self) -> list:
        """Discover all EC2 instances via pagination."""
        resources = []
        try:
            paginator = self.ec2.get_paginator('describe_instances')
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        name = "unnamed-ec2"
                        tags = instance.get('Tags', [])
                        for tag in tags:
                            if tag['Key'] == 'Name':
                                name = tag['Value']
                        
                        resources.append({
                            "resource_id": instance['InstanceId'],
                            "resource_type": "ec2_instance",
                            "name": name,
                            "status": instance['State']['Name'],
                            "provider": "aws",
                            "region": self.session.region_name,
                            "extra_metadata": {
                                "instance_type": instance.get('InstanceType'),
                                "vpc_id": instance.get('VpcId'),
                                "subnet_id": instance.get('SubnetId')
                            }
                        })
        except ClientError as e:
            logger.error(f"EC2 scanning failed: {e}")
            raise
        return resources

    async def scan_rds_instances(self) -> list:
        """Discover RDS databases."""
        resources = []
        try:
            paginator = self.rds.get_paginator('describe_db_instances')
            for page in paginator.paginate():
                for db in page['DBInstances']:
                    resources.append({
                        "resource_id": db['DBInstanceIdentifier'],
                        "resource_type": "rds_instance",
                        "name": db['DBInstanceIdentifier'],
                        "status": db['DBInstanceStatus'],
                        "provider": "aws",
                        "region": self.session.region_name,
                        "extra_metadata": {
                            "engine": db.get('Engine'),
                            "vpc_id": db['DBSubnetGroup'].get('VpcId') if 'DBSubnetGroup' in db else None,
                            "publicly_accessible": db.get('PubliclyAccessible')
                        }
                    })
        except ClientError as e:
            logger.error(f"RDS scanning failed: {e}")
            raise
        return resources

    async def scan_load_balancers(self) -> list:
        """Discover ALBs and NLBs."""
        resources = []
        try:
            paginator = self.elb.get_paginator('describe_load_balancers')
            for page in paginator.paginate():
                for lb in page['LoadBalancers']:
                    resources.append({
                        "resource_id": lb['LoadBalancerArn'], # ARNs are globally unique
                        "resource_type": "load_balancer",
                        "name": lb['LoadBalancerName'],
                        "status": lb['State']['Code'],
                        "provider": "aws",
                        "region": self.session.region_name,
                        "extra_metadata": {
                            "scheme": lb.get('Scheme'),
                            "vpc_id": lb.get('VpcId')
                        }
                    })
        except ClientError as e:
            logger.error(f"ELB scanning failed: {e}")
            raise
        return resources

    async def perform_full_scan(self) -> list:
        """Orchestrate the full topology discovery."""
        all_resources = []
        # In a real environment, run these concurrently using asyncio.gather with thread executors
        all_resources.extend(await self.scan_ec2_instances())
        all_resources.extend(await self.scan_rds_instances())
        all_resources.extend(await self.scan_load_balancers())
        return all_resources
