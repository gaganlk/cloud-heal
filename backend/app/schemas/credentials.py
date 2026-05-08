from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class AWSCredentials(BaseModel):
    access_key_id: str
    secret_access_key: str
    region: str = "us-east-1"


class GCPCredentials(BaseModel):
    project_id: str
    service_account_json: str


class AzureCredentials(BaseModel):
    subscription_id: str
    client_id: str
    client_secret: str
    tenant_id: str


class CredentialCreate(BaseModel):
    provider: str  # aws, gcp, azure
    name: str
    credentials: Dict[str, Any]


class CredentialResponse(BaseModel):
    id: int
    provider: str
    name: str
    is_active: bool
    last_scan: Optional[datetime] = None
    scan_status: Optional[str] = "never"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
