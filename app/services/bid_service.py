import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.logger import get_logger
from app.enums import AuditAction
from app.models.bid_model import Bid
from app.models.tender_model import Tender
from app.schemas.bid_schema import BidCreate, BidUpdate
from app.services.audit_service import AuditService

logger = get_logger(__name__)


def _generate_bid_reference() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"BID-{ts}-{str(uuid.uuid4())[:6].upper()}"


async def create_bid(
    db: AsyncSession,
    bid_data: BidCreate,
    submitted_by: uuid.UUID,
    technical_documents: list[dict] | None = None,
    financial_documents: list[dict] | None = None,
    compliance_documents: list[dict] | None = None,
) -> Bid:
    try:
        # Verify tender exists
        result = await db.execute(
            select(Tender).filter(Tender.id == bid_data.tender_id)
        )
        tender = result.scalars().first()
        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tender not found.",
            )

        # Prevent duplicate bids from same supplier on same tender
        existing = await db.execute(
            select(Bid).filter(
                Bid.tender_id == bid_data.tender_id,
                Bid.supplier_id == bid_data.supplier_id,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already submitted a bid for this tender.",
            )

        new_bid = Bid(
            **bid_data.model_dump(),
            submitted_by=submitted_by,
            bid_reference=_generate_bid_reference(),
            technical_documents=technical_documents or [],
            financial_documents=financial_documents or [],
            compliance_documents=compliance_documents or [],
        )
        db.add(new_bid)
        await db.commit()
        await db.refresh(new_bid)
        await AuditService.log(
            db,
            AuditAction.BID_SUBMITTED,
            user_id=submitted_by,
            entity_type="Bid",
            entity_id=new_bid.id,
        )
        return new_bid
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Failed to create bid", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit bid.",
        ) from e


async def list_bids_for_tender(
    db: AsyncSession,
    tender_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[Bid]:
    result = await db.execute(
        select(Bid)
        .filter(Bid.tender_id == tender_id)
        .order_by(Bid.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def list_bids_for_supplier(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[Bid]:
    result = await db.execute(
        select(Bid)
        .filter(Bid.supplier_id == supplier_id)
        .order_by(Bid.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_bid_by_id(db: AsyncSession, bid_id: uuid.UUID) -> Bid:
    result = await db.execute(select(Bid).filter(Bid.id == bid_id))
    bid = result.scalars().first()
    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bid not found.",
        )
    return bid


async def update_bid(
    db: AsyncSession,
    bid_id: uuid.UUID,
    bid_data: BidUpdate,
    updated_by: Optional[uuid.UUID] = None,
) -> Bid:
    try:
        bid = await get_bid_by_id(db, bid_id)
        update_data = bid_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(bid, field, value)
        await db.commit()
        await db.refresh(bid)
        if updated_by:
            await AuditService.log(
                db,
                AuditAction.BID_UPDATED,
                user_id=updated_by,
                entity_type="Bid",
                entity_id=bid.id,
            )
        return bid
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Failed to update bid", extra={"bid_id": str(bid_id), "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bid.",
        ) from e


async def delete_bid(db: AsyncSession, bid_id: uuid.UUID) -> None:
    try:
        bid = await get_bid_by_id(db, bid_id)
        await db.delete(bid)
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Failed to delete bid", extra={"bid_id": str(bid_id), "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete bid.",
        ) from e
