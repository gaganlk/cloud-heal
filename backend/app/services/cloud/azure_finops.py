import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List
from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition, QueryTimePeriod, QueryDataset, QueryAggregation, QueryGrouping
)

logger = logging.getLogger(__name__)

def get_azure_costs(credentials: dict, days: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch historical cost data from Azure Cost Management.
    """
    try:
        subscription_id = credentials.get("subscription_id")
        az_creds = ClientSecretCredential(
            tenant_id=credentials.get("tenant_id"),
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
        )
        client = CostManagementClient(az_creds)
        
        end = datetime.now()
        start = end - timedelta(days=days)
        
        scope = f"/subscriptions/{subscription_id}"
        query = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(from_property=start, to=end),
            dataset=QueryDataset(
                granularity="Daily",
                aggregation={
                    "totalCost": QueryAggregation(name="PreTaxCost", function="Sum")
                },
                grouping=[
                    QueryGrouping(type="Dimension", name="ServiceName")
                ]
            )
        )
        
        response = client.query.usage(scope, query)
        
        results = []
        # Azure Cost Management returns data in a table-like format (Rows)
        # Column order usually: PreTaxCost, ServiceName, UsageDate, Currency
        columns = [c.name for c in response.columns]
        for row in response.rows:
            data = dict(zip(columns, row))
            results.append({
                "date": str(data.get("UsageDate", "")),
                "service": data.get("ServiceName", "Unknown"),
                "amount": float(data.get("PreTaxCost", 0.0)),
                "currency": data.get("Currency", "USD")
            })
            
        return results
    except Exception as e:
        logger.error(f"Failed to fetch Azure costs: {e}")
        return []

def get_azure_recommendations(credentials: dict) -> List[Dict[str, Any]]:
    """
    Fetch Azure Advisor recommendations.
    (Simplified: Requires azure-mgmt-advisor SDK which I'll add if needed, 
    but for now I'll stub it with empty list or basic logic).
    """
    # Azure Advisor integration would go here
    return []
