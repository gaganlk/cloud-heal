from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import CloudCredential, EventLog, User
from app.schemas.credentials import CredentialCreate, CredentialResponse
from app.services.encryption import encrypt_credentials, decrypt_credentials
from app.api.endpoints.auth import get_current_user

router = APIRouter()


@router.post("/", response_model=CredentialResponse)
async def add_credential(
    data: CredentialCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encrypted = encrypt_credentials(data.credentials)
    cred = CloudCredential(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        provider=data.provider,
        name=data.name,
        encrypted_data=encrypted,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)

    db.add(EventLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        event_type="credential_added",
        description=f"Added {data.provider.upper()} credentials: {data.name}",
        severity="info",
    ))
    await db.commit()
    
    # ── Next Level: Trigger immediate scan ──────────────────────────────────
    from app.api.endpoints.scanner import _perform_scan
    background_tasks.add_task(_perform_scan, cred.id)
    
    return cred


@router.get("/", response_model=List[CredentialResponse])
async def list_credentials(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CloudCredential).filter(
        CloudCredential.user_id == current_user.id,
        CloudCredential.is_active == True,
    ))
    return result.scalars().all()


@router.delete("/{credential_id}")
async def delete_credential(
    credential_id: int,
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
    cred.is_active = False
    await db.commit()
    return {"message": "Credential removed"}


@router.post("/{credential_id}/validate")
async def validate_credential(
    credential_id: int,
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

    try:
        raw = decrypt_credentials(cred.encrypted_data)
        if cred.provider == "aws":
            from app.services.cloud.aws_scanner import validate_aws_credentials
            valid = validate_aws_credentials(raw)
        elif cred.provider == "gcp":
            from app.services.cloud.gcp_scanner import validate_gcp_credentials
            valid = validate_gcp_credentials(raw)
        elif cred.provider == "azure":
            from app.services.cloud.azure_scanner import validate_azure_credentials
            valid = validate_azure_credentials(raw)
        else:
            valid = False
    except Exception as e:
        return {"credential_id": credential_id, "valid": False, "message": str(e)}

    if valid:
        # Trigger immediate scan on successful validation
        from app.api.endpoints.scanner import _perform_scan
        background_tasks.add_task(_perform_scan, cred.id)

    return {
        "credential_id": credential_id,
        "provider": cred.provider,
        "valid": valid,
        "message": (
            "✅ Credentials valid — connected to real cloud"
            if valid
            else "ℹ️  Could not connect to cloud API — demo data will be used"
        ),
    }

