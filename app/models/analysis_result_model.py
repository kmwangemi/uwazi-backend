import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums_model import AnalysisType, RiskLevel


class AnalysisResult(Base):
    """Stores detailed analysis results for tenders."""

    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, index=True
    )
    # Analysis type
    analysis_type: Mapped[AnalysisType] = mapped_column(
        SQLEnum(AnalysisType), nullable=False, index=True
    )
    # Results
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(
        SQLEnum(RiskLevel), nullable=True
    )
    findings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Model/Version info
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    analysis_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Metadata
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    tender = relationship("Tender", back_populates="analysis_results")

    def __repr__(self) -> str:
        return f"<AnalysisResult(id={self.id}, analysis_type={self.analysis_type}, tender_id={self.tender_id})>"
