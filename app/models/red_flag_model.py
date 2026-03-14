"""
app/models/red_flag.py
──────────────────────
RedFlag model — an individual corruption indicator detected on a tender.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tender_model import Tender


class RedFlag(Base):
    """
    A single corruption indicator on a Tender.

    A tender may have multiple RedFlags of different types and severities.
    They are displayed as cards in the frontend "Risk & Flags" tab.

    evidence is a JSONB field — its schema varies by flag_type:

    price_inflation:
        {"tender_price": 5000000, "benchmark_avg": 1200000, "deviation_pct": 316.7}

    ghost_supplier:
        {"company_age_days": 45, "tax_filings_count": 0, "has_physical_address": false}

    collusion:
        {"bid_a_id": "...", "bid_b_id": "...", "similarity_score": 0.91,
         "matching_phrases": ["as per the specifications provided", "ISO 9001 certified"]}

    spec_restriction:
        {"brand_names": ["Cisco", "HP"], "experience_years_required": 20,
         "single_source_phrases": ["only authorised dealer"]}

    contract_variation:
        {"original_value": 5000000, "final_value": 12000000, "variation_pct": 140.0,
         "variation_count": 4}

    source_model tracks which ML model detected this flag for audit purposes.
    """

    __tablename__ = "red_flags"

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
    flag_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="FlagType enum value.",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="FlagSeverity enum value.",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable description shown in the frontend flag card.",
    )
    evidence: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="Structured supporting data — schema varies by flag_type (see docstring).",
    )
    source_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="ML model that generated this flag e.g. 'isolation_forest', 'spacy_ner', 'xgboost'",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="red_flags",
    )

    # ── Composite indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_red_flags_tender_severity", "tender_id", "severity"),
        Index("ix_red_flags_type_severity", "flag_type", "severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<RedFlag tender={self.tender_id} "
            f"type={self.flag_type} severity={self.severity}>"
        )
