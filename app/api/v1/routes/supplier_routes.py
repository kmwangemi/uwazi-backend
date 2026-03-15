from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.supplier_model import Supplier
from app.schemas.supplier_schema import SupplierCreate
from app.core.dependencies import require_role
from app.services.supplier_checker_service import compute_supplier_score

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
        if r.get("ghost_probability") is not None:
            return round(r["ghost_probability"], 4)
        return round(r["combined_score"] / 100, 4)
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


@router.get("", response_model=dict)
def list_suppliers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    county: Optional[str] = None,
    min_risk_score: Optional[float] = Query(None),
    risk_level: Optional[str] = Query(None, description="low|medium|high|critical"),
    has_red_flags: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """List suppliers. Public endpoint."""
    query = db.query(Supplier)

    if search:
        query = query.filter(
            Supplier.name.ilike(f"%{search}%")
            | Supplier.registration_number.ilike(f"%{search}%")
            | Supplier.kra_pin.ilike(f"%{search}%")
        )
    if county:
        query = query.filter(Supplier.county.ilike(f"%{county}%"))
    if min_risk_score is not None:
        query = query.filter(Supplier.risk_score >= min_risk_score)
    if risk_level:
        lo = {"critical": 80, "high": 60, "medium": 40, "low": 0}.get(risk_level, 0)
        hi = {"critical": 101, "high": 80, "medium": 60, "low": 40}.get(risk_level, 101)
        query = query.filter(Supplier.risk_score >= lo, Supplier.risk_score < hi)
    if has_red_flags is True:
        query = query.filter(Supplier.risk_score >= 60)
    elif has_red_flags is False:
        query = query.filter(Supplier.risk_score < 60)

    total = query.count()
    suppliers = (
        query.order_by(desc(Supplier.risk_score))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": str(s.id),
                "name": s.name,
                "registration_number": s.registration_number,
                "kra_pin": s.kra_pin,
                "company_age_days": s.company_age_days,
                "risk_score": s.risk_score,
                "risk_level": _risk_level(s.risk_score),
                "ghost_probability": _ghost_prob(s),
                "past_contracts_count": s.past_contracts_count,
                "past_contracts_value": s.past_contracts_value,
                "is_verified": s.is_verified,
                "county": s.county,
                "tax_filings_count": s.tax_filings_count,
            }
            for s in suppliers
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/{supplier_id}", response_model=dict)
def get_supplier(supplier_id: UUID, db: Session = Depends(get_db)):
    """Full supplier detail. Public."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    risk_result = compute_supplier_score(supplier)
    ghost_prob = _ghost_prob(supplier)

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
        "directors": supplier.directors,
        "tax_filings_count": supplier.tax_filings_count,
        "employee_count": supplier.employee_count,
        "has_physical_address": supplier.has_physical_address,
        "has_online_presence": supplier.has_online_presence,
        "past_contracts_count": supplier.past_contracts_count,
        "past_contracts_value": supplier.past_contracts_value,
        "risk_score": supplier.risk_score,
        "risk_level": _risk_level(supplier.risk_score),
        "ghost_probability": ghost_prob,
        "risk_flags": risk_result["flags"],
        "is_verified": supplier.is_verified,
        "verification_notes": supplier.verification_notes,
        "created_at": supplier.created_at.isoformat(),
    }


@router.post("", response_model=dict, status_code=201)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
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
    db.commit()
    db.refresh(supplier)

    return {
        "id": str(supplier.id),
        "name": supplier.name,
        "risk_score": supplier.risk_score,
        "risk_flags": risk_result["flags"],
        "message": "Supplier created",
    }


@router.post("/{supplier_id}/refresh-risk", response_model=dict)
def refresh_supplier_risk(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    result = compute_supplier_score(supplier)
    supplier.risk_score = result["score"]
    db.commit()

    return {"risk_score": result["score"], "flags": result["flags"]}
