"""
app/models/whistleblower_report.py
───────────────────────────────────
WhistleblowerReport model — anonymous tip submissions about suspected
procurement corruption.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tender_model import Tender
    from app.models.user_model import User


class WhistleblowerReport(Base):
    """
    An anonymous tip about suspected procurement corruption.

    Privacy by design:
        - No IP addresses, device fingerprints, or session tokens are stored
        - No contact information is recorded unless the reporter chooses to provide
          a secure email (which is never stored in this table)
        - The reporter receives a UUID reference number stored only in their
          browser's sessionStorage — not in the database

    AI triage pipeline (runs immediately on submission):
        1. POST /api/whistleblower/submit received
        2. ai_service.triage_whistleblower_report() calls Claude claude-opus-4-6
        3. Returns: credibility_score, urgency, allegation_type, identity_risk,
                   corroborating_evidence_needed
        4. All fields stored on this record
        5. If credibility_score >= 60: notifies investigators via dashboard

    Review workflow:
        - Investigators see reports sorted by credibility_score descending
        - reviewed_by_id and reviewed_at are set when an investigator marks
          a report as reviewed
        - is_credible is the investigator's final judgement (may differ from AI)
    """

    __tablename__ = "whistleblower_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Optional link to a specific tender
    tender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        # SET NULL: deleting a tender should not delete the report
        ForeignKey("tenders.id", ondelete="SET NULL"),
        index=True,
    )
    tender_reference: Mapped[Optional[str]] = mapped_column(
        String(200),
        comment="Free-text tender reference entered by reporter; may not match a real tender.",
    )
    # Report content
    report_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Primary allegation description. Minimum 50 characters enforced in schema.",
    )
    allegation_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        comment="AllegationType enum value — set by reporter or corrected by AI triage.",
    )
    entity_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="Name of the procuring entity as entered by reporter.",
    )
    evidence_description: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Reporter's description of supporting evidence they hold.",
    )
    # ── AI triage output ───────────────────────────────────────────────────────
    ai_triage_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Claude's narrative summary of the allegation and its credibility.",
    )
    credibility_score: Mapped[Optional[float]] = mapped_column(
        Float,
        index=True,
        comment="AI-assessed credibility 0–100. Reports >= 60 surface to investigators.",
    )
    urgency: Mapped[Optional[str]] = mapped_column(
        String(20),
        index=True,
        comment="WhistleblowerUrgency enum value set by AI triage.",
    )
    is_credible: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        comment="Investigator's final credibility judgement (may differ from AI score).",
    )
    # ── Review workflow ────────────────────────────────────────────────────────
    is_reviewed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    reviewed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        comment="Investigator who reviewed this report.",
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tender: Mapped[Optional["Tender"]] = relationship(
        "Tender",
        back_populates="whistleblower_reports",
    )
    reviewed_by: Mapped[Optional["User"]] = relationship("User")

    # ── Composite indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        Index(
            "ix_wb_reports_credibility_reviewed",
            "credibility_score",
            "is_reviewed",
        ),
        Index("ix_wb_reports_urgency_reviewed", "urgency", "is_reviewed"),
    )

    def __repr__(self) -> str:
        return (
            f"<WhistleblowerReport id={self.id} "
            f"allegation={self.allegation_type} "
            f"credibility={self.credibility_score} reviewed={self.is_reviewed}>"
        )
