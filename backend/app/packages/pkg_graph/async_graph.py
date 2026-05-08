"""
Updated async graph engine with K8s topology discovery.
Adds: real Kubernetes pod/service dependency mapping
      on top of existing NetworkX graph computation.
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import networkx as nx

logger = logging.getLogger(__name__)


# ── Kubernetes Topology Discovery ─────────────────────────────────────────────

async def discover_k8s_topology(namespace: str = "default") -> Dict[str, Any]:
    """
    Discover Kubernetes pods, services, deployments and build dependency graph.
    Works both in-cluster (production) and with local kubeconfig (development).

    Returns dict with:
      nodes: {node_id: {"type": ..., "status": ..., ...}}
      edges: [{"source": ..., "target": ..., "type": ...}]
    """
    try:
        from kubernetes import client as k8s_client, config as k8s_config

        # Try in-cluster config first (running inside K8s pod)
        try:
            k8s_config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except k8s_config.ConfigException:
            # Fall back to local kubeconfig
            kubeconfig = os.getenv("KUBECONFIG")
            k8s_config.load_kube_config(config_file=kubeconfig)
            logger.info("Loaded local kubeconfig")

        v1 = k8s_client.CoreV1Api()
        apps_v1 = k8s_client.AppsV1Api()

        nodes: Dict[str, Dict] = {}
        edges: List[Dict] = []

        loop = asyncio.get_running_loop()

        # Fetch pods and services in parallel
        pods_resp, svcs_resp, deps_resp = await asyncio.gather(
            loop.run_in_executor(None, lambda: v1.list_namespaced_pod(namespace)),
            loop.run_in_executor(None, lambda: v1.list_namespaced_service(namespace)),
            loop.run_in_executor(None, lambda: apps_v1.list_namespaced_deployment(namespace)),
        )

        # ── Pods ──────────────────────────────────────────────────────────
        for pod in pods_resp.items:
            pod_id = f"pod/{pod.metadata.name}"
            nodes[pod_id] = {
                "type": "k8s_pod",
                "name": pod.metadata.name,
                "status": pod.status.phase or "Unknown",
                "node": pod.spec.node_name,
                "labels": dict(pod.metadata.labels or {}),
                "containers": [c.name for c in (pod.spec.containers or [])],
                "restart_count": sum(
                    cs.restart_count for cs in (pod.status.container_statuses or [])
                    if cs.restart_count
                ),
                "namespace": namespace,
            }

        # ── Services → Pods edges ─────────────────────────────────────────
        for svc in svcs_resp.items:
            svc_id = f"svc/{svc.metadata.name}"
            nodes[svc_id] = {
                "type": "k8s_service",
                "name": svc.metadata.name,
                "status": "active",
                "cluster_ip": svc.spec.cluster_ip,
                "ports": [f"{p.port}/{p.protocol}" for p in (svc.spec.ports or [])],
                "selector": dict(svc.spec.selector or {}),
                "namespace": namespace,
            }

            # Build service-to-pod edges by matching selectors
            if svc.spec.selector:
                for pod in pods_resp.items:
                    pod_labels = dict(pod.metadata.labels or {})
                    if all(pod_labels.get(k) == v for k, v in svc.spec.selector.items()):
                        edges.append({
                            "source": svc_id,
                            "target": f"pod/{pod.metadata.name}",
                            "type": "routes_to",
                        })

        # ── Deployments → Pods edges ──────────────────────────────────────
        for dep in deps_resp.items:
            dep_id = f"deploy/{dep.metadata.name}"
            nodes[dep_id] = {
                "type": "k8s_deployment",
                "name": dep.metadata.name,
                "status": "active",
                "replicas": dep.spec.replicas,
                "ready_replicas": dep.status.ready_replicas or 0,
                "selector": dict((dep.spec.selector.match_labels or {}) if dep.spec.selector else {}),
                "namespace": namespace,
            }

            # Deployment → managed pods
            if dep.spec.selector and dep.spec.selector.match_labels:
                for pod in pods_resp.items:
                    pod_labels = dict(pod.metadata.labels or {})
                    if all(pod_labels.get(k) == v for k, v in dep.spec.selector.match_labels.items()):
                        edges.append({
                            "source": dep_id,
                            "target": f"pod/{pod.metadata.name}",
                            "type": "manages",
                        })

        logger.info(
            f"K8s topology discovered: {len(nodes)} nodes, {len(edges)} edges "
            f"in namespace '{namespace}'"
        )
        return {"nodes": nodes, "edges": edges, "namespace": namespace}

    except ImportError:
        logger.warning("kubernetes package not installed. Run: pip install kubernetes")
        return {"nodes": {}, "edges": [], "namespace": namespace, "error": "kubernetes package not available"}
    except Exception as e:
        logger.error(f"K8s topology discovery failed: {e}")
        return {"nodes": {}, "edges": [], "namespace": namespace, "error": str(e)}


# ── NetworkX Graph Operations ─────────────────────────────────────────────────

def build_dependency_graph(resources: List[Dict], edges: List[Dict]) -> nx.DiGraph:
    """
    Build a directed dependency graph from cloud resources and their relationships.
    Returns a networkx DiGraph for propagation analysis.
    """
    G = nx.DiGraph()

    for r in resources:
        G.add_node(
            r["resource_id"],
            name=r.get("name", r["resource_id"]),
            resource_type=r.get("resource_type", "unknown"),
            provider=r.get("provider", "unknown"),
            status=r.get("status", "unknown"),
            cpu_usage=r.get("cpu_usage", 0.0),
            memory_usage=r.get("memory_usage", 0.0),
        )

    for edge in edges:
        src = edge.get("source_id") or edge.get("source")
        tgt = edge.get("target_id") or edge.get("target")
        etype = edge.get("edge_type") or edge.get("type", "depends_on")
        weight = edge.get("weight", 1.0)

        if src in G and tgt in G:
            G.add_edge(src, tgt, edge_type=etype, weight=weight)

    return G


def validate_graph_edges(G: nx.DiGraph) -> List[str]:
    """
    Validate graph integrity — returns list of error strings.
    Checks: no self-loops, no edges to non-existent nodes.
    """
    errors = []
    for src, tgt in G.edges():
        if src == tgt:
            errors.append(f"Self-loop detected: {src}")
        if src not in G.nodes:
            errors.append(f"Edge source not a node: {src}")
        if tgt not in G.nodes:
            errors.append(f"Edge target not a node: {tgt}")
    return errors


def find_critical_path(G: nx.DiGraph, failed_node: str) -> List[str]:
    """
    Find all nodes upstream of the failed node (failure propagation path).
    Returns list of affected node IDs sorted by impact.
    """
    if failed_node not in G:
        return []
    # Nodes that depend on failed_node (reverse reachability)
    affected = list(nx.ancestors(G, failed_node))
    # Sort by distance from failed_node (closer = more immediately affected)
    try:
        paths = {n: nx.shortest_path_length(G, n, failed_node) for n in affected}
        return sorted(affected, key=lambda n: paths.get(n, 999))
    except Exception:
        return affected


async def build_full_topology(
    resources: List[Dict],
    db_edges: List[Dict],
    include_k8s: bool = False,
    k8s_namespace: str = "default",
) -> Dict[str, Any]:
    """
    Build the complete dependency graph combining:
    - Cloud resources from AWS/GCP/Azure
    - DB-stored graph edges
    - K8s topology (optional)
    """
    G = build_dependency_graph(resources, db_edges)
    k8s_data = {}

    if include_k8s:
        k8s_data = await discover_k8s_topology(k8s_namespace)
        # Add K8s nodes and edges to the graph
        for nid, ndata in k8s_data.get("nodes", {}).items():
            G.add_node(nid, **ndata)
        for edge in k8s_data.get("edges", []):
            src = edge.get("source")
            tgt = edge.get("target")
            if src and tgt:
                G.add_edge(src, tgt, edge_type=edge.get("type", "k8s_link"), weight=1.0)

    errors = validate_graph_edges(G)
    if errors:
        logger.warning(f"Graph validation errors: {errors}")

    return {
        "nodes": [{"id": n, **G.nodes[n]} for n in G.nodes],
        "edges": [{"source": u, "target": v, **G.edges[u, v]} for u, v in G.edges],
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "validation_errors": errors,
        "k8s_included": include_k8s,
    }
