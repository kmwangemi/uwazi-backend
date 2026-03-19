"""
app/models/supplier.py
──────────────────────
Supplier model — registered companies and individuals that bid on government tenders.
Companion model Director is in director.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.enums import SupplierVerificationStatus

if TYPE_CHECKING:
    from app.models.bid_model import Bid
    from app.models.contract_model import Contract
    from app.models.director_model import Director


class Supplier(Base):
    """
    A company or individual vendor registered to supply goods/services to government.

    ML feature columns (used by supplier_risk.py):
        company_age_days       — young companies with large contracts are suspect
        tax_filings_count      — ghost suppliers typically have zero or one filing
        has_physical_address   — ghost suppliers rarely have a verifiable address
        has_online_presence    — no web presence is a ghost indicator
        past_contracts_count   — sudden contract wins with no history = suspicious
        past_contracts_value   — disproportionate value relative to company size

    Directors are stored in a separate Director table (not JSON) so we can:
        - query cross-supplier shared directors (collusion / PEP signal)
        - index by national_id for cross-referencing with EACC watchlists
    """

    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    registration_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        index=True,
        comment="Companies Registry registration number",
    )
    kra_pin: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        comment="Kenya Revenue Authority Personal Identification Number",
    )
    incorporation_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    company_age_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Computed from incorporation_date; updated on supplier refresh.",
    )
    address: Mapped[Optional[str]] = mapped_column(String(500))
    county: Mapped[Optional[str]] = mapped_column(
        String(100),
        index=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(320))
    # ── ML feature columns ─────────────────────────────────────────────────────
    tax_filings_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    has_physical_address: Mapped[Optional[bool]] = mapped_column(Boolean)
    has_online_presence: Mapped[Optional[bool]] = mapped_column(Boolean)
    past_contracts_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    past_contracts_value: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    # ── Risk scoring ───────────────────────────────────────────────────────────
    risk_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        index=True,
        comment="Composite ghost-supplier risk score (0–100); written by risk engine.",
    )
    # ── Verification / status ─────────────────────────────────────────────────
    verification_status: Mapped[str] = mapped_column(
        String(20),
        default=SupplierVerificationStatus.UNVERIFIED,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_blacklisted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    verification_notes: Mapped[Optional[str]] = mapped_column(Text)
    blacklist_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    directors: Mapped[List["Director"]] = relationship(
        "Director",
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="select",
    )
    bids: Mapped[List["Bid"]] = relationship(
        "Bid",
        back_populates="supplier",
        lazy="select",
    )
    contracts: Mapped[List["Contract"]] = relationship(
        "Contract",
        back_populates="supplier",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Supplier id={self.id} name={self.name!r} "
            f"risk={self.risk_score} verified={self.is_verified}>"
        )
