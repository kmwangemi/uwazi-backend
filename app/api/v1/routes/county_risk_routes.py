from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.county_risk_service import (
    get_county_risk,
    get_risk_trend,
    get_risk_type_distribution,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/county-risk", response_model=dict)
async def county_risk(db: AsyncSession = Depends(get_db)):
    """Aggregated risk stats per county."""
    items = await get_county_risk(db)
    return {"items": items}


@router.get("/risk-trend", response_model=dict)
async def risk_trend(
    months: int = Query(6, ge=1, le=24, description="Number of months to look back"),
    db: AsyncSession = Depends(get_db),
):
    """Monthly tender counts by risk level."""
    items = await get_risk_trend(db, months=months)
    return {"items": items}


@router.get("/risk-type-distribution", response_model=dict)
async def risk_type_distribution(db: AsyncSession = Depends(get_db)):
    """Total count per RedFlag type across all tenders."""
    items = await get_risk_type_distribution(db)
    return {"items": items}
