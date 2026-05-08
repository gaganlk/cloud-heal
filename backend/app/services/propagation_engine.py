import networkx as nx
from typing import List, Dict, Any, Set
from app.services.graph_engine import calculate_node_risk


def simulate_failure_propagation(
    G: nx.DiGraph,
    failed_node_id: str,
    resources: List[Dict],
    max_depth: int = 10,
) -> Dict[str, Any]:
    """
    BFS cascade simulation from a failed node.
    Traverses both dependents (successors) and upward dependencies (predecessors at depth=0).
    """
    resource_map = {r["resource_id"]: r for r in resources}

    affected: Set[str] = set()
    paths: List[List[str]] = []
    depths: Dict[str, int] = {failed_node_id: 0}
    queue = [(failed_node_id, [failed_node_id])]

    while queue:
        current, path = queue.pop(0)
        d = depths[current]
        if d >= max_depth:
            continue

        # Forward cascade: services that depend on current
        for nbr in G.successors(current):
            if nbr not in affected and nbr != failed_node_id:
                affected.add(nbr)
                new_path = path + [nbr]
                paths.append(new_path)
                depths[nbr] = d + 1
                queue.append((nbr, new_path))

        # At origin: also surface upward (services this node depends on — now degraded)
        if d == 0:
            for nbr in G.predecessors(current):
                if nbr not in affected and nbr != failed_node_id:
                    affected.add(nbr)
                    new_path = path + [nbr]
                    paths.append(new_path)
                    depths[nbr] = d + 1
                    queue.append((nbr, new_path))

    impact_score = _calculate_impact_score(failed_node_id, list(affected), G, resource_map, depths)

    if impact_score >= 80:
        severity = "critical"
    elif impact_score >= 60:
        severity = "high"
    elif impact_score >= 40:
        severity = "medium"
    else:
        severity = "low"

    cascade_levels: Dict[str, List[str]] = {}
    for node, depth in depths.items():
        if node != failed_node_id:
            key = str(depth)
            cascade_levels.setdefault(key, []).append(node)

    failed_res = resource_map.get(failed_node_id, {})

    return {
        "failed_node": failed_node_id,
        "failed_node_name": failed_res.get("name", failed_node_id),
        "failed_node_type": failed_res.get("resource_type", "unknown"),
        "failed_node_provider": failed_res.get("provider", "unknown"),
        "affected_nodes": list(affected),
        "affected_node_details": [
            {
                "id": n,
                "name": resource_map.get(n, {}).get("name", n),
                "resource_type": resource_map.get(n, {}).get("resource_type", "unknown"),
                "provider": resource_map.get(n, {}).get("provider", "unknown"),
                "depth": depths.get(n, 0),
            }
            for n in affected
        ],
        "propagation_paths": paths[:10],
        "cascade_levels": cascade_levels,
        "impact_score": impact_score,
        "severity": severity,
        "total_affected": len(affected),
        "total_resources": G.number_of_nodes(),
        "healing_suggestions": _generate_healing_suggestions(
            failed_node_id, list(affected), resource_map, severity
        ),
    }


def _calculate_impact_score(
    failed_node: str,
    affected: List[str],
    G: nx.DiGraph,
    resource_map: Dict,
    depths: Dict,
) -> float:
    total = G.number_of_nodes()
    score = (len(affected) / total * 50) if total else 0

    max_d = max(depths.values(), default=0)
    score += min(20, max_d * 4)

    critical_types = {
        "load_balancer", "rds_instance", "cloud_sql", "sql_database",
        "gke_cluster", "aks_cluster",
    }
    failed_type = resource_map.get(failed_node, {}).get("resource_type", "")
    score += 20 if failed_type in critical_types else 10

    if affected:
        avg_cpu = sum(resource_map.get(n, {}).get("cpu_usage", 50) for n in affected) / len(affected)
        score += (avg_cpu / 100) * 10

    return min(100.0, round(score, 2))


def _generate_healing_suggestions(
    failed_node: str,
    affected: List[str],
    resource_map: Dict,
    severity: str,
) -> List[Dict]:
    suggestions = []
    failed_res = resource_map.get(failed_node, {})
    rtype = failed_res.get("resource_type", "")

    action_map = {
        "load_balancer": ("reroute", "Redirect traffic to healthy load balancer endpoint"),
        "rds_instance": ("failover", "Trigger database failover to standby replica"),
        "cloud_sql": ("failover", "Trigger Cloud SQL failover"),
        "sql_database": ("failover", "Trigger Azure SQL failover"),
        "gke_cluster": ("scale_up", "Scale up k8s node pool to absorb load"),
        "aks_cluster": ("scale_up", "Scale up AKS node pool"),
    }
    primary_action, primary_desc = action_map.get(rtype, ("restart", f"Restart failed {rtype}"))

    suggestions.append({
        "priority": 1,
        "action": primary_action,
        "target": failed_node,
        "target_name": failed_res.get("name", failed_node),
        "description": primary_desc,
        "estimated_time": "1-3 minutes",
    })

    if severity in ("high", "critical") and rtype not in ("load_balancer",):
        suggestions.append({
            "priority": 2,
            "action": "reroute",
            "target": failed_node,
            "target_name": failed_res.get("name", failed_node),
            "description": "Divert traffic away from affected node",
            "estimated_time": "30 seconds",
        })

    for aff_id in list(affected)[:2]:
        aff_res = resource_map.get(aff_id, {})
        suggestions.append({
            "priority": 3,
            "action": "isolate",
            "target": aff_id,
            "target_name": aff_res.get("name", aff_id),
            "description": f"Isolate {aff_res.get('name', aff_id)} to stop cascade",
            "estimated_time": "< 1 minute",
        })

    return suggestions[:5]
