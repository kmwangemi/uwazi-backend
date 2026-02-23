import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums_model import RiskLevel
from app.models.supplier_model import Supplier
from app.schemas.supplier_schema import SupplierCreate, SupplierResponse, SupplierUpdate

supplier_router = APIRouter()

DbDependency = Annotated[AsyncSession, Depends(get_db)]


# ─── Create ───────────────────────────────────────────────────────────────────


@supplier_router.post(
    "/",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier(
    supplier_data: SupplierCreate,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    try:
        # Check for duplicate registration number
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create supplier.",
        ) from e


# ─── List / Search / Filter ───────────────────────────────────────────────────


@supplier_router.get("/", response_model=list[SupplierResponse])
async def list_suppliers(
    db: DbDependency,
    # Search
    search: Optional[str] = Query(
        None,
        description="Search by supplier name, registration number, or county",
    ),
    # Filters
    is_verified: Optional[bool] = Query(
        None, description="Filter by verification status"
    ),
    is_blacklisted: Optional[bool] = Query(
        None, description="Filter blacklisted suppliers"
    ),
    is_ghost_likely: Optional[bool] = Query(
        None, description="Filter ghost company suspects"
    ),
    tax_compliant: Optional[bool] = Query(
        None, description="Filter by tax compliance status"
    ),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    county: Optional[str] = Query(None, description="Filter by county"),
    agpo_group: Optional[str] = Query(None, description="Filter by AGPO group"),
    supply_category: Optional[str] = Query(
        None, description="Filter by supply category"
    ),
    # Pagination
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    query = select(Supplier)

    # Search across name, registration_number, county
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Supplier.name.ilike(term),
                Supplier.registration_number.ilike(term),
                Supplier.county.ilike(term),
            )
        )

    # Filters
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


# ─── Get by ID ────────────────────────────────────────────────────────────────


@supplier_router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: uuid.UUID,
    db: DbDependency,
):
    result = await db.execute(select(Supplier).filter(Supplier.id == supplier_id))
    supplier = result.scalars().first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found.",
        )
    return supplier


# ─── Update ───────────────────────────────────────────────────────────────────


@supplier_router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: uuid.UUID,
    supplier_data: SupplierUpdate,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    try:
        result = await db.execute(select(Supplier).filter(Supplier.id == supplier_id))
        supplier = result.scalars().first()
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update supplier.",
        ) from e


# ─── Delete ───────────────────────────────────────────────────────────────────


@supplier_router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: uuid.UUID,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    try:
        result = await db.execute(select(Supplier).filter(Supplier.id == supplier_id))
        supplier = result.scalars().first()
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )

        await db.delete(supplier)
        await db.commit()

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete supplier.",
        ) from e
