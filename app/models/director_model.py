"""
app/models/director.py
──────────────────────
Director model — company directors associated with a Supplier.

Normalised into its own table (not a JSON column) so we can:
  - JOIN across suppliers to find shared directors (collusion / PEP signal)
  - Index by national_id for watchlist cross-referencing
  - Count director_company_count efficiently with SQL aggregates
"""

from __future__ import annotations

import uuid
from datetime import timezone, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.supplier_model import Supplier


class Director(Base):
    """
    A named director or beneficial owner of a Supplier company.

    is_politically_exposed flags directors who are PEPs (Politically Exposed
    Persons) — government officials, their relatives, or close associates.
    A PEP director is a strong corruption risk indicator.

    Cross-supplier director queries:
        SELECT d.full_name, COUNT(DISTINCT d.supplier_id)
        FROM directors d
        GROUP BY d.national_id, d.full_name
        HAVING COUNT(DISTINCT d.supplier_id) > 1;
    This detects shell companies with the same beneficial owner.
    """

    __tablename__ = "directors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # CASCADE: deleting a supplier removes all its director records
        __import__("sqlalchemy").ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    national_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        comment="Kenya National ID or passport number; used for watchlist matching.",
    )
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(320))
    role_title: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="e.g. 'Managing Director', 'Chairperson', 'Secretary'",
    )
    is_politically_exposed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="True if director is a PEP — raises corruption risk score.",
    )
    pep_details: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="Free-text description of political exposure if is_politically_exposed=True.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="directors",
    )

    # ── Composite indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        Index(
            "ix_directors_supplier_national_id",
            "supplier_id",
            "national_id",
        ),
        Index(
            "ix_directors_national_id",
            "national_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Director id={self.id} name={self.full_name!r} "
            f"supplier={self.supplier_id} pep={self.is_politically_exposed}>"
        )
