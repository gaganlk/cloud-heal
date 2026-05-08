from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from datetime import datetime
import networkx as nx

from app.db.database import get_db
from app.db.models import CloudCredential, CloudResource, EventLog, GraphEdge, User, Tenant
from app.schemas.resources import ResourceResponse, ScanStatus
from app.services.encryption import decrypt_credentials
from app.services.graph_engine import _auto_generate_dependencies
from app.api.endpoints.auth import get_current_user
from sqlalchemy import select, delete, func
from app.services.intelligence_engine import IntelligenceEngine
from app.services.websocket_manager import manager

router = APIRouter()


async def _perform_scan(credential_id: int):
    """Background scan task — Async-first PostgreSQL."""
    from app.db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        cred = None
        try:
            result = await db.execute(select(CloudCredential).where(CloudCredential.id == credential_id))
            cred = result.scalar_one_or_none()
            if not cred:
                return

            cred.scan_status = "scanning"
            await db.commit()

            raw = decrypt_credentials(cred.encrypted_data)

            if cred.provider == "aws":
                from app.services.cloud.aws_scanner import scan_aws_resources
                resources = await scan_aws_resources(raw, broadcast_callback=manager.broadcast)
            elif cred.provider == "gcp":
                from app.services.cloud.gcp_scanner import scan_gcp_resources
                resources = await scan_gcp_resources(raw, broadcast_callback=manager.broadcast)
            elif cred.provider == "azure":
                from app.services.cloud.azure_scanner import scan_azure_resources
                resources = await scan_azure_resources(raw, broadcast_callback=manager.broadcast)
            else:
                resources = []

            # ── Clear old data (Tenant aware) ──────────────────────────────────
            await db.execute(delete(CloudResource).where(CloudResource.credential_id == credential_id))
            await db.execute(delete(GraphEdge).where(GraphEdge.credential_id == credential_id))

            stored = []
            for r in resources:
                obj = CloudResource(
                    tenant_id=cred.tenant_id,
                    credential_id=credential_id,
                    resource_id=r["resource_id"],
                    resource_type=r["resource_type"],
                    name=r["name"],
                    region=r.get("region"),
                    status=r["status"],
                    provider=r["provider"],
                    tags=r.get("tags", {}),
                    extra_metadata=r.get("extra_metadata", {}),
                    cpu_usage=r.get("cpu_usage", 0.0),
                    memory_usage=r.get("memory_usage", 0.0),
                    network_usage=r.get("network_usage", 0.0),
                )
                db.add(obj)
                stored.append(r)

            await db.flush()

            # Auto-generate dependency graph
            G = nx.DiGraph()
            for r in stored:
                G.add_node(r["resource_id"])
            _auto_generate_dependencies(G, stored)

            for src, tgt, attrs in G.edges(data=True):
                db.add(GraphEdge(
                    credential_id=credential_id,
                    source_id=src,
                    target_id=tgt,
                    edge_type=attrs.get("edge_type", "depends_on"),
                    weight=attrs.get("weight", 1.0),
                ))

            cred.last_scan = datetime.utcnow()
            cred.scan_status = "completed"
            
            db.add(EventLog(
                tenant_id=cred.tenant_id,
                user_id=cred.user_id,
                event_type="scan_completed",
                description=f"Scan completed for {cred.provider.upper()} '{cred.name}': {len(resources)} resources",
                severity="info",
            ))
            await db.commit()

            # Broadcast completion to UI
            await manager.broadcast({
                "type": "scan_completed",
                "data": {
                    "credential_id": credential_id,
                    "provider": cred.provider,
                    "count": len(resources)
                }
            })

            # 4. Trigger Intelligence Scan
            await IntelligenceEngine.run_intelligence_scan(db, credential_id)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Scan error: {e}")
            if cred:
                cred.scan_status = "failed"
                db.add(EventLog(
                    tenant_id=cred.tenant_id,
                    user_id=cred.user_id,
                    event_type="scan_failed",
                    description=f"Scan failed for {cred.provider.upper()}: {str(e)[:200]}",
                    severity="error",
                ))
                await db.commit()


@router.post("/scan/{credential_id}")
async def trigger_scan(
    credential_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CloudCredential).filter(
        CloudCredential.id == credential_id,
        CloudCredential.user_id == current_user.id,
    ))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    # Guard: prevent duplicate concurrent scans
    if cred.scan_status == "scanning":
        return {
            "message": f"Scan already in progress for {cred.provider.upper()} — {cred.name}",
            "credential_id": credential_id,
            "status": "scanning",
        }

    background_tasks.add_task(_perform_scan, credential_id)
    return {
        "message": f"Scan started for {cred.provider.upper()} — {cred.name}",
        "credential_id": credential_id,
        "status": "scanning",
    }


@router.get("/resources/{credential_id}", response_model=List[ResourceResponse])
async def get_resources(
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
    return res_result.scalars().all()


@router.get("/all-resources")
async def get_all_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    creds_result = await db.execute(select(CloudCredential).filter(
        CloudCredential.user_id == current_user.id,
        CloudCredential.is_active == True,
    ))
    creds = creds_result.scalars().all()

    result = []
    for cred in creds:
        res_result = await db.execute(select(CloudResource).filter(CloudResource.credential_id == cred.id))
        for r in res_result.scalars().all():
            result.append({
                "id": r.id,
                "resource_id": r.resource_id,
                "resource_type": r.resource_type,
                "name": r.name,
                "region": r.region,
                "status": r.status,
                "provider": r.provider,
                "tags": r.tags,
                "extra_metadata": r.extra_metadata,
                "cpu_usage": r.cpu_usage,
                "memory_usage": r.memory_usage,
                "network_usage": r.network_usage,
                "credential_id": cred.id,
                "credential_name": cred.name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
    return result


@router.get("/status/{credential_id}", response_model=ScanStatus)
async def get_scan_status(
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

    from sqlalchemy import func
    count_result = await db.execute(select(func.count(CloudResource.id)).filter(CloudResource.credential_id == credential_id))
    count = count_result.scalar() or 0
    
    return ScanStatus(
        credential_id=credential_id,
        status=cred.scan_status or "never",
        resource_count=count,
        last_scan=cred.last_scan,
        message=f"Found {count} resources" if count > 0 else "No scan performed yet",
    )
