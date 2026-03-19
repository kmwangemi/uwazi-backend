"""
app/models/bid.py
─────────────────
Bid model — a supplier's submission for a specific tender.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.enums import BidStatus

if TYPE_CHECKING:
    from app.models.supplier_model import Supplier
    from app.models.tender_model import Tender


class Bid(Base):
    """
    A bid submitted by a Supplier in response to a Tender.

    Collusion detection fields:
        proposal_text    — full proposal text; fed to TF-IDF collusion.py
        similarity_score — cosine similarity vs other bids on same tender (0–1)
                           scores above 0.75 trigger a COLLUSION red flag

    Evaluation fields:
        technical_score  — evaluator's technical score
        financial_score  — evaluator's financial score
        is_winner        — True for the single winning bid
        status           — tracks evaluation lifecycle

    Unique constraint on (tender_id, supplier_id) prevents a supplier
    from submitting duplicate bids on the same tender.
    """

    __tablename__ = "bids"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ── Financial ─────────────────────────────────────────────────────────────
    bid_amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Bid amount in KES.",
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="KES",
        nullable=False,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    # ── Collusion detection ────────────────────────────────────────────────────
    proposal_text: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Full proposal text; fed to TF-IDF collusion analysis.",
    )
    similarity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Max cosine similarity vs all other bids on this tender (0–1). "
        "Values above 0.75 indicate potential collusion.",
    )
    # ── Evaluation ─────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        default=BidStatus.SUBMITTED,
        nullable=False,
    )
    is_winner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    technical_score: Mapped[Optional[float]] = mapped_column(Float)
    financial_score: Mapped[Optional[float]] = mapped_column(Float)
    evaluation_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="bids",
    )
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="bids",
    )

    # ── Constraints & indexes ─────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "tender_id",
            "supplier_id",
            name="uq_bid_tender_supplier",
        ),
        Index("ix_bids_tender_is_winner", "tender_id", "is_winner"),
        Index("ix_bids_tender_similarity", "tender_id", "similarity_score"),
    )

    def __repr__(self) -> str:
        return (
            f"<Bid id={self.id} tender={self.tender_id} "
            f"supplier={self.supplier_id} amount={self.bid_amount} winner={self.is_winner}>"
        )
