import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.logger import get_logger
from app.models.enums_model import RiskLevel, TenderStatus
from app.models.tender_model import Tender
from app.schemas.tender_schema import TenderCreate, TenderUpdate

logger = get_logger(__name__)


async def create_tender(
    db: AsyncSession,
    tender_data: TenderCreate,
    created_by: uuid.UUID,
    attachments: list[dict] | None = None,
) -> Tender:
    try:
        result = await db.execute(
            select(Tender).filter(Tender.tender_number == tender_data.tender_number)
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A tender with this reference number already exists.",
            )
        # new_tender = Tender(
        #     **tender_data.model_dump(),
        #     created_by=created_by,
        #     attachments=attachments or [],
        # )
        new_tender = Tender(
            **tender_data.model_dump(exclude={"attachments"}),
            created_by=created_by,
            attachments=attachments or [],
        )
        db.add(new_tender)
        await db.commit()
        await db.refresh(new_tender)
        return new_tender
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Failed to create tender", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tender.",
        ) from e


async def list_tenders(
    db: AsyncSession,
    search: Optional[str] = None,
    status: Optional[TenderStatus] = None,
    risk_level: Optional[RiskLevel] = None,
    county: Optional[str] = None,
    category: Optional[str] = None,
    is_flagged: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Tender]:
    query = select(Tender)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Tender.tender_number.ilike(term),
                Tender.title.ilike(term),
                Tender.entity_name.ilike(term),
            )
        )
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


async def get_tender_by_id(db: AsyncSession, tender_id: uuid.UUID) -> Tender:
    result = await db.execute(select(Tender).filter(Tender.id == tender_id))
    tender = result.scalars().first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found.",
        )
    return tender


async def update_tender(
    db: AsyncSession,
    tender_id: uuid.UUID,
    tender_data: TenderUpdate,
) -> Tender:
    try:
        tender = await get_tender_by_id(db, tender_id)
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
        logger.error(
            "Failed to update tender",
            extra={"tender_id": str(tender_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tender.",
        ) from e


async def delete_tender(db: AsyncSession, tender_id: uuid.UUID) -> None:
    try:
        tender = await get_tender_by_id(db, tender_id)
        await db.delete(tender)
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Failed to delete tender",
            extra={"tender_id": str(tender_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tender.",
        ) from e
