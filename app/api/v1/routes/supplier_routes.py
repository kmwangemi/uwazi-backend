import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums_model import RiskLevel
from app.schemas.supplier_schema import SupplierCreate, SupplierResponse, SupplierUpdate
from app.services import supplier_service

supplier_router = APIRouter()

DbDependency = Annotated[AsyncSession, Depends(get_db)]


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
    return await supplier_service.create_supplier(db, supplier_data)


@supplier_router.get("/", response_model=list[SupplierResponse])
async def list_suppliers(
    db: DbDependency,
    search: Optional[str] = Query(
        None, description="Search by name, registration number, or county"
    ),
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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return await supplier_service.list_suppliers(
        db=db,
        search=search,
        is_verified=is_verified,
        is_blacklisted=is_blacklisted,
        is_ghost_likely=is_ghost_likely,
        tax_compliant=tax_compliant,
        risk_level=risk_level,
        county=county,
        agpo_group=agpo_group,
        supply_category=supply_category,
        skip=skip,
        limit=limit,
    )


@supplier_router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: uuid.UUID, db: DbDependency):
    return await supplier_service.get_supplier_by_id(db, supplier_id)


@supplier_router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: uuid.UUID,
    supplier_data: SupplierUpdate,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    return await supplier_service.update_supplier(db, supplier_id, supplier_data)


@supplier_router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: uuid.UUID,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    await supplier_service.delete_supplier(db, supplier_id)
