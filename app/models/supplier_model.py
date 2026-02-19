import uuid
from datetime import UTC, date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Numeric

from app.core.database import Base
from app.models.enums_model import RiskLevel


class Supplier(Base):
    """Supplier database model."""

    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    # Company details
    registration_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    business_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    physical_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    postal_address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Tax & Registration
    tax_pin: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    registration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    nca_registration_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    nca_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Contact
    contact_email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Directors & Ownership
    directors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    beneficial_owners: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tax_compliant: Mapped[bool] = mapped_column(Boolean, default=False)
    tax_compliance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Risk Assessment
    risk_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(
        SQLEnum(RiskLevel), nullable=True
    )
    is_ghost_likely: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    blacklist_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Performance history
    total_contracts_won: Mapped[int] = mapped_column(Integer, default=0)
    total_contract_value: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    performance_rating: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    awarded_tenders = relationship("Tender", back_populates="awarded_supplier")
    verification_checks = relationship(
        "SupplierVerificationCheck",
        back_populates="supplier",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, registration_number={self.registration_number}, name={self.name})>"
