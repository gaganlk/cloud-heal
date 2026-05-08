from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import CloudCredential, CloudResource, GraphEdge, User
from app.services.graph_engine import build_dependency_graph, graph_to_dict
from app.api.endpoints.auth import get_current_user

router = APIRouter()


async def _get_graph_data(credential_ids: list, db: AsyncSession):
    all_resources, all_edges = [], []
    for cid in credential_ids:
        # Get resources
        res_result = await db.execute(select(CloudResource).filter(CloudResource.credential_id == cid))
        for r in res_result.scalars().all():
            all_resources.append({
                "resource_id": r.resource_id, "resource_type": r.resource_type,
                "name": r.name, "region": r.region, "status": r.status,
                "provider": r.provider, "tags": r.tags or {},
                "extra_metadata": r.extra_metadata or {},
                "cpu_usage": r.cpu_usage, "memory_usage": r.memory_usage,
            })
        # Get edges
        edge_result = await db.execute(select(GraphEdge).filter(GraphEdge.credential_id == cid))
        for e in edge_result.scalars().all():
            all_edges.append({
                "source_id": e.source_id, "target_id": e.target_id,
                "edge_type": e.edge_type, "weight": e.weight,
            })
    return all_resources, all_edges


@router.get("/{credential_id}")
async def get_graph(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cred_result = await db.execute(select(CloudCredential).filter(
        CloudCredential.id == credential_id,
        CloudCredential.user_id == current_user.id,
    ))
    cred = cred_result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    resources, edges = await _get_graph_data([credential_id], db)
    if not resources:
        raise HTTPException(status_code=404, detail="No resources found — run a scan first")

    G = build_dependency_graph(resources, edges)
    data = graph_to_dict(G, resources)
    data["credential_id"] = credential_id
    return data


@router.get("/all/combined")
async def get_combined_graph(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    creds_result = await db.execute(select(CloudCredential).filter(
        CloudCredential.user_id == current_user.id,
        CloudCredential.is_active == True,
    ))
    creds = creds_result.scalars().all()
    if not creds:
        return {"nodes": [], "edges": [], "credential_id": 0}

    resources, edges = await _get_graph_data([c.id for c in creds], db)
    if not resources:
        return {"nodes": [], "edges": [], "credential_id": 0}

    G = build_dependency_graph(resources, edges)
    data = graph_to_dict(G, resources)
    data["credential_id"] = 0
    return data
