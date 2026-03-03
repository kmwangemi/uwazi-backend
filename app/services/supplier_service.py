import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.logger import get_logger
from app.models.enums_model import RiskLevel
from app.models.supplier_model import Supplier
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
    is_verified: Optional[bool] = None,
    is_blacklisted: Optional[bool] = None,
    is_ghost_likely: Optional[bool] = None,
    tax_compliant: Optional[bool] = None,
    risk_level: Optional[RiskLevel] = None,
    county: Optional[str] = None,
    agpo_group: Optional[str] = None,
    supply_category: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Supplier]:
    query = select(Supplier)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Supplier.name.ilike(term),
                Supplier.registration_number.ilike(term),
                Supplier.county.ilike(term),
            )
        )
    if is_verified is not None:
        query = query.filter(Supplier.is_verified == is_verified)
    if is_blacklisted is not None:
        query = query.filter(Supplier.is_blacklisted == is_blacklisted)
    if is_ghost_likely is not None:
        query = query.filter(Supplier.is_ghost_likely == is_ghost_likely)
    if tax_compliant is not None:
        query = query.filter(Supplier.tax_compliant == tax_compliant)
    if risk_level is not None:
        query = query.filter(Supplier.risk_level == risk_level)
    if county is not None:
        query = query.filter(Supplier.county.ilike(f"%{county}%"))
    if agpo_group is not None:
        query = query.filter(Supplier.agpo_group == agpo_group)
    if supply_category is not None:
        query = query.filter(Supplier.supply_category.ilike(f"%{supply_category}%"))
    query = query.order_by(Supplier.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_supplier_by_id(db: AsyncSession, supplier_id: uuid.UUID) -> Supplier:
    result = await db.execute(select(Supplier).filter(Supplier.id == supplier_id))
    supplier = result.scalars().first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found.",
        )
    return supplier


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


async def delete_supplier(db: AsyncSession, supplier_id: uuid.UUID) -> None:
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
