"""
app/models/investigation_model.py
──────────────────────────────────
Investigation model — tracks active corruption investigations on tenders.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tender_model import Tender
    from app.models.user_model import User


class Investigation(Base):
    """
    An active corruption investigation opened on a tender.

    Workflow:
        open → in_review → escalated → closed
    """

    __tablename__ = "investigations"

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
    title: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    tender_ref: Mapped[Optional[str]] = mapped_column(
        String(200),
        comment="Denormalised tender reference for fast display.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        nullable=False,
        index=True,
        comment="open | in_review | escalated | closed",
    )
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        index=True,
        comment="critical | high | medium | low — copied from RiskScore at open time.",
    )
    findings: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Investigator's running notes and key findings.",
    )
    investigator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    investigator_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Denormalised for display without joining users table.",
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tender: Mapped["Tender"] = relationship("Tender", lazy="select")
    investigator: Mapped[Optional["User"]] = relationship("User", lazy="select")

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_investigations_status_risk", "status", "risk_level"),
        Index("ix_investigations_opened_at", "opened_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Investigation id={self.id} tender={self.tender_id} "
            f"status={self.status} risk={self.risk_level}>"
        )
