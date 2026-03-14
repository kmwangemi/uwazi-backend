"""
app/models/contract.py
──────────────────────
Contract model — an awarded contract between a procuring entity and a supplier.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.enums import ContractStatus

if TYPE_CHECKING:
    from app.models.supplier_model import Supplier
    from app.models.tender_model import Tender


class Contract(Base):
    """
    An awarded contract linking a Tender to a winning Supplier.

    One-to-one with Tender (unique=True on tender_id).

    Key corruption signal — value_variation_pct:
        The percentage difference between the final contract_value and the
        original estimated_value from the tender.
        Formula: ((contract_value - original_tender_value) / original_tender_value) × 100

        >25%  → contract_variation red flag (MEDIUM severity)
        >50%  → contract_variation red flag (HIGH severity)
        >100% → contract_variation red flag (CRITICAL severity)

    Repeated addenda (variation_count) without justification indicate
    post-award price manipulation — a common kickback mechanism in Kenya.
    """

    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one contract per tender
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # RESTRICT: cannot delete a supplier who has an active contract
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # ── Financial ─────────────────────────────────────────────────────────────
    contract_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Final awarded contract value in KES.",
    )
    original_tender_value: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Estimated value from the tender at publication time.",
    )
    value_variation_pct: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="((contract_value - original_tender_value) / original_tender_value) × 100. "
        "High values indicate post-award price manipulation.",
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="KES",
        nullable=False,
    )
    # ── Timeline ───────────────────────────────────────────────────────────────
    awarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="Actual completion date; may differ from end_date.",
    )
    # ── Status & addenda ───────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        default=ContractStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    variation_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of contract addenda/variations issued post-award.",
    )
    variation_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Justification notes for contract variations.",
    )
    termination_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="contract",
    )
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="contracts",
    )

    def __repr__(self) -> str:
        return (
            f"<Contract id={self.id} tender={self.tender_id} "
            f"value={self.contract_value} variation={self.value_variation_pct}%>"
        )
