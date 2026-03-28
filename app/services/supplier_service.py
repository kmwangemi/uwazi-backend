import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.functions import count

from app.core.logger import get_logger
from app.models.bid_model import Bid
from app.models.contract_model import Contract
from app.models.red_flag_model import RedFlag
from app.models.supplier_model import Supplier
from app.models.tender_model import Tender
from app.schemas.supplier_schema import SupplierCreate, SupplierUpdate

logger = get_logger(__name__)


async def create_supplier(
    db: AsyncSession,
    supplier_data: SupplierCreate,
) -> Supplier:
    try:
        result = await db.execute(
            select(Supplier).filter(
                Supplier.registration_number == supplier_data.registration_number
            )
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A supplier with this registration number already exists.",
            )
        new_supplier = Supplier(**supplier_data.model_dump())
        db.add(new_supplier)
        await db.commit()
        await db.refresh(new_supplier)
        return new_supplier
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Failed to create supplier", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create supplier.",
        ) from e


async def list_suppliers(
    db: AsyncSession,
    search: Optional[str] = None,
    county: Optional[str] = None,
    is_verified: Optional[bool] = None,
    is_blacklisted: Optional[bool] = None,
    min_risk_score: Optional[float] = None,
    risk_level: Optional[str] = None,  # derived from risk_score ranges, not a column
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Supplier], int]:
    """Returns (suppliers, total_count)."""
    base_query = select(Supplier)

    if search:
        term = f"%{search.strip()}%"
        base_query = base_query.filter(
            or_(
                Supplier.name.ilike(term),
                Supplier.registration_number.ilike(term),
                Supplier.kra_pin.ilike(term),
            )
        )
    if county is not None:
        base_query = base_query.filter(Supplier.county.ilike(f"%{county}%"))
    if is_verified is not None:
        base_query = base_query.filter(Supplier.is_verified == is_verified)
    if is_blacklisted is not None:
        base_query = base_query.filter(Supplier.is_blacklisted == is_blacklisted)
    if min_risk_score is not None:
        base_query = base_query.filter(Supplier.risk_score >= min_risk_score)
    if risk_level:
        bands = {
            "critical": (80, 101),
            "high": (60, 80),
            "medium": (40, 60),
            "low": (0, 40),
        }
        lo, hi = bands.get(risk_level, (0, 101))
        base_query = base_query.filter(
            Supplier.risk_score >= lo, Supplier.risk_score < hi
        )

    total = await db.scalar(select(count()).select_from(base_query.subquery())) or 0

    data_query = (
        base_query.options(
            selectinload(Supplier.directors),
            selectinload(Supplier.contracts),
        )
        .order_by(desc(Supplier.risk_score))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    suppliers = (await db.execute(data_query)).unique().scalars().all()
    return suppliers, total


async def get_supplier_by_id(
    db: AsyncSession,
    supplier_id: uuid.UUID,
) -> Supplier:
    result = await db.execute(
        select(Supplier)
        .options(
            selectinload(Supplier.directors),
            selectinload(Supplier.contracts),
        )
        .filter(Supplier.id == supplier_id)
    )
    supplier = result.scalars().first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found.",
        )
    return supplier


async def get_supplier_red_flags(
    db: AsyncSession,
    supplier_id: uuid.UUID,
) -> list[RedFlag]:
    """Traverse Supplier → Bid/Contract → Tender → RedFlag."""
    result = await db.execute(
        select(RedFlag)
        .join(Tender, Tender.id == RedFlag.tender_id)
        .outerjoin(Bid, Bid.tender_id == Tender.id)
        .outerjoin(Contract, Contract.tender_id == Tender.id)
        .filter(
            or_(
                Bid.supplier_id == supplier_id,
                Contract.supplier_id == supplier_id
            )
        )
        .distinct()
    )
    return result.unique().scalars().all()


async def update_supplier(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    supplier_data: SupplierUpdate,
) -> Supplier:
    try:
        supplier = await get_supplier_by_id(db, supplier_id)
        update_data = supplier_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(supplier, field, value)
        await db.commit()
        await db.refresh(supplier)
        return supplier
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Failed to update supplier",
            extra={"supplier_id": str(supplier_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update supplier.",
        ) from e


async def delete_supplier(
    db: AsyncSession,
    supplier_id: uuid.UUID,
) -> None:
    try:
        supplier = await get_supplier_by_id(db, supplier_id)
        await db.delete(supplier)
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Failed to delete supplier",
            extra={"supplier_id": str(supplier_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete supplier.",
        ) from e
