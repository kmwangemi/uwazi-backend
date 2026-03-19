"""
app/models/procuring_entity.py
───────────────────────────────
ProcuringEntity model — government ministries, county governments,
state corporations, and constitutional commissions that issue tenders.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tender_model import Tender


class ProcuringEntity(Base):
    """
    A government body that publishes and manages procurement tenders.

    Examples:
        - National Treasury (ministry)
        - Nairobi City County Government (county_government)
        - Kenya Power & Lighting Company (state_corporation)
        - Kenya National Human Rights Commission (constitutional_commission)

    corruption_history_score (0–100) is computed by the risk engine
    from the rolling average of all past tender risk scores for this entity.
    A high score here feeds directly into the entity_history_score component
    of any new tender's RiskScore.
    """

    __tablename__ = "procuring_entities"

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
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="EntityType enum value: ministry / county_government / state_corporation …",
    )
    county: Mapped[Optional[str]] = mapped_column(
        String(100),
        index=True,
        comment="For county-level entities; null for national ministries.",
    )
    code: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        comment="Official PPIP entity code e.g. 'NT', 'NRB-CGV'",
    )
    website: Mapped[Optional[str]] = mapped_column(String(500))
    contact_email: Mapped[Optional[str]] = mapped_column(String(320))
    # Corruption risk profile
    corruption_history_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Rolling average risk score across all past tenders (0–100).",
    )
    investigation_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of confirmed EACC investigations involving this entity.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tenders: Mapped[List["Tender"]] = relationship(
        "Tender",
        back_populates="entity",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<ProcuringEntity id={self.id} name={self.name!r} "
            f"type={self.entity_type} score={self.corruption_history_score}>"
        )
