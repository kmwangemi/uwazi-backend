import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProcuringEntity(Base):
    """Procuring entity — auto-created when a tender is submitted."""

    __tablename__ = "procuring_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True
    )
    entity_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OTHER"
    )  # MINISTRY | COUNTY | PARASTATAL | OTHER
    county: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Computed / aggregated stats ───────────────────────────────────────────
    total_tenders: Mapped[int] = mapped_column(Integer, default=0)
    total_expenditure: Mapped[float] = mapped_column(Float, default=0.0)
    flagged_tenders: Mapped[int] = mapped_column(Integer, default=0)
    average_corruption_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Metadata ──────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenders = relationship("Tender", back_populates="procuring_entity")

    def __repr__(self) -> str:
        return f"<ProcuringEntity(code={self.entity_code}, name={self.name})>"