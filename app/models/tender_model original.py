import uuid
from datetime import UTC, date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Numeric

from app.core.database import Base
from app.models.enums_model import RiskLevel, TenderStatus


class Tender(Base):
    """Tender database model."""

    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    tender_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technical_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Financial
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="KES")
    # Organization details
    procuring_entity: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True
    )
    county: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    # Dates
    publication_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    submission_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    award_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Award details
    awarded_supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True
    )
    # Status
    status: Mapped[TenderStatus] = mapped_column(
        SQLEnum(TenderStatus), default=TenderStatus.PUBLISHED, index=True
    )
    # Document details
    source_document_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    source_document_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    # Extracted data
    items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    specifications: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    bidders: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Risk & Analysis
    risk_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(
        SQLEnum(RiskLevel), nullable=True
    )
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    awarded_supplier = relationship("Supplier", back_populates="awarded_tenders")
    alerts = relationship(
        "Alert", back_populates="tender", cascade="all, delete-orphan"
    )
    analysis_results = relationship(
        "AnalysisResult", back_populates="tender", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tender(id={self.id}, tender_number={self.tender_number}, status={self.status})>"
