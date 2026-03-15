"""
app/models/tender.py
────────────────────
Tender model — the core procurement entity in the system.
"""

from __future__ import annotations

import uuid
from datetime import timezone, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.enums import TenderStatus

if TYPE_CHECKING:
    from app.models.bid_model import Bid
    from app.models.contract_model import Contract
    from app.models.procuring_entity_model import ProcuringEntity
    from app.models.red_flag_model import RedFlag
    from app.models.risk_score_model import RiskScore
    from app.models.tender_document_model import TenderDocument
    from app.models.whistleblower_report_model import WhistleblowerReport


class Tender(Base):
    """
    A single procurement tender published by a government entity.

    Tenders are either scraped from PPIP (supplier.treasury.go.ke) and
    the Kenya Gazette, or entered manually by investigators.

    The full corruption-detection pipeline runs on each tender:
      1. Price deviation  → price_score     (IsolationForest)
      2. Supplier risk    → supplier_score  (RandomForest + IsolationForest)
      3. Spec analysis    → spec_score      (spaCy NER)
      4. Bid collusion    → collusion_score (TF-IDF cosine similarity)
      5. Composite score  → total_score     (XGBoost when trained)
      6. AI narrative     → ai_analysis     (Claude claude-opus-4-6)

    Results are stored in the related RiskScore record.
    Individual issues are stored as RedFlag records.
    """

    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    reference_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        unique=True,
        index=True,
        comment="Official PPIP / Gazette reference e.g. 'KEBS/OT/2026/001'",
    )
    title: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    # Category
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        comment="TenderCategory enum value: works / goods / services / ict …",
    )
    category_raw: Mapped[Optional[str]] = mapped_column(
        String(200),
        comment="Original scraped category string before normalisation.",
    )
    # Financial
    estimated_value: Mapped[Optional[float]] = mapped_column(
        Float,
        index=True,
        comment="Estimated contract value in KES.",
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="KES",
        nullable=False,
    )
    # Location
    county: Mapped[Optional[str]] = mapped_column(
        String(100),
        index=True,
    )
    # Procurement metadata
    procurement_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        comment="ProcurementMethod enum value per PPADA 2015.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=TenderStatus.OPEN,
        nullable=False,
        index=True,
    )
    submission_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    opening_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="Date bids are publicly opened.",
    )
    # Source tracking
    source_url: Mapped[Optional[str]] = mapped_column(String(2000))
    source: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Data source identifier: 'ppip' / 'gazette' / 'manual'",
    )
    is_scraped: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # ── Foreign keys ───────────────────────────────────────────────────────────
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        # SET NULL so deleting an entity doesn't cascade-delete all its tenders
        __import__("sqlalchemy").ForeignKey(
            "procuring_entities.id", ondelete="SET NULL"
        ),
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    entity: Mapped[Optional["ProcuringEntity"]] = relationship(
        "ProcuringEntity",
        back_populates="tenders",
        lazy="select",
    )
    bids: Mapped[List["Bid"]] = relationship(
        "Bid",
        back_populates="tender",
        cascade="all, delete-orphan",
        lazy="select",
    )
    contract: Mapped[Optional["Contract"]] = relationship(
        "Contract",
        back_populates="tender",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )
    risk_score: Mapped[Optional["RiskScore"]] = relationship(
        "RiskScore",
        back_populates="tender",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )
    red_flags: Mapped[List["RedFlag"]] = relationship(
        "RedFlag",
        back_populates="tender",
        cascade="all, delete-orphan",
        lazy="select",
    )
    documents: Mapped[List["TenderDocument"]] = relationship(
        "TenderDocument",
        back_populates="tender",
        cascade="all, delete-orphan",
        lazy="select",
    )
    whistleblower_reports: Mapped[List["WhistleblowerReport"]] = relationship(
        "WhistleblowerReport",
        back_populates="tender",
        lazy="select",
    )
    alerts = relationship("Alert", back_populates="tender", lazy="selectin")

    # ── Composite indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_tenders_county_status", "county", "status"),
        Index("ix_tenders_county_category", "county", "category"),
        Index("ix_tenders_created_at", "created_at"),
        Index("ix_tenders_estimated_value", "estimated_value"),
    )

    def __repr__(self) -> str:
        return (
            f"<Tender id={self.id} ref={self.reference_number!r} "
            f"status={self.status} value={self.estimated_value}>"
        )
