from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.services.investigation_service import (
    create_investigation,
    get_investigation_by_id,
    get_whistleblower_report_by_id,
    list_investigations,
    list_whistleblower_reports,
    mark_report_reviewed,
    update_investigation,
)

router = APIRouter(prefix="/investigations", tags=["Investigations"])


# ── Serialisers ────────────────────────────────────────────────────────────────


def serialize_investigation(inv) -> dict:
    return {
        "id": str(inv.id),
        "tender_id": str(inv.tender_id),
        "tender_ref": inv.tender_ref,
        "title": inv.title,
        "status": inv.status,
        "risk_level": inv.risk_level,
        "findings": inv.findings,
        "investigator_name": inv.investigator_name,
        "opened_at": inv.opened_at.isoformat(),
        "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
        "created_at": inv.created_at.isoformat(),
        "updated_at": inv.updated_at.isoformat(),
    }


def serialize_report(r) -> dict:
    return {
        "id": str(r.id),
        "tender_id": str(r.tender_id) if r.tender_id else None,
        "tender_reference": r.tender_reference,
        "allegation_type": r.allegation_type,
        "entity_name": r.entity_name,
        "report_text": r.report_text,
        "evidence_description": r.evidence_description,
        "ai_triage_summary": r.ai_triage_summary,
        "credibility_score": r.credibility_score,
        "urgency": r.urgency,
        "is_credible": r.is_credible,
        "is_reviewed": r.is_reviewed,
        "reviewer_notes": r.reviewer_notes,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "submitted_at": r.submitted_at.isoformat(),
    }


# ── Whistleblower routes (MUST be before /{investigation_id}) ──────────────────


@router.get("/whistleblower", response_model=dict)
async def list_whistleblower_reports_route(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_reviewed: Optional[bool] = None,
    urgency: Optional[str] = Query(None, description="critical|high|medium|low"),
    db: AsyncSession = Depends(get_db),
):
    reports, total = await list_whistleblower_reports(
        db,
        search=search,
        is_reviewed=is_reviewed,
        urgency=urgency,
        page=page,
        limit=limit,
    )
    return {
        "items": [serialize_report(r) for r in reports],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/whistleblower/{report_id}", response_model=dict)
async def get_whistleblower_report_route(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    report = await get_whistleblower_report_by_id(db, report_id)
    return serialize_report(report)


class ReviewReportRequest(BaseModel):
    reviewer_id: UUID
    reviewer_notes: Optional[str] = None
    is_credible: Optional[bool] = None


@router.patch("/whistleblower/{report_id}/review", response_model=dict)
async def review_report_route(
    report_id: UUID,
    payload: ReviewReportRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    report = await mark_report_reviewed(
        db,
        report_id,
        reviewer_id=payload.reviewer_id,
        reviewer_notes=payload.reviewer_notes,
        is_credible=payload.is_credible,
    )
    return serialize_report(report)


# ── Investigation routes (parameterized LAST) ──────────────────────────────────


@router.get("", response_model=dict)
async def list_investigations_route(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = Query(None, description="open|in_review|escalated|closed"),
    risk_level: Optional[str] = Query(None, description="critical|high|medium|low"),
    db: AsyncSession = Depends(get_db),
):
    investigations, total = await list_investigations(
        db,
        search=search,
        status=status,
        risk_level=risk_level,
        page=page,
        limit=limit,
    )
    return {
        "items": [serialize_investigation(i) for i in investigations],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


class CreateInvestigationRequest(BaseModel):
    tender_id: UUID
    title: str
    tender_ref: Optional[str] = None
    risk_level: Optional[str] = None
    findings: Optional[str] = None
    investigator_name: Optional[str] = None


@router.post("", response_model=dict, status_code=201)
async def create_investigation_route(
    payload: CreateInvestigationRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    inv = await create_investigation(
        db,
        tender_id=payload.tender_id,
        title=payload.title,
        tender_ref=payload.tender_ref,
        risk_level=payload.risk_level,
        findings=payload.findings,
        investigator_name=payload.investigator_name,
    )
    return serialize_investigation(inv)


class UpdateInvestigationRequest(BaseModel):
    status: Optional[str] = None
    findings: Optional[str] = None
    investigator_name: Optional[str] = None


# ⚠️ Parameterized routes LAST — must never appear before any static path
@router.get("/{investigation_id}", response_model=dict)
async def get_investigation_route(
    investigation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    inv = await get_investigation_by_id(db, investigation_id)
    return serialize_investigation(inv)


@router.patch("/{investigation_id}", response_model=dict)
async def update_investigation_route(
    investigation_id: UUID,
    payload: UpdateInvestigationRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    inv = await update_investigation(
        db,
        investigation_id,
        status=payload.status,
        findings=payload.findings,
        investigator_name=payload.investigator_name,
    )
    return serialize_investigation(inv)
