from pydantic import BaseModel
from typing import List, Dict, Optional, Any


class GraphNode(BaseModel):
    id: str
    label: str
    resource_type: str
    provider: str
    status: str
    region: Optional[str] = None
    cpu_usage: float
    memory_usage: float
    risk_score: float
    data: Optional[Dict[str, Any]] = {}


class GraphEdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    weight: float


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdgeSchema]
    credential_id: int
