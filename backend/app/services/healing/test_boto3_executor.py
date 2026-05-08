import pytest
import asyncio
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from app.services.healing.boto3_executor import CloudHealingExecutor

@pytest.fixture
def executor():
    with patch('boto3.Session') as mock_session:
        yield CloudHealingExecutor(region_name="us-east-1")

@pytest.mark.asyncio
async def test_ec2_reboot_success(executor):
    """Verify that reboot call is correctly structured."""
    executor.ec2_client.reboot_instances.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    
    result = await executor.reboot_ec2_instance("i-12345")
    assert result["status"] == "success"
    assert result["target"] == "i-12345"
    executor.ec2_client.reboot_instances.assert_called_once_with(InstanceIds=["i-12345"])

@pytest.mark.asyncio
async def test_asg_scale_out_success(executor):
    """Verify ASG scaling logic calculates new capacity correctly."""
    # Mock describe
    executor.autoscaling_client.describe_auto_scaling_groups.return_value = {
        "AutoScalingGroups": [{"DesiredCapacity": 2}]
    }
    # Mock set_desired
    executor.autoscaling_client.set_desired_capacity.return_value = {}
    
    result = await executor.scale_out_asg("my-asg", increment=2)
    assert result["status"] == "success"
    assert result["new_capacity"] == 4
    executor.autoscaling_client.set_desired_capacity.assert_called_once_with(
        AutoScalingGroupName="my-asg",
        DesiredCapacity=4,
        HonorCooldown=True
    )

@pytest.mark.asyncio
async def test_healing_failure_handling(executor):
    """Verify error responses are captured when AWS APIs fail."""
    error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Not found'}}
    executor.rds_client.reboot_db_instance.side_effect = ClientError(error_response, 'RebootDBInstance')
    
    result = await executor.restart_rds_cluster("missing-db")
    assert result["status"] == "failed"
    assert "ResourceNotFoundException" in result["error"]
