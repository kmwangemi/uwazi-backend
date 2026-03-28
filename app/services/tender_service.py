import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.core.logger import get_logger
from app.enums import AuditAction, RiskLevel, TenderStatus
from app.models.risk_score_model import RiskScore
from app.models.tender_model import Tender
from app.schemas.tender_schema import TenderCreate, TenderUpdate
from app.services.audit_service import AuditService
from app.services.entity_service import get_or_create_entity

logger = get_logger(__name__)


async def create_tender(
    db: AsyncSession,
    tender_data: TenderCreate,
    created_by: uuid.UUID,
    attachments: list[dict] | None = None,
) -> Tender:
    try:
        result = await db.execute(
            select(Tender).filter(
                Tender.reference_number == tender_data.reference_number
            )
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A tender with this reference number already exists.",
            )
        new_tender = Tender(**tender_data.model_dump())
        db.add(new_tender)
        await db.flush()  # get the new_tender.id without committing yet
        if attachments:
            from app.models.tender_document_model import TenderDocument
            for att in attachments:
                doc = TenderDocument(
                    tender_id=new_tender.id,
                    filename=att.get("filename", "document.pdf"),
                    file_path=att.get("file_path"),
                    mime_type=att.get("mime_type", "application/pdf"),
                    doc_type=att.get("doc_type", "tender_notice"),
                )
                db.add(doc)
                
        await db.commit()
        await db.refresh(new_tender)
        await AuditService.log(
            db,
            AuditAction.TENDER_CREATED,
            user_id=created_by,
            entity_type="Tender",
            entity_id=new_tender.id,
        )
        return new_tender
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        # logger.error("Failed to create tender", extra={"error": str(e)})
        logger.error("Failed to create tender: %s", e)
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
    query = select(Tender).options(
        joinedload(Tender.entity),  # single row JOIN — efficient
        selectinload(Tender.risk_score),  # one-to-one via separate query
        selectinload(Tender.red_flags),  # one-to-many
        selectinload(Tender.bids),  # one-to-many
        selectinload(Tender.documents),  # one-to-many
    )
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Tender.reference_number.ilike(term),
                Tender.title.ilike(term),
            )
        )
    if status is not None:
        query = query.filter(Tender.status == status)
    if county is not None:
        query = query.filter(Tender.county.ilike(f"%{county}%"))
    if category is not None:
        query = query.filter(Tender.category.ilike(f"%{category}%"))
    # risk_level filter — joins RiskScore and filters by its level field
    if risk_level is not None:
        query = query.join(Tender.risk_score).filter(RiskScore.level == risk_level)
    query = query.order_by(Tender.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.unique().scalars().all()  # .unique() required when using joinedload


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
    updated_by: Optional[uuid.UUID] = None,
) -> Tender:
    try:
        tender = await get_tender_by_id(db, tender_id)
        update_data = tender_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(tender, field, value)
        await db.commit()
        await db.refresh(tender)
        if updated_by:
            await AuditService.log(
                db,
                AuditAction.TENDER_UPDATED,
                user_id=updated_by,
                entity_type="Tender",
                entity_id=tender.id,
            )
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
