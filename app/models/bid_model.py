import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Numeric

from app.core.database import Base


class Bid(Base):
    """Supplier bid on a tender."""

    __tablename__ = "bids"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True
    )
    # ── Relations ─────────────────────────────────────────────────────────────
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # ── Financial ─────────────────────────────────────────────────────────────
    quote_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    delivery_timeline: Mapped[int] = mapped_column(Integer, nullable=False)  # days
    payment_terms: Mapped[str] = mapped_column(String(100), nullable=False)
    warranty: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # ── Proposal Text ─────────────────────────────────────────────────────────
    technical_proposal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_mitigation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_approach: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ── Documents (Cloudinary metadata) ───────────────────────────────────────
    technical_documents: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    financial_documents: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    compliance_documents: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # ── Status ────────────────────────────────────────────────────────────────
    terms_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    bid_reference: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="submitted", index=True
    )  # submitted | under_review | accepted | rejected
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
    tender = relationship("Tender", back_populates="bids")
    supplier = relationship("Supplier", back_populates="bids")

    def __repr__(self) -> str:
        return (
            f"<Bid(id={self.id}, reference={self.bid_reference}, status={self.status})>"
        )
