from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics_service import (
    get_analytics_kpis,
    get_daily_trend,
    get_risk_distribution,
    get_spending_trend,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/kpis", response_model=dict)
async def analytics_kpis(db: AsyncSession = Depends(get_db)):
    """Top-level KPI cards for the analytics page."""
    return await get_analytics_kpis(db)


@router.get("/spending-trend", response_model=dict)
async def spending_trend(
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    """Monthly budgeted vs actual vs flagged spend in millions KES."""
    items = await get_spending_trend(db, months=months)
    return {"items": items}


@router.get("/risk-distribution", response_model=dict)
async def risk_distribution(db: AsyncSession = Depends(get_db)):
    """Count of tenders per risk level."""
    return await get_risk_distribution(db)


@router.get("/daily-trend", response_model=dict)
async def daily_trend(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Daily risk level counts for TrendChart area chart."""
    items = await get_daily_trend(db, days=days)
    return {"items": items}
