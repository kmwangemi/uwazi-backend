from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.sql.functions import count

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user_model import User
from app.models.risk_score_model import RiskScore
from app.models.supplier_model import Supplier
from app.models.tender_model import Tender
from app.schemas.tender_schema import TenderCreate
from app.services.risk_engine_service import compute_and_save_risk
from app.services.tender_service import create_tender as create_tender_service

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
        "created_at", description="created_at | estimated_value | total_score"
    ),
    sort_order: Optional[str] = Query("desc", description="asc | desc"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tenders with filters, sorting, and pagination. Protected endpoint."""

    base_query = select(Tender)

    # ── Filters ────────────────────────────────────────────────────────────────
    if county:
        base_query = base_query.filter(Tender.county.ilike(f"%{county}%"))
    if category:
        base_query = base_query.filter(Tender.category.ilike(f"%{category}%"))
    if status:
        base_query = base_query.filter(Tender.status == status)
    if procurement_method:
        base_query = base_query.filter(Tender.procurement_method == procurement_method)
    if min_value is not None:
        base_query = base_query.filter(Tender.estimated_value >= min_value)
    if max_value is not None:
        base_query = base_query.filter(Tender.estimated_value <= max_value)
    if date_from:
        try:
            base_query = base_query.filter(
                Tender.created_at >= datetime.fromisoformat(date_from)
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid date_from format: {date_from!r}"
            )
    if date_to:
        try:
            base_query = base_query.filter(
                Tender.created_at <= datetime.fromisoformat(date_to)
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid date_to format: {date_to!r}"
            )
    if search:
        base_query = base_query.filter(
            Tender.title.ilike(f"%{search}%")
            | Tender.description.ilike(f"%{search}%")
            | Tender.reference_number.ilike(f"%{search}%")
        )
    if risk_level:
        base_query = base_query.join(
            RiskScore, RiskScore.tender_id == Tender.id
        ).filter(RiskScore.risk_level == risk_level)

    # ── Sorting ────────────────────────────────────────────────────────────────
    order_fn = desc if sort_order == "desc" else asc
    if sort_by == "estimated_value":
        base_query = base_query.order_by(order_fn(Tender.estimated_value))
    elif sort_by == "total_score":
        if risk_level is None:
            base_query = base_query.outerjoin(
                RiskScore, RiskScore.tender_id == Tender.id
            )
        base_query = base_query.order_by(order_fn(RiskScore.total_score))
    else:
        base_query = base_query.order_by(order_fn(Tender.created_at))

    # ── Count (clean, before pagination + load options) ────────────────────────
    count_query = select(count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # ── Data fetch ─────────────────────────────────────────────────────────────
    data_query = (
        base_query.options(
            joinedload(Tender.entity),
            selectinload(Tender.risk_score),
            selectinload(Tender.red_flags),
            selectinload(Tender.bids),
            selectinload(Tender.documents),
        )
        .offset((page - 1) * limit)
        .limit(limit)
    )
    tenders = (await db.execute(data_query)).unique().scalars().all()

    # ── Serialisers ────────────────────────────────────────────────────────────
    def serialize_entity(e) -> dict | None:
        if not e:
            return None
        return {
            "id": str(e.id),
            "name": e.name,
            "type": e.entity_type,
            "county": e.county,
            "contact_email": e.contact_email,
        }

    def serialize_risk_score(rs) -> dict | None:
        if not rs:
            return None
        return {
            "id": str(rs.id),
            "total_score": rs.total_score,
            "risk_level": rs.risk_level.value if rs.risk_level else None,
            "price_score": rs.price_score,
            "supplier_score": rs.supplier_score,
            "spec_score": rs.spec_score,
            "collusion_score": rs.collusion_score,
            "ai_analysis": rs.ai_analysis,
            "computed_at": rs.computed_at.isoformat() if rs.computed_at else None,
        }

    def serialize_red_flag(rf) -> dict:
        return {
            "id": str(rf.id),
            "flag_type": rf.flag_type,
            "severity": rf.severity,
            "description": rf.description,
            "evidence": rf.evidence,
            "created_at": rf.created_at.isoformat(),
        }

    def serialize_bid(b) -> dict:
        return {
            "id": str(b.id),
            "supplier_name": b.supplier_name,
            "amount": b.amount,
            "currency": b.currency,
            "status": b.status,
            "is_winner": b.is_winner,
            "submitted_at": b.submitted_at.isoformat() if b.submitted_at else None,
        }

    def serialize_document(d) -> dict:
        return {
            "id": str(d.id),
            "title": d.title,
            "document_type": d.document_type,
            "file_url": d.file_url,
            "file_size": d.file_size,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }

    # ── Build response items ───────────────────────────────────────────────────
    items = [
        {
            "id": str(t.id),
            "reference_number": t.reference_number,
            "title": t.title,
            "description": t.description,
            "category": t.category,
            "county": t.county,
            "estimated_value": t.estimated_value,
            "currency": t.currency,
            "procurement_method": t.procurement_method,
            "status": t.status,
            "submission_deadline": (
                t.submission_deadline.isoformat() if t.submission_deadline else None
            ),
            "opening_date": t.opening_date.isoformat() if t.opening_date else None,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
            "source_url": t.source_url,
            "source": t.source,
            "entity": serialize_entity(t.entity),
            "risk_score": serialize_risk_score(t.risk_score),
            "red_flags": [serialize_red_flag(rf) for rf in t.red_flags],
            "bids": [serialize_bid(b) for b in t.bids],
            "documents": [serialize_document(d) for d in t.documents],
        }
        for t in tenders
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/{tender_id}", response_model=dict)
async def get_tender(
    tender_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full tender detail with risk score, red flags, bids, and entity."""
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
        "procurement_method": tender.procurement_method,
        "status": tender.status,
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
                "risk_level": tender.risk_score.risk_level.value if hasattr(tender.risk_score.risk_level, "value") else tender.risk_score.risk_level,
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
    tender = await create_tender_service(db, payload, created_by=user.id)
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
        db, tender, supplier, list(tender.bids or []), use_ai=use_ai, user_id=user.id
    )

    return {
        "tender_id": str(tender_id),
        "total_score": risk_score.total_score,
        "risk_level": risk_score.risk_level.value if hasattr(risk_score.risk_level, "value") else risk_score.risk_level,
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
            "procurement_method": tender.procurement_method,
            "status": tender.status,
            "reference_number": tender.reference_number,
        },
        risk_score={
            "total_score": tender.risk_score.total_score,
            "risk_level": tender.risk_score.risk_level.value if hasattr(tender.risk_score.risk_level, "value") else tender.risk_score.risk_level,
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
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
