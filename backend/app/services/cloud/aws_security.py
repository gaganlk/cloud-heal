import boto3
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def get_aws_security_findings(credentials: dict) -> List[Dict[str, Any]]:
    """
    Fetch security findings from AWS Security Hub.
    Requires 'securityhub:GetFindings' permission.
    """
    try:
        session = boto3.Session(
            aws_access_key_id=credentials.get("access_key_id"),
            aws_secret_access_key=credentials.get("secret_access_key"),
            region_name=credentials.get("region", "us-east-1"),
        )
        sh = session.client("securityhub")
        
        # Get active findings with severity High or Critical
        response = sh.get_findings(
            Filters={
                "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
                "SeverityLabel": [
                    {"Value": "CRITICAL", "Comparison": "EQUALS"},
                    {"Value": "HIGH", "Comparison": "EQUALS"}
                ],
                "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}]
            },
            MaxResults=50
        )
        
        findings = []
        for finding in response.get("Findings", []):
            resource_id = finding["Resources"][0]["Id"]
            findings.append({
                "resource_id": resource_id,
                "finding_type": finding["Title"],
                "severity": finding["Severity"]["Label"].lower(),
                "description": finding["Description"],
                "remediation": finding.get("Remediation", {}).get("Recommendation", {}).get("Text", "Review AWS documentation for remediation steps.")
            })
        
        return findings
    except Exception as e:
        logger.warning(f"AWS Security Hub fetch failed (Security Hub might be disabled): {e}")
        # Fallback to manual basic security checks if SH is disabled
        return _perform_basic_iam_checks(session)

def _perform_basic_iam_checks(session: boto3.Session) -> List[Dict[str, Any]]:
    """Basic fallback security checks if Security Hub is not enabled."""
    findings = []
    try:
        iam = session.client("iam")
        users = iam.list_users().get("Users", [])
        for user in users:
            uname = user["UserName"]
            # Check for users without MFA (including Security Keys/Passkeys)
            mfa = iam.list_mfa_devices(UserName=uname).get("MFADevices", [])
            
            # Note: For newer Passkeys, we also want to ensure we aren't missing any newer device types
            if not mfa:
                findings.append({
                    "resource_id": f"iam_user:{uname}",
                    "finding_type": "MFA Not Enabled",
                    "severity": "high",
                    "description": f"IAM user '{uname}' does not have MFA enabled.",
                    "remediation": "Enable multi-factor authentication (Virtual, Hardware, or Security Key) for this user in the IAM console."
                })
                
        # Check for public S3 buckets (simplified check)
        s3 = session.client("s3")
        buckets = s3.list_buckets().get("Buckets", [])
        for bucket in buckets:
            bname = bucket["Name"]
            try:
                policy_status = s3.get_bucket_policy_status(Bucket=bname)
                if policy_status.get("PolicyStatus", {}).get("IsPublic"):
                    findings.append({
                        "resource_id": bname,
                        "finding_type": "Public S3 Bucket",
                        "severity": "critical",
                        "description": f"S3 bucket '{bname}' is publicly accessible.",
                        "remediation": "Update bucket policy to restrict access or enable Block Public Access."
                    })
            except:
                pass # Policy doesn't exist or access denied
                
        # Check for unencrypted EBS volumes
        ec2 = session.client("ec2")
        volumes = ec2.describe_volumes().get("Volumes", [])
        for vol in volumes:
            if not vol.get("Encrypted"):
                findings.append({
                    "resource_id": vol["VolumeId"],
                    "finding_type": "Unencrypted EBS Volume",
                    "severity": "medium",
                    "description": f"EBS Volume '{vol['VolumeId']}' is not encrypted.",
                    "remediation": "Re-create volume from encrypted snapshot or enable default encryption."
                })

        # Check for Security Groups with port 22 open to world
        sgs = ec2.describe_security_groups().get("SecurityGroups", [])
        for sg in sgs:
            for perm in sg.get("IpPermissions", []):
                from_port = perm.get("FromPort")
                to_port = perm.get("ToPort")
                if from_port == 22 or (from_port and from_port <= 22 <= to_port):
                    for range in perm.get("IpRanges", []):
                        if range.get("CidrIp") == "0.0.0.0/0":
                            findings.append({
                                "resource_id": sg["GroupId"],
                                "finding_type": "Open SSH Port",
                                "severity": "high",
                                "description": f"Security Group '{sg['GroupName']}' allows SSH from 0.0.0.0/0.",
                                "remediation": "Restrict SSH access to specific CIDR ranges."
                            })

    except Exception as e:
        logger.error(f"Basic security checks failed: {e}")
        
    return findings

