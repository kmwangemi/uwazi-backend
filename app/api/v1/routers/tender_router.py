import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums_model import RiskLevel, TenderStatus
from app.models.tender_model import Tender
from app.schemas.tender_schema import TenderCreate, TenderResponse, TenderUpdate

tender_router = APIRouter()

DbDependency = Annotated[AsyncSession, Depends(get_db)]


# ─── Create ───────────────────────────────────────────────────────────────────


@tender_router.post(
    "/",
    response_model=TenderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tender(
    tender_data: TenderCreate,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    try:
        # Check for duplicate tender number
        result = await db.execute(
            select(Tender).filter(Tender.tender_number == tender_data.tender_number)
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A tender with this reference number already exists.",
            )

        new_tender = Tender(
            **tender_data.model_dump(),
            created_by=current_user.id,
        )
        db.add(new_tender)
        await db.commit()
        await db.refresh(new_tender)
        return new_tender

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tender.",
        ) from e


# ─── List / Search / Filter ───────────────────────────────────────────────────


@tender_router.get("/", response_model=list[TenderResponse])
async def list_tenders(
    db: DbDependency,
    # Search
    search: Optional[str] = Query(
        None,
        description="Search by tender number, title, or procuring entity",
    ),
    # Filters
    status: Optional[TenderStatus] = Query(None, description="Filter by tender status"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    county: Optional[str] = Query(None, description="Filter by county"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_flagged: Optional[bool] = Query(None, description="Filter flagged tenders"),
    # Pagination
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    query = select(Tender)

    # Search across tender_number, title, procuring_entity
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Tender.tender_number.ilike(term),
                Tender.title.ilike(term),
                Tender.procuring_entity.ilike(term),
            )
        )

    # Filters
    if status is not None:
        query = query.filter(Tender.status == status)
    if risk_level is not None:
        query = query.filter(Tender.risk_level == risk_level)
    if county is not None:
        query = query.filter(Tender.county.ilike(f"%{county}%"))
    if category is not None:
        query = query.filter(Tender.category.ilike(f"%{category}%"))
    if is_flagged is not None:
        query = query.filter(Tender.is_flagged == is_flagged)

    query = query.order_by(Tender.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# ─── Get by ID ────────────────────────────────────────────────────────────────


@tender_router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender(
    tender_id: uuid.UUID,
    db: DbDependency,
):
    result = await db.execute(select(Tender).filter(Tender.id == tender_id))
    tender = result.scalars().first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found.",
        )
    return tender


# ─── Update ───────────────────────────────────────────────────────────────────


@tender_router.patch("/{tender_id}", response_model=TenderResponse)
async def update_tender(
    tender_id: uuid.UUID,
    tender_data: TenderUpdate,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    try:
        result = await db.execute(select(Tender).filter(Tender.id == tender_id))
        tender = result.scalars().first()
        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tender not found.",
            )

        update_data = tender_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(tender, field, value)

        await db.commit()
        await db.refresh(tender)
        return tender

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tender.",
        ) from e


# ─── Delete ───────────────────────────────────────────────────────────────────


@tender_router.delete("/{tender_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tender(
    tender_id: uuid.UUID,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    try:
        result = await db.execute(select(Tender).filter(Tender.id == tender_id))
        tender = result.scalars().first()
        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tender not found.",
            )

        await db.delete(tender)
        await db.commit()

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tender.",
        ) from e
