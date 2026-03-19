from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.supplier_model import Supplier
from app.schemas.supplier_schema import SupplierCreate
from app.services.supplier_checker_service import compute_supplier_score
from app.services.supplier_service import (
    delete_supplier,
    get_supplier_by_id,
    get_supplier_red_flags,
    list_suppliers,
)

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


def _ghost_prob(supplier: Supplier) -> float:
    try:
        from app.ml.supplier_risk import predict as ml_supplier

        r = ml_supplier(
            company_age_days=supplier.company_age_days,
            tax_filings_count=supplier.tax_filings_count,
            directors=supplier.directors or [],
            has_physical_address=supplier.has_physical_address,
            has_online_presence=supplier.has_online_presence,
            past_contracts_count=supplier.past_contracts_count,
            past_contracts_value=supplier.past_contracts_value,
        )
        return round(r.get("ghost_probability") or r["combined_score"] / 100, 4)
    except Exception:
        return round(min((supplier.risk_score or 0) / 100, 1.0), 4)


def _risk_level(score: Optional[float]) -> str:
    if score is None:
        return "low"
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def serialize_director(d) -> dict:
    return {
        "id": str(d.id),
        "full_name": d.full_name,
        "national_id": d.national_id,
        "role_title": d.role_title,
        "phone": d.phone,
        "email": d.email,
        "is_politically_exposed": d.is_politically_exposed,
        "pep_details": d.pep_details,
    }


def serialize_red_flag(rf) -> dict:
    return {
        "id": str(rf.id),
        "flag_type": rf.flag_type,
        "severity": rf.severity,
        "description": rf.description,
        "evidence": rf.evidence,
        "source_model": rf.source_model,
        "tender_id": str(rf.tender_id),
        "created_at": rf.created_at.isoformat(),
    }


def serialize_contract(c) -> dict:
    return {
        "id": str(c.id),
        "title": getattr(c, "title", None),
        "value": getattr(c, "value", None),
        "status": getattr(c, "status", None),
        "awarded_at": (
            c.awarded_at.isoformat() if getattr(c, "awarded_at", None) else None
        ),
    }


@router.get("", response_model=dict)
async def list_suppliers_route(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    county: Optional[str] = None,
    is_verified: Optional[bool] = None,
    is_blacklisted: Optional[bool] = None,
    min_risk_score: Optional[float] = Query(None),
    risk_level: Optional[str] = Query(None, description="low|medium|high|critical"),
    db: AsyncSession = Depends(get_db),
):
    suppliers, total = await list_suppliers(
        db,
        search=search,
        county=county,
        is_verified=is_verified,
        is_blacklisted=is_blacklisted,
        min_risk_score=min_risk_score,
        risk_level=risk_level,
        page=page,
        limit=limit,
    )

    items = [
        {
            "id": str(s.id),
            "name": s.name,
            "registration_number": s.registration_number,
            "county": s.county,
            "company_age_days": s.company_age_days,
            "tax_filings_count": s.tax_filings_count,
            "risk_score": s.risk_score,
            "risk_level": _risk_level(s.risk_score),
            "ghost_probability": _ghost_prob(s),
            "is_verified": s.is_verified,
            "is_blacklisted": s.is_blacklisted,
            "directors": [serialize_director(d) for d in (s.directors or [])],
            "contracts_won": len(s.contracts) if s.contracts else 0,
            "total_value_won": (
                sum(c.contract_value or 0 for c in s.contracts) if s.contracts else 0
            ),
        }
        for s in suppliers
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/{supplier_id}", response_model=dict)
async def get_supplier_route(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier_by_id(db, supplier_id)
    red_flags = await get_supplier_red_flags(db, supplier_id)
    risk_result = compute_supplier_score(supplier)

    return {
        "id": str(supplier.id),
        "name": supplier.name,
        "registration_number": supplier.registration_number,
        "kra_pin": supplier.kra_pin,
        "incorporation_date": (
            supplier.incorporation_date.isoformat()
            if supplier.incorporation_date
            else None
        ),
        "company_age_days": supplier.company_age_days,
        "address": supplier.address,
        "county": supplier.county,
        "phone": supplier.phone,
        "email": supplier.email,
        "tax_filings_count": supplier.tax_filings_count,
        "employee_count": supplier.employee_count,
        "has_physical_address": supplier.has_physical_address,
        "has_online_presence": supplier.has_online_presence,
        "past_contracts_count": supplier.past_contracts_count,
        "past_contracts_value": supplier.past_contracts_value,
        "risk_score": supplier.risk_score,
        "risk_level": _risk_level(supplier.risk_score),
        "ghost_probability": _ghost_prob(supplier),
        "risk_flags": risk_result["flags"],
        "is_verified": supplier.is_verified,
        "is_blacklisted": supplier.is_blacklisted,
        "verification_status": supplier.verification_status,
        "verification_notes": supplier.verification_notes,
        "blacklist_reason": supplier.blacklist_reason,
        "directors": [serialize_director(d) for d in (supplier.directors or [])],
        "contracts_won": len(supplier.contracts) if supplier.contracts else 0,
        "total_value_won": (
            sum(c.value or 0 for c in supplier.contracts) if supplier.contracts else 0
        ),
        "contracts": [serialize_contract(c) for c in (supplier.contracts or [])],
        "red_flags": [serialize_red_flag(rf) for rf in red_flags],
        "created_at": supplier.created_at.isoformat(),
        "updated_at": supplier.updated_at.isoformat(),
    }


@router.post("", response_model=dict, status_code=201)
async def create_supplier_route(
    payload: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    company_age_days = None
    if payload.incorporation_date:
        company_age_days = (
            datetime.now(timezone.utc) - payload.incorporation_date
        ).days

    supplier = Supplier(**payload.model_dump(), company_age_days=company_age_days)
    risk_result = compute_supplier_score(supplier)
    supplier.risk_score = risk_result["score"]

    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)

    return {
        "id": str(supplier.id),
        "name": supplier.name,
        "risk_score": supplier.risk_score,
        "risk_flags": risk_result["flags"],
        "message": "Supplier created",
    }


@router.post("/{supplier_id}/refresh-risk", response_model=dict)
async def refresh_supplier_risk(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    supplier = await get_supplier_by_id(db, supplier_id)
    risk_result = compute_supplier_score(supplier)
    supplier.risk_score = risk_result["score"]
    await db.commit()

    return {"risk_score": risk_result["score"], "flags": risk_result["flags"]}


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier_route(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin")),
):
    await delete_supplier(db, supplier_id)
