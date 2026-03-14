from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import count

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.risk_score_model import RiskScore
from app.models.supplier_model import Supplier
from app.models.tender_model import Tender
from app.schemas.tender_schema import TenderCreate
from app.services.risk_engine_service import compute_and_save_risk

router = APIRouter(prefix="/tenders", tags=["Tenders"])


@router.get("", response_model=dict)
async def list_tenders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    county: Optional[str] = None,
    category: Optional[str] = None,
    risk_level: Optional[str] = None,
    status: Optional[str] = None,
    procurement_method: Optional[str] = None,
    min_value: Optional[float] = Query(None, description="Min estimated value KES"),
    max_value: Optional[float] = Query(None, description="Max estimated value KES"),
    date_from: Optional[str] = Query(None, description="ISO date e.g. 2026-01-01"),
    date_to: Optional[str] = Query(None, description="ISO date e.g. 2026-12-31"),
    sort_by: Optional[str] = Query(
        "created_at", description="created_at|estimated_value|total_score"
    ),
    sort_order: Optional[str] = Query("desc", description="asc|desc"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List tenders with filters, sorting, and pagination. Public endpoint."""
    query = select(Tender).options(
        joinedload(Tender.risk_score),
        joinedload(Tender.red_flags),
        joinedload(Tender.bids),
    )

    if county:
        query = query.filter(Tender.county.ilike(f"%{county}%"))
    if category:
        query = query.filter(Tender.category.ilike(f"%{category}%"))
    if status:
        query = query.filter(Tender.status == status)
    if procurement_method:
        query = query.filter(Tender.procurement_method == procurement_method)
    if min_value is not None:
        query = query.filter(Tender.estimated_value >= min_value)
    if max_value is not None:
        query = query.filter(Tender.estimated_value <= max_value)
    if date_from:
        try:
            query = query.filter(Tender.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Tender.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass
    if search:
        query = query.filter(
            Tender.title.ilike(f"%{search}%")
            | Tender.description.ilike(f"%{search}%")
            | Tender.reference_number.ilike(f"%{search}%")
        )
    if risk_level:
        query = query.join(RiskScore, RiskScore.tender_id == Tender.id).filter(
            RiskScore.risk_level == risk_level
        )

    # Sorting
    order_fn = desc if sort_order == "desc" else asc
    if sort_by == "estimated_value":
        query = query.order_by(order_fn(Tender.estimated_value))
    elif sort_by == "total_score":
        if risk_level is None:  # avoid double join
            query = query.outerjoin(RiskScore, RiskScore.tender_id == Tender.id)
        query = query.order_by(order_fn(RiskScore.total_score))
    else:
        query = query.order_by(order_fn(Tender.created_at))

    # Count total
    count_query = select(count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    tenders = result.unique().scalars().all()

    items = []
    for t in tenders:
        items.append(
            {
                "id": str(t.id),
                "reference_number": t.reference_number,
                "title": t.title,
                "category": t.category,
                "estimated_value": t.estimated_value,
                "county": t.county,
                "procurement_method": (
                    t.procurement_method.value if t.procurement_method else None
                ),
                "status": t.status.value if t.status else None,
                "submission_deadline": (
                    t.submission_deadline.isoformat() if t.submission_deadline else None
                ),
                "created_at": t.created_at.isoformat(),
                "risk_level": t.risk_score.risk_level.value if t.risk_score else None,
                "total_risk_score": t.risk_score.total_score if t.risk_score else None,
                "flag_count": len(t.red_flags) if t.red_flags else 0,
                "bid_count": len(t.bids) if t.bids else 0,
                "is_flagged": bool(t.red_flags),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/{tender_id}", response_model=dict)
async def get_tender(tender_id: UUID, db: AsyncSession = Depends(get_db)):
    """Full tender detail with risk score, red flags, bids, and entity. Public."""
    result = await db.execute(
        select(Tender)
        .options(
            joinedload(Tender.risk_score),
            joinedload(Tender.red_flags),
            joinedload(Tender.bids),
            joinedload(Tender.contract),
            joinedload(Tender.entity),
        )
        .filter(Tender.id == tender_id)
    )
    tender = result.unique().scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Enrich bids with supplier names
    bids_out = []
    for b in tender.bids or []:
        supplier_result = await db.execute(
            select(Supplier).filter(Supplier.id == b.supplier_id)
        )
        supplier = supplier_result.scalar_one_or_none()
        bids_out.append(
            {
                "id": str(b.id),
                "supplier_id": str(b.supplier_id),
                "supplier_name": supplier.name if supplier else None,
                "bid_amount": b.bid_amount,
                "is_winner": b.is_winner,
                "similarity_score": b.similarity_score,
                "proposal_text": b.proposal_text,
            }
        )

    return {
        "id": str(tender.id),
        "reference_number": tender.reference_number,
        "title": tender.title,
        "description": tender.description,
        "category": tender.category,
        "estimated_value": tender.estimated_value,
        "currency": tender.currency or "KES",
        "county": tender.county,
        "procurement_method": (
            tender.procurement_method.value if tender.procurement_method else None
        ),
        "status": tender.status.value if tender.status else None,
        "submission_deadline": (
            tender.submission_deadline.isoformat()
            if tender.submission_deadline
            else None
        ),
        "source_url": tender.source_url,
        "created_at": tender.created_at.isoformat(),
        "entity": (
            {
                "id": str(tender.entity.id),
                "name": tender.entity.name,
                "county": tender.entity.county,
                "corruption_history_score": tender.entity.corruption_history_score,
            }
            if tender.entity
            else None
        ),
        "risk_score": (
            {
                "total_score": tender.risk_score.total_score,
                "risk_level": tender.risk_score.risk_level.value,
                "price_score": tender.risk_score.price_score,
                "supplier_score": tender.risk_score.supplier_score,
                "spec_score": tender.risk_score.spec_score,
                "contract_value_score": tender.risk_score.contract_value_score,
                "entity_history_score": tender.risk_score.entity_history_score,
                "flags": tender.risk_score.flags,
                "ai_analysis": tender.risk_score.ai_analysis,
                "recommended_action": tender.risk_score.recommended_action,
                "computed_at": tender.risk_score.computed_at.isoformat(),
            }
            if tender.risk_score
            else None
        ),
        "red_flags": [
            {
                "type": f.flag_type,
                "severity": f.severity,
                "description": f.description,
                "evidence": f.evidence,
            }
            for f in (tender.red_flags or [])
        ],
        "bids": bids_out,
        "bid_count": len(bids_out),
        "contract": (
            {
                "contract_value": tender.contract.contract_value,
                "awarded_at": (
                    tender.contract.awarded_at.isoformat()
                    if tender.contract.awarded_at
                    else None
                ),
                "value_variation_pct": tender.contract.value_variation_pct,
            }
            if tender.contract
            else None
        ),
    }


@router.post("", response_model=dict, status_code=201)
async def create_tender(
    payload: TenderCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """Create a tender manually."""
    tender = Tender(**payload.model_dump())
    db.add(tender)
    await db.commit()
    await db.refresh(tender)
    background_tasks.add_task(_run_risk_in_background, tender.id)
    return {"id": str(tender.id), "message": "Tender created. Risk analysis queued."}


@router.post("/{tender_id}/analyze-risk", response_model=dict)
async def trigger_risk_analysis(
    tender_id: UUID,
    use_ai: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """Manually trigger / refresh risk analysis for a tender."""
    result = await db.execute(
        select(Tender)
        .options(
            joinedload(Tender.bids),
            joinedload(Tender.contract),
            joinedload(Tender.entity),
        )
        .filter(Tender.id == tender_id)
    )
    tender = result.unique().scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    supplier = None
    if tender.contract:
        supplier_result = await db.execute(
            select(Supplier).filter(Supplier.id == tender.contract.supplier_id)
        )
        supplier = supplier_result.scalar_one_or_none()
    elif tender.bids:
        winning_bid = next((b for b in tender.bids if b.is_winner), tender.bids[0])
        supplier_result = await db.execute(
            select(Supplier).filter(Supplier.id == winning_bid.supplier_id)
        )
        supplier = supplier_result.scalar_one_or_none()

    risk_score = await compute_and_save_risk(
        db, tender, supplier, list(tender.bids or []), use_ai=use_ai
    )

    return {
        "tender_id": str(tender_id),
        "total_score": risk_score.total_score,
        "risk_level": risk_score.risk_level.value,
        "price_score": risk_score.price_score,
        "supplier_score": risk_score.supplier_score,
        "spec_score": risk_score.spec_score,
        "contract_value_score": risk_score.contract_value_score,
        "flags": risk_score.flags,
        "ai_analysis": risk_score.ai_analysis,
        "recommended_action": risk_score.recommended_action,
        "computed_at": risk_score.computed_at.isoformat(),
    }


@router.get("/{tender_id}/investigation-package", response_model=dict)
async def get_investigation_package(
    tender_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """Generate full AI investigation briefing for EACC investigators."""
    result = await db.execute(
        select(Tender)
        .options(
            joinedload(Tender.risk_score),
            joinedload(Tender.bids),
            joinedload(Tender.contract),
        )
        .filter(Tender.id == tender_id)
    )
    tender = result.unique().scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if not tender.risk_score:
        raise HTTPException(
            status_code=400,
            detail="Run risk analysis first before generating investigation package",
        )

    supplier = None
    if tender.contract:
        supplier_result = await db.execute(
            select(Supplier).filter(Supplier.id == tender.contract.supplier_id)
        )
        supplier = supplier_result.scalar_one_or_none()

    from app.services.ai_service import generate_investigation_package

    package_md = await generate_investigation_package(
        tender={
            "title": tender.title,
            "description": tender.description,
            "estimated_value": tender.estimated_value,
            "county": tender.county,
            "procurement_method": (
                tender.procurement_method.value if tender.procurement_method else None
            ),
            "status": tender.status.value if tender.status else None,
            "reference_number": tender.reference_number,
        },
        risk_score={
            "total_score": tender.risk_score.total_score,
            "risk_level": tender.risk_score.risk_level.value,
            "price_score": tender.risk_score.price_score,
            "supplier_score": tender.risk_score.supplier_score,
            "spec_score": tender.risk_score.spec_score,
            "flags": tender.risk_score.flags,
            "ai_analysis": tender.risk_score.ai_analysis,
        },
        supplier=(
            {
                "name": supplier.name,
                "registration_number": supplier.registration_number,
                "company_age_days": supplier.company_age_days,
                "tax_filings_count": supplier.tax_filings_count,
                "directors": supplier.directors,
                "risk_score": supplier.risk_score,
            }
            if supplier
            else None
        ),
        bids=[
            {"bid_amount": b.bid_amount, "is_winner": b.is_winner}
            for b in (tender.bids or [])
        ],
    )

    return {
        "tender_id": str(tender_id),
        "tender_title": tender.title,
        "reference_number": tender.reference_number,
        "package_markdown": package_md,
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _run_risk_in_background(tender_id: UUID):
    """Background task — uses its own session since request session is closed."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Tender)
                .options(joinedload(Tender.bids), joinedload(Tender.entity))
                .filter(Tender.id == tender_id)
            )
            tender = result.unique().scalar_one_or_none()
            if tender:
                await compute_and_save_risk(db, tender, use_ai=True)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
