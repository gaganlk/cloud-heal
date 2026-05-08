import pytest
import asyncio
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from app.services.discovery.aws_scanner import AWSTopologyScanner

@pytest.fixture
def scanner():
    with patch('boto3.Session') as mock_session:
        yield AWSTopologyScanner("fake_access", "fake_secret")

@pytest.mark.asyncio
async def test_ec2_scan_success(scanner):
    # Mocking EC2 describe_instances paginator
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'State': {'Name': 'running'},
                            'InstanceType': 't3.micro',
                            'Tags': [{'Key': 'Name', 'Value': 'production-web'}]
                        }
                    ]
                }
            ]
        }
    ]
    scanner.ec2.get_paginator.return_value = mock_paginator

    resources = await scanner.scan_ec2_instances()
    assert len(resources) == 1
    assert resources[0]["name"] == "production-web"
    assert resources[0]["status"] == "running"
    assert resources[0]["extra_metadata"]["instance_type"] == "t3.micro"

@pytest.mark.asyncio
async def test_throttling_failure_scenario(scanner):
    # Simulate an AWS API Throttling Exception
    mock_paginator = MagicMock()
    
    error_response = {'Error': {'Code': 'Throttling', 'Message': 'Rate exceeded'}}
    mock_paginator.paginate.side_effect = ClientError(error_response, 'DescribeInstances')
    scanner.ec2.get_paginator.return_value = mock_paginator

    with pytest.raises(ClientError) as exc_info:
        await scanner.scan_ec2_instances()
    
    assert exc_info.value.response['Error']['Code'] == 'Throttling'

if __name__ == "__main__":
    # Usually executed via pytest CLI
    pass
