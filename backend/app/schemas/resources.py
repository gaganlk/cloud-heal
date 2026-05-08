from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class ResourceResponse(BaseModel):
    id: int
    resource_id: str
    resource_type: str
    name: str
    region: Optional[str] = None
    status: str
    provider: str
    tags: Optional[Dict] = {}
    extra_metadata: Optional[Dict] = {}
    cpu_usage: float
    memory_usage: float
    created_at: datetime

    class Config:
        from_attributes = True


class ScanStatus(BaseModel):
    credential_id: int
    status: str
    resource_count: int
    last_scan: Optional[datetime] = None
    message: str
