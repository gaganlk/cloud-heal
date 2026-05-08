"""
Root Cause Analysis (RCA) Engine.
Traverses the resource dependency graph to identify true root causes of failures,
suppressing "alert storms" by healing only the upstream root instead of every affected node.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class RCANode:
    resource_id: str
    resource_name: str
    resource_type: str
    provider: str
    status: str
    cpu_usage: float
    memory_usage: float
    risk_score: float
    is_root_cause: bool = False
    is_affected: bool = False
    causal_distance: int = 0  # hops from root


@dataclass
class RCAReport:
    target_resource_id: str
    root_cause_id: Optional[str]
    root_cause_name: Optional[str]
    causal_chain: List[str] = field(default_factory=list)
    blast_radius: List[str] = field(default_factory=list)
    affected_nodes: List[Dict] = field(default_factory=list)
    root_nodes: List[Dict] = field(default_factory=list)
    analysis_method: str = "graph_traversal"
    confidence_score: float = 0.0
    recommendation: str = ""
    analyzed_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        return {
            "target_resource_id": self.target_resource_id,
            "root_cause_id": self.root_cause_id,
            "root_cause_name": self.root_cause_name,
            "causal_chain": self.causal_chain,
            "blast_radius": self.blast_radius,
            "affected_nodes": self.affected_nodes,
            "root_nodes": self.root_nodes,
            "analysis_method": self.analysis_method,
            "confidence_score": self.confidence_score,
            "recommendation": self.recommendation,
            "analyzed_at": self.analyzed_at,
        }


class RCAEngine:
    """
    Graph-based Root Cause Analysis using networkx.
    Algorithm:
      1. Build directed dependency graph from resource edges
      2. From the failing node, traverse UPSTREAM (reverse edges)
      3. Find the furthest ancestor that is ALSO failing/degraded = root cause
      4. Map downstream nodes = blast radius
    """

    @staticmethod
    async def analyze(target_resource_id: str, db) -> RCAReport:
        """
        Perform RCA on a resource. Returns full RCAReport with causal chain.
        """
        try:
            import networkx as nx
        except ImportError:
            raise RuntimeError("networkx not installed: pip install networkx")

        report = RCAReport(target_resource_id=target_resource_id)

        try:
            # Load graph from DB
            nodes_data, edges_data = await RCAEngine._load_graph_data(db)

            if not nodes_data:
                report.recommendation = "No graph data available. Run a cloud scan first."
                return report

            # Build directed graph (A → B means A depends on B / A routes through B)
            G = nx.DiGraph()
            node_map: Dict[str, dict] = {}

            for n in nodes_data:
                G.add_node(n["resource_id"], **n)
                node_map[n["resource_id"]] = n

            for e in edges_data:
                G.add_edge(e["source_id"], e["target_id"], edge_type=e.get("edge_type", "depends_on"))

            if target_resource_id not in G:
                report.recommendation = f"Resource {target_resource_id} not found in topology graph."
                return report

            # ── Step 1: Find upstream ancestors (potential root causes) ──────
            # Reverse graph: follow edges in reverse to find what THIS node depends on
            reverse_G = G.reverse()
            ancestors: Set[str] = nx.ancestors(reverse_G, target_resource_id)
            ancestors.add(target_resource_id)

            # ── Step 2: Score each ancestor by failure likelihood ────────────
            def failure_score(node_id: str) -> float:
                n = node_map.get(node_id, {})
                score = 0.0
                cpu = n.get("cpu_usage", 0) or 0
                mem = n.get("memory_usage", 0) or 0
                risk = n.get("risk_score", 0) or 0
                status = (n.get("status", "running") or "running").lower()

                if status in ("stopped", "terminated", "failed", "error", "deallocated"):
                    score += 60
                score += min(cpu / 100, 1.0) * 20
                score += min(mem / 100, 1.0) * 10
                score += min(risk / 100, 1.0) * 10
                return score

            # The root cause is the highest-scoring ancestor with no incoming edges
            # from other failing nodes (i.e., it is truly "first" in the failure chain)
            root_candidates = []
            for ancestor_id in ancestors:
                if ancestor_id == target_resource_id:
                    continue
                score = failure_score(ancestor_id)
                if score > 10:  # Only flag nodes that show degradation
                    root_candidates.append((score, ancestor_id))

            root_candidates.sort(reverse=True)

            # ── Step 3: Build causal chain ───────────────────────────────────
            causal_chain = []
            root_cause_id = None
            root_cause_name = None

            if root_candidates:
                root_cause_id = root_candidates[0][1]
                root_n = node_map.get(root_cause_id, {})
                root_cause_name = root_n.get("name", root_cause_id)

                # Find shortest path from root → target
                try:
                    path = nx.shortest_path(G, source=root_cause_id, target=target_resource_id)
                    causal_chain = path
                except nx.NetworkXNoPath:
                    causal_chain = [root_cause_id, target_resource_id]

            else:
                # No upstream failures — target IS the root cause
                root_cause_id = target_resource_id
                root_n = node_map.get(target_resource_id, {})
                root_cause_name = root_n.get("name", target_resource_id)
                causal_chain = [target_resource_id]

            # ── Step 4: Map blast radius (downstream affected) ──────────────
            descendants = nx.descendants(G, target_resource_id)
            blast_radius = list(descendants)

            # ── Step 5: Build report ─────────────────────────────────────────
            confidence = min(100, failure_score(root_cause_id) * 1.5) if root_cause_id else 50

            affected_nodes = [
                {
                    "resource_id": nid,
                    "name": node_map.get(nid, {}).get("name", nid),
                    "status": node_map.get(nid, {}).get("status", "unknown"),
                    "risk_score": node_map.get(nid, {}).get("risk_score", 0),
                }
                for nid in blast_radius
            ]

            root_nodes = [
                {
                    "resource_id": rid,
                    "name": node_map.get(rid, {}).get("name", rid),
                    "score": score,
                    "status": node_map.get(rid, {}).get("status", "unknown"),
                }
                for score, rid in root_candidates[:3]
            ]

            # Recommendation
            if root_cause_id == target_resource_id:
                recommendation = (
                    f"This resource appears to be a **self-originated failure**. "
                    f"Trigger a healing action (restart/scale) directly on this node. "
                    f"No upstream root cause detected."
                )
            else:
                recommendation = (
                    f"Root cause identified: **{root_cause_name}**. "
                    f"Heal the root cause first to prevent healing {len(blast_radius)} downstream node(s). "
                    f"Causal path: {' → '.join(causal_chain[:5])}."
                )

            report.root_cause_id = root_cause_id
            report.root_cause_name = root_cause_name
            report.causal_chain = causal_chain
            report.blast_radius = blast_radius
            report.affected_nodes = affected_nodes[:20]
            report.root_nodes = root_nodes
            report.confidence_score = round(confidence, 1)
            report.recommendation = recommendation

        except Exception as e:
            logger.error(f"RCA analysis failed: {e}")
            report.recommendation = f"RCA analysis error: {e}"

        return report

    @staticmethod
    async def _load_graph_data(db):
        """Load nodes + edges from the graph tables."""
        from sqlalchemy import text

        try:
            # Load resources
            node_result = await db.execute(
                text("""
                    SELECT resource_id, name, resource_type, provider, status, 
                           cpu_usage, memory_usage, risk_score
                    FROM cloud_resources
                    LIMIT 500
                """)
            )
            nodes = [dict(row._mapping) for row in node_result]

            # Load edges
            edge_result = await db.execute(
                text("""
                    SELECT source_id, target_id, edge_type
                    FROM graph_edges
                    LIMIT 1000
                """)
            )
            edges = [dict(row._mapping) for row in edge_result]
            return nodes, edges

        except Exception as e:
            logger.warning(f"Graph data load failed (tables may not exist yet): {e}")
            return [], []
