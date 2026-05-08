import boto3
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def get_aws_costs(credentials: dict, days: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch historical cost data from AWS Cost Explorer.
    Requires 'ce:GetCostAndUsage' permission.
    """
    try:
        session = boto3.Session(
            aws_access_key_id=credentials.get("access_key_id"),
            aws_secret_access_key=credentials.get("secret_access_key"),
            region_name=credentials.get("region", "us-east-1"),
        )
        ce = session.client("ce")
        
        end = datetime.now().date()
        start = end - timedelta(days=days)
        
        response = ce.get_cost_and_usage(
            TimePeriod={
                "Start": start.isoformat(),
                "End": end.isoformat()
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"}
            ]
        )
        
        results = []
        for day in response.get("ResultsByTime", []):
            date_str = day["TimePeriod"]["Start"]
            for group in day.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if amount > 0:
                    results.append({
                        "date": date_str,
                        "service": service,
                        "amount": amount,
                        "currency": group["Metrics"]["UnblendedCost"]["Unit"]
                    })
        
        return results
    except Exception as e:
        logger.error(f"Failed to fetch AWS costs: {e}")
        return []

def get_aws_recommendations(credentials: dict) -> List[Dict[str, Any]]:
    """
    Fetch AWS Cost Optimization Recommendations (Rightsizing).
    Requires 'ce:GetRightsizingRecommendation' permission.
    """
    try:
        session = boto3.Session(
            aws_access_key_id=credentials.get("access_key_id"),
            aws_secret_access_key=credentials.get("secret_access_key"),
            region_name=credentials.get("region", "us-east-1"),
        )
        ce = session.client("ce")
        
        response = ce.get_rightsizing_recommendation(
            Service="AmazonEC2",
            Configuration={
                "RecommendationTarget": "SAME_INSTANCE_FAMILY",
                "BenefitsConsidered": True
            }
        )
        
        recommendations = []
        for rec in response.get("RightsizingRecommendations", []):
            if rec["RightsizingType"] == "Modify":
                current = rec["ModifyRecommendationDetail"]["CurrentInstance"]
                target = rec["ModifyRecommendationDetail"]["TargetInstances"][0]
                savings = float(target["EstimatedMonthlySavings"])
                
                recommendations.append({
                    "resource_id": current["ResourceId"],
                    "recommendation_type": "rightsize",
                    "description": f"Change {current['ResourceName']} from {current['InstanceType']} to {target['InstanceType']}",
                    "potential_savings": savings
                })
            elif rec["RightsizingType"] == "Terminate":
                current = rec["TerminateRecommendationDetail"]["CurrentInstance"]
                savings = float(rec["TerminateRecommendationDetail"]["EstimatedMonthlySavings"])
                
                recommendations.append({
                    "resource_id": current["ResourceId"],
                    "recommendation_type": "idle",
                    "description": f"Terminate idle instance {current['ResourceName']} ({current['InstanceType']})",
                    "potential_savings": savings
                })
        
        return recommendations
    except Exception as e:
        logger.warning(f"Failed to fetch AWS cost recommendations: {e}")
        return []
