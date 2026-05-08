"""
Root Cause Analysis (RCA) REST API router.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.rca_engine import RCAEngine

logger = logging.getLogger(__name__)
router = APIRouter()


class RCARequest(BaseModel):
    resource_id: str


@router.post("/analyze")
async def analyze_rca(req: RCARequest, db: AsyncSession = Depends(get_db)):
    """
    Perform Root Cause Analysis for a given resource.
    Traverses the dependency graph to find the true root cause.
    """
    report = await RCAEngine.analyze(req.resource_id, db)
    return report.to_dict()


@router.get("/analyze/{resource_id}")
async def analyze_rca_get(resource_id: str, db: AsyncSession = Depends(get_db)):
    """GET variant — convenient for direct links from the UI."""
    report = await RCAEngine.analyze(resource_id, db)
    return report.to_dict()
