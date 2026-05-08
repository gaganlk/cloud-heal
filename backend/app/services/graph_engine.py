import networkx as nx
from typing import List, Dict, Any, Optional


def build_dependency_graph(resources: List[Dict], edges: List[Dict] = None) -> nx.DiGraph:
    """Build a directed dependency graph from cloud resources."""
    G = nx.DiGraph()

    for resource in resources:
        G.add_node(
            resource["resource_id"],
            label=resource["name"],
            resource_type=resource["resource_type"],
            provider=resource["provider"],
            status=resource.get("status", "unknown"),
            region=resource.get("region", "unknown"),
            cpu_usage=resource.get("cpu_usage", 0.0),
            memory_usage=resource.get("memory_usage", 0.0),
        )

    if edges:
        for edge in edges:
            if edge["source_id"] in G and edge["target_id"] in G:
                G.add_edge(
                    edge["source_id"],
                    edge["target_id"],
                    edge_type=edge.get("edge_type", "depends_on"),
                    weight=edge.get("weight", 1.0),
                )
    else:
        _auto_generate_dependencies(G, resources)

    return G


def _auto_generate_dependencies(G: nx.DiGraph, resources: List[Dict]):
    """Auto-generate logical cloud dependency edges."""
    resource_map = {r["resource_id"]: r for r in resources}

    # Group by type
    compute_ids = [r["resource_id"] for r in resources
                  if r["resource_type"] in ("ec2_instance", "compute_instance", "virtual_machine", "cloud_run", "cloud_function", "lambda_function", "azure_app_service", "azure_function", "ecs_cluster")]
    db_ids = [r["resource_id"] for r in resources
              if r["resource_type"] in ("rds_instance", "cloud_sql", "sql_database", "azure_sql", "azure_cosmos_db")]
    lb_ids = [r["resource_id"] for r in resources
              if r["resource_type"] in ("load_balancer", "azure_load_balancer")]
    cache_ids = [r["resource_id"] for r in resources
                 if r["resource_type"] in ("redis_cache", "azure_redis")]
    k8s_ids = [r["resource_id"] for r in resources
               if r["resource_type"] in ("gke_cluster", "aks_cluster", "eks_cluster")]
    storage_ids = [r["resource_id"] for r in resources
                   if r["resource_type"] in ("s3_bucket", "gcs_bucket", "storage_bucket", "azure_storage")]
    messaging_ids = [r["resource_id"] for r in resources
                  if r["resource_type"] in ("pubsub_topic", "sqs_queue", "sns_topic", "azure_service_bus")]

    # LB → compute/k8s
    for lb_id in lb_ids:
        for comp_id in compute_ids[:2]:
            G.add_edge(lb_id, comp_id, edge_type="routes_to", weight=1.0)
        for k8s_id in k8s_ids:
            G.add_edge(lb_id, k8s_id, edge_type="routes_to", weight=1.2)

    # Compute/K8s → DB
    for comp_id in compute_ids:
        for db_id in db_ids:
            G.add_edge(comp_id, db_id, edge_type="reads_from", weight=1.5)

    # Functions → Messaging
    for comp_id in compute_ids:
        r = resource_map.get(comp_id, {})
        if "function" in r.get("resource_type", ""):
            for m_id in messaging_ids:
                G.add_edge(comp_id, m_id, edge_type="triggers", weight=0.6)

    # Storage connections
    for comp_id in compute_ids:
        for storage_id in storage_ids:
            G.add_edge(comp_id, storage_id, edge_type="uses_storage", weight=0.8)



    # Worker → Storage
    for comp_id in compute_ids:
        r = resource_map.get(comp_id, {})
        if "worker" in r.get("name", "").lower():
            for storage_id in storage_ids:
                G.add_edge(comp_id, storage_id, edge_type="writes_to", weight=0.7)

    # ML/training → Storage
    for comp_id in compute_ids:
        r = resource_map.get(comp_id, {})
        if any(kw in r.get("name", "").lower() for kw in ("ml", "train", "batch")):
            for storage_id in storage_ids:
                G.add_edge(comp_id, storage_id, edge_type="reads_writes", weight=1.1)



def graph_to_dict(G: nx.DiGraph, resources: List[Dict]) -> Dict[str, Any]:
    """Convert NetworkX graph to React Flow compatible format."""
    resource_map = {r["resource_id"]: r for r in resources}

    nodes = []
    for node_id in G.nodes():
        attrs = G.nodes[node_id]
        resource = resource_map.get(node_id, {})
        cpu = resource.get("cpu_usage", attrs.get("cpu_usage", 0.0))
        memory = resource.get("memory_usage", attrs.get("memory_usage", 0.0))
        risk_score = calculate_node_risk(cpu, memory, attrs.get("status", "running"))

        nodes.append({
            "id": node_id,
            "label": attrs.get("label", node_id),
            "resource_type": attrs.get("resource_type", "unknown"),
            "provider": attrs.get("provider", "unknown"),
            "status": attrs.get("status", "unknown"),
            "region": attrs.get("region", "unknown"),
            "cpu_usage": cpu,
            "memory_usage": memory,
            "risk_score": risk_score,
            "data": {
                "extra_metadata": resource.get("extra_metadata", {}),
                "tags": resource.get("tags", {}),
            },
        })

    edges = []
    for i, (source, target, attrs) in enumerate(G.edges(data=True)):
        edges.append({
            "id": f"e-{i}",
            "source": source,
            "target": target,
            "edge_type": attrs.get("edge_type", "depends_on"),
            "weight": attrs.get("weight", 1.0),
        })

    return {"nodes": nodes, "edges": edges}


def calculate_node_risk(cpu: float, memory: float, status: str) -> float:
    """Return a 0–100 risk score for a node."""
    risk = 0.0

    # CPU → 0–40 pts
    if cpu >= 95:
        risk += 40
    elif cpu >= 85:
        risk += 30
    elif cpu >= 75:
        risk += 20
    elif cpu >= 65:
        risk += 12
    else:
        risk += (cpu / 65) * 10

    # Memory → 0–40 pts
    if memory >= 95:
        risk += 40
    elif memory >= 85:
        risk += 30
    elif memory >= 75:
        risk += 20
    elif memory >= 65:
        risk += 12
    else:
        risk += (memory / 65) * 10

    # Status → 0–20 pts
    status_risk = {
        "running": 0, "active": 0, "available": 0, "runnable": 0, "online": 0,
        "pending": 5, "stopping": 10, "stopped": 15, "terminated": 20,
        "error": 20, "failed": 20, "unknown": 8,
    }
    risk += status_risk.get((status or "unknown").lower(), 8)

    return min(100.0, round(risk, 2))
