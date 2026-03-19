from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.dashboard_service import (
    ask_ai_query,
    get_dashboard_heatmap,
    get_dashboard_stats,
    get_high_risk_tenders,
    get_top_risk_suppliers,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=dict)
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """KPI cards — totals and deltas vs last 30 days."""
    return await get_dashboard_stats(db)


@router.get("/heatmap", response_model=dict)
async def dashboard_heatmap(db: AsyncSession = Depends(get_db)):
    """County risk summary for the map widget."""
    items = await get_dashboard_heatmap(db)
    return {"items": items}


@router.get("/top-risk-suppliers", response_model=dict)
async def top_risk_suppliers(db: AsyncSession = Depends(get_db)):
    """Top 5 suppliers by risk score."""
    items = await get_top_risk_suppliers(db)
    return {"items": items}


@router.get("/high-risk-tenders", response_model=dict)
async def high_risk_tenders(db: AsyncSession = Depends(get_db)):
    """Top 10 high/critical risk tenders for the dashboard table."""
    items = await get_high_risk_tenders(db)
    return {"items": items}


class AIQueryRequest(BaseModel):
    question: str


@router.post("/ai-query", response_model=dict)
async def ai_query(payload: AIQueryRequest):
    """Natural language query answered by Claude."""
    return await ask_ai_query(payload.question)
