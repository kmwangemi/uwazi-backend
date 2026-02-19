import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums_model import ReportCategory, ReportPriority, ReportStatus


class WhistleblowerReport(Base):
    """Anonymous whistleblower reports."""

    __tablename__ = "whistleblower_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    # Anonymous tracking
    anonymous_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    tracking_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    # Report details
    category: Mapped[ReportCategory] = mapped_column(
        SQLEnum(ReportCategory), nullable=False, index=True
    )
    tender_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Evidence files
    evidence_files: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Status & Priority
    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(ReportStatus), default=ReportStatus.SUBMITTED, index=True
    )
    priority: Mapped[ReportPriority] = mapped_column(
        SQLEnum(ReportPriority), default=ReportPriority.MEDIUM
    )
    # Investigation
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Resolution
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Metadata
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<WhistleblowerReport(id={self.id}, tracking_id={self.tracking_id}, category={self.category})>"
