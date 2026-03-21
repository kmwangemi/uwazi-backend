import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.enums import AuditAction
from app.models.investigation_model import Investigation
from app.models.whistleblower_report_model import WhistleblowerReport
from app.services.audit_service import AuditService

logger = get_logger(__name__)


# ── Investigations ─────────────────────────────────────────────────────────────


async def list_investigations(
    db: AsyncSession,
    search: Optional[str] = None,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Investigation], int]:
    base_query = select(Investigation)

    if search:
        term = f"%{search.strip()}%"
        base_query = base_query.filter(
            or_(
                Investigation.title.ilike(term),
                Investigation.tender_ref.ilike(term),
                Investigation.investigator_name.ilike(term),
            )
        )
    if status:
        base_query = base_query.filter(Investigation.status == status)
    if risk_level:
        base_query = base_query.filter(Investigation.risk_level == risk_level)

    total = (
        await db.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    )

    data_query = (
        base_query.order_by(desc(Investigation.opened_at))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    investigations = (await db.execute(data_query)).scalars().all()
    return investigations, total


async def get_investigation_by_id(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> Investigation:
    result = await db.execute(
        select(Investigation).filter(Investigation.id == investigation_id)
    )
    investigation = result.scalars().first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found.",
        )
    return investigation


async def create_investigation(
    db: AsyncSession,
    tender_id: uuid.UUID,
    title: str,
    tender_ref: Optional[str],
    risk_level: Optional[str],
    findings: Optional[str],
    investigator_name: Optional[str],
    created_by: Optional[uuid.UUID] = None,
) -> Investigation:
    try:
        investigation = Investigation(
            tender_id=tender_id,
            title=title,
            tender_ref=tender_ref,
            risk_level=risk_level,
            findings=findings,
            investigator_name=investigator_name,
        )
        db.add(investigation)
        await db.commit()
        await db.refresh(investigation)
        if created_by:
            await AuditService.log(
                db,
                AuditAction.CASE_CREATED,
                user_id=created_by,
                entity_type="Investigation",
                entity_id=investigation.id,
            )
        return investigation
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Failed to create investigation", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create investigation.",
        ) from e


async def update_investigation(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    status: Optional[str] = None,
    findings: Optional[str] = None,
    investigator_name: Optional[str] = None,
    updated_by: Optional[uuid.UUID] = None,
) -> Investigation:
    try:
        investigation = await get_investigation_by_id(db, investigation_id)
        if status is not None:
            investigation.status = status
            if status == "closed":
                investigation.closed_at = datetime.now(timezone.utc)
        if findings is not None:
            investigation.findings = findings
        if investigator_name is not None:
            investigation.investigator_name = investigator_name
        await db.commit()
        await db.refresh(investigation)
        if updated_by:
            action = AuditAction.CASE_CLOSED if status == "closed" else AuditAction.CASE_STATUS_UPDATED
            await AuditService.log(
                db,
                action,
                user_id=updated_by,
                entity_type="Investigation",
                entity_id=investigation.id,
            )
        return investigation
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Failed to update investigation",
            extra={"investigation_id": str(investigation_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update investigation.",
        ) from e


# ── Whistleblower Reports ──────────────────────────────────────────────────────


async def list_whistleblower_reports(
    db: AsyncSession,
    search: Optional[str] = None,
    is_reviewed: Optional[bool] = None,
    urgency: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[WhistleblowerReport], int]:
    base_query = select(WhistleblowerReport)

    if search:
        term = f"%{search.strip()}%"
        base_query = base_query.filter(
            or_(
                WhistleblowerReport.allegation_type.ilike(term),
                WhistleblowerReport.report_text.ilike(term),
                WhistleblowerReport.entity_name.ilike(term),
                WhistleblowerReport.tender_reference.ilike(term),
            )
        )
    if is_reviewed is not None:
        base_query = base_query.filter(WhistleblowerReport.is_reviewed == is_reviewed)
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
    return reports, total


async def get_whistleblower_report_by_id(
    db: AsyncSession,
    report_id: uuid.UUID,
) -> WhistleblowerReport:
    result = await db.execute(
        select(WhistleblowerReport).filter(WhistleblowerReport.id == report_id)
    )
    report = result.scalars().first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Whistleblower report not found.",
        )
    return report


async def mark_report_reviewed(
    db: AsyncSession,
    report_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    reviewer_notes: Optional[str],
    is_credible: Optional[bool],
) -> WhistleblowerReport:
    try:
        report = await get_whistleblower_report_by_id(db, report_id)
        report.is_reviewed = True
        report.reviewed_by_id = reviewer_id
        report.reviewed_at = datetime.now(timezone.utc)
        report.reviewer_notes = reviewer_notes
        report.is_credible = is_credible
        await db.commit()
        await db.refresh(report)
        await AuditService.log(
            db,
            AuditAction.CASE_NOTE_ADDED,
            user_id=reviewer_id,
            entity_type="WhistleblowerReport",
            entity_id=report.id,
        )
        return report
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Failed to mark report reviewed",
            extra={"report_id": str(report_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark report as reviewed.",
        ) from e
