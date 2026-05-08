import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# CIS Benchmark Mapping
CIS_MAPPING = {
    "Public S3 Bucket": "CIS 2.1.1",
    "Unencrypted EBS Volume": "CIS 2.2.1",
    "Open SSH Port": "CIS 4.1",
    "Iam Policy": "CIS 1.2",
    "Sg Rules": "CIS 4.2",
    "Bucket Policy": "CIS 2.1.2",
    "Status": "Availability-1.0",
}

# Remediation Database
REMEDIATIONS = {
    "Public S3 Bucket": "Ensure 'Block Public Access' is enabled at the bucket level and the bucket policy does not allow 'Principal': '*'.",
    "Unencrypted EBS Volume": "Enable default EBS encryption for the region or re-create the volume from an encrypted snapshot.",
    "Open SSH Port": "Restrict Security Group ingress rules for port 22 to authorized CIDR blocks only (never 0.0.0.0/0).",
    "Iam Policy": "Review the historical drift timeline and revert unauthorized changes to the IAM policy document.",
    "Sg Rules": "Audit the recently added rules and remove any that do not align with the approved security baseline.",
    "Bucket Policy": "Restore the bucket policy to the last known good configuration and audit IAM permissions of the user who made the change.",
}


# Impact Analysis
IMPACT_CLASSIFICATION = {
    "critical": "Potential Data Exfiltration / Full System Compromise",
    "high": "Unauthorized Access / Privilege Escalation",
    "medium": "Policy Violation / Reduced Visibility",
    "low": "Non-compliant Configuration / Best Practice Deviation",
}

class ComplianceEngine:
    @staticmethod
    def calculate_risk_score(severity: str, asset_criticality: float = 1.0) -> float:
        """
        Calculate a risk score between 0 and 100.
        """
        severity_weights = {
            "critical": 95.0,
            "high": 75.0,
            "medium": 45.0,
            "low": 15.0
        }
        base_score = severity_weights.get(severity.lower(), 10.0)
        # Final score capped at 100
        return min(100.0, base_score * asset_criticality)

    @staticmethod
    def get_compliance_metadata(finding_type: str, severity: str) -> Dict[str, Any]:
        """
        Enrich a finding with CIS mapping, impact, and remediation.
        """
        return {
            "compliance_id": CIS_MAPPING.get(finding_type, "Custom-Policy"),
            "impact": IMPACT_CLASSIFICATION.get(severity.lower(), "Unknown Impact"),
            "remediation": REMEDIATIONS.get(finding_type, "Review enterprise security documentation for remediation steps."),
            "risk_score": ComplianceEngine.calculate_risk_score(severity)
        }

    @staticmethod
    def analyze_drift_impact(field: str, old_val: Any, new_val: Any) -> str:
        """Analyze the business/system impact of a specific field change."""
        impact_map = {
            "status": "Service Availability Impact",
            "iam_policy": "Security Boundary Change",
            "sg_rules": "Network Exposure Change",
            "bucket_policy": "Data Privacy Impact",
            "resource_type": "Cost & Performance Impact",
        }
        return impact_map.get(field, "Configuration Change")
