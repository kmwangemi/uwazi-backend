from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models import Tender, WhistleblowerReport
from app.schemas.whistleblower_schema import WhistleblowerCreate

router = APIRouter(prefix="/api/whistleblower", tags=["Whistleblower"])


@router.post("/submit", response_model=dict, status_code=201)
def submit_report(payload: WhistleblowerCreate, db: Session = Depends(get_db)):
    """
    Anonymous whistleblower report submission. No authentication required.
    AI triages the report immediately on submission.

    Response shape matches frontend WhistleblowerResponse type:
    {
        report_id, credibility_score, allegation_type, urgency,
        triage_summary, is_credible, identity_risk, corroborating_evidence_needed
    }
    """
    related_tender_title = None
    if payload.tender_id:
        tender = db.query(Tender).filter(Tender.id == payload.tender_id).first()
        related_tender_title = tender.title if tender else None

    triage_result = None
    credibility_score = None
    triage_summary = None
    urgency = "medium"
    is_credible = False
    allegation_type = getattr(payload, "allegation_type", None) or "other"
    identity_risk = "low"
    corroborating_evidence_needed = []

    try:
        from app.services.ai_service import triage_whistleblower_report

        triage_result = triage_whistleblower_report(
            getattr(payload, "description", None)
            or getattr(payload, "report_text", ""),
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
        # AI unavailable — still accept the report
        pass

    report_text = getattr(payload, "description", None) or getattr(
        payload, "report_text", ""
    )
    report = WhistleblowerReport(
        tender_id=getattr(payload, "tender_id", None),
        report_text=report_text,
        allegation_type=allegation_type,
        ai_triage_summary=triage_summary,
        credibility_score=credibility_score,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

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
def list_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    is_reviewed: Optional[bool] = Query(None),
    urgency: Optional[str] = Query(None, description="low|medium|high|critical"),
    allegation_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """List whistleblower reports. Investigators and admins only."""
    query = db.query(WhistleblowerReport)

    if is_reviewed is not None:
        query = query.filter(WhistleblowerReport.is_reviewed == is_reviewed)
    if allegation_type:
        query = query.filter(
            WhistleblowerReport.allegation_type.ilike(f"%{allegation_type}%")
        )

    # urgency stored in ai_triage_summary as JSON — filter by credibility_score proxy
    if urgency == "critical":
        query = query.filter(WhistleblowerReport.credibility_score >= 80)
    elif urgency == "high":
        query = query.filter(
            WhistleblowerReport.credibility_score >= 60,
            WhistleblowerReport.credibility_score < 80,
        )
    elif urgency == "medium":
        query = query.filter(
            WhistleblowerReport.credibility_score >= 40,
            WhistleblowerReport.credibility_score < 60,
        )

    total = query.count()
    reports = (
        query.order_by(desc(WhistleblowerReport.credibility_score))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": str(r.id),
                "tender_id": str(r.tender_id) if r.tender_id else None,
                "allegation_type": r.allegation_type,
                "ai_triage_summary": r.ai_triage_summary,
                "credibility_score": r.credibility_score,
                "is_reviewed": r.is_reviewed,
                "is_credible": r.is_credible if hasattr(r, "is_credible") else None,
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
def mark_report_reviewed(
    report_id: UUID,
    is_credible: bool,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """Mark a report as reviewed."""
    report = (
        db.query(WhistleblowerReport)
        .filter(WhistleblowerReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.is_reviewed = True
    if hasattr(report, "is_credible"):
        report.is_credible = is_credible
    db.commit()

    return {"id": str(report_id), "is_reviewed": True, "is_credible": is_credible}
