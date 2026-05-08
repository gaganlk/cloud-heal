from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.db.database import get_db
from app.db.models import CloudCredential, CloudResource, GraphEdge, User
from app.services.graph_engine import build_dependency_graph
from app.services.propagation_engine import simulate_failure_propagation
from app.api.endpoints.auth import get_current_user

router = APIRouter()


class PropagationRequest(BaseModel):
    failed_node_id: str
    credential_id: int
    max_depth: Optional[int] = 10


@router.post("/simulate")
async def simulate_propagation(
    request: PropagationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CloudCredential).where(
        CloudCredential.id == request.credential_id,
        CloudCredential.user_id == current_user.id,
    ))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    res_result = await db.execute(select(CloudResource).where(
        CloudResource.credential_id == request.credential_id
    ))
    resources_db = res_result.scalars().all()
    if not resources_db:
        raise HTTPException(status_code=404, detail="No resources found — run a scan first")

    resources = [
        {
            "resource_id": r.resource_id, "resource_type": r.resource_type,
            "name": r.name, "region": r.region, "status": r.status,
            "provider": r.provider, "cpu_usage": r.cpu_usage, "memory_usage": r.memory_usage,
        }
        for r in resources_db
    ]

    edge_result = await db.execute(select(GraphEdge).where(GraphEdge.credential_id == request.credential_id))
    edges = [
        {"source_id": e.source_id, "target_id": e.target_id,
         "edge_type": e.edge_type, "weight": e.weight}
        for e in edge_result.scalars().all()
    ]

    G = build_dependency_graph(resources, edges)

    if request.failed_node_id not in G.nodes():
        raise HTTPException(
            status_code=400,
            detail=f"Node '{request.failed_node_id}' not found in graph",
        )

    return simulate_failure_propagation(G, request.failed_node_id, resources, request.max_depth)


@router.get("/resources/{credential_id}")
async def list_propagation_resources(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cred_result = await db.execute(select(CloudCredential).where(
        CloudCredential.id == credential_id,
        CloudCredential.user_id == current_user.id,
    ))
    cred = cred_result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    res_result = await db.execute(select(CloudResource).where(CloudResource.credential_id == credential_id))
    return [
        {
            "resource_id": r.resource_id, "name": r.name,
            "resource_type": r.resource_type, "provider": r.provider,
            "status": r.status, "cpu_usage": r.cpu_usage, "memory_usage": r.memory_usage,
        }
        for r in res_result.scalars().all()
    ]
