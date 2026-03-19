from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.tender_model import Tender
from app.models.whistleblower_report_model import WhistleblowerReport
from app.schemas.whistleblower_schema import WhistleblowerCreate

router = APIRouter(prefix="/whistleblower", tags=["Whistleblower"])


@router.post("/submit", response_model=dict, status_code=201)
async def submit_report(
    payload: WhistleblowerCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Anonymous whistleblower report submission. No authentication required.
    AI triages the report immediately on submission.
    """
    # Resolve tender title if tender_id provided
    related_tender_title = None
    if payload.tender_id:
        result = await db.execute(select(Tender).filter(Tender.id == payload.tender_id))
        tender = result.scalars().first()
        related_tender_title = tender.title if tender else None

    # AI triage
    credibility_score = None
    triage_summary = None
    urgency = "medium"
    is_credible = False
    allegation_type = payload.allegation_type or "other"
    identity_risk = "low"
    corroborating_evidence_needed = []

    try:
        from app.services.ai_service import triage_whistleblower_report

        triage_result = await triage_whistleblower_report(
            payload.description,
            related_tender_title,
        )
        credibility_score = triage_result.get("credibility_score")
        triage_summary = triage_result.get("triage_summary")
        urgency = triage_result.get("urgency", "medium")
        is_credible = triage_result.get("is_credible", False)
        allegation_type = triage_result.get("allegation_type", allegation_type)
        identity_risk = triage_result.get("identity_risk", "low")
        corroborating_evidence_needed = triage_result.get(
            "corroborating_evidence_needed", []
        )
    except Exception:
        pass  # AI unavailable — still accept the report

    # Save — map form fields to model columns correctly
    report = WhistleblowerReport(
        tender_id=payload.tender_id,
        tender_reference=payload.tender_reference,  # ← now saved
        report_text=payload.description,  # ← description → report_text
        allegation_type=allegation_type,
        entity_name=payload.entity_name,  # ← now saved
        evidence_description=payload.evidence_description,  # ← now saved
        ai_triage_summary=triage_summary,
        credibility_score=credibility_score,
        urgency=urgency,
        is_credible=is_credible,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return {
        "report_id": str(report.id),
        "credibility_score": credibility_score,
        "allegation_type": allegation_type,
        "urgency": urgency,
        "triage_summary": triage_summary,
        "is_credible": is_credible,
        "identity_risk": identity_risk,
        "corroborating_evidence_needed": corroborating_evidence_needed,
        "message": "Your report has been received securely and anonymously.",
    }


@router.get("/reports", response_model=dict)
async def list_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    is_reviewed: Optional[bool] = Query(None),
    urgency: Optional[str] = Query(None, description="low|medium|high|critical"),
    allegation_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """List whistleblower reports. Investigators and admins only."""
    base_query = select(WhistleblowerReport)

    if is_reviewed is not None:
        base_query = base_query.filter(WhistleblowerReport.is_reviewed == is_reviewed)
    if allegation_type:
        base_query = base_query.filter(
            WhistleblowerReport.allegation_type.ilike(f"%{allegation_type}%")
        )
    # urgency is now stored directly on the model column
    if urgency:
        base_query = base_query.filter(WhistleblowerReport.urgency == urgency)

    total = (
        await db.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    )

    data_query = (
        base_query.order_by(desc(WhistleblowerReport.credibility_score))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    reports = (await db.execute(data_query)).scalars().all()

    return {
        "items": [
            {
                "id": str(r.id),
                "tender_id": str(r.tender_id) if r.tender_id else None,
                "tender_reference": r.tender_reference,
                "allegation_type": r.allegation_type,
                "entity_name": r.entity_name,
                "ai_triage_summary": r.ai_triage_summary,
                "credibility_score": r.credibility_score,
                "urgency": r.urgency,
                "is_reviewed": r.is_reviewed,
                "is_credible": r.is_credible,
                "submitted_at": r.submitted_at.isoformat(),
            }
            for r in reports
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.patch("/reports/{report_id}/review", response_model=dict)
async def mark_report_reviewed(
    report_id: UUID,
    is_credible: bool,
    reviewer_notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """Mark a report as reviewed."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(WhistleblowerReport).filter(WhistleblowerReport.id == report_id)
    )
    report = result.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.is_reviewed = True
    report.is_credible = is_credible
    report.reviewed_at = datetime.now(timezone.utc)
    report.reviewer_notes = reviewer_notes
    await db.commit()

    return {
        "id": str(report_id),
        "is_reviewed": True,
        "is_credible": is_credible,
        "reviewed_at": report.reviewed_at.isoformat(),
    }
