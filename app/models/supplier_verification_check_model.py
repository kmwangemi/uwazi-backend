import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums_model import VerificationCheckType


class SupplierVerificationCheck(Base):
    """Individual verification checks for suppliers."""

    __tablename__ = "supplier_verification_checks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    check_type: Mapped[VerificationCheckType] = mapped_column(
        SQLEnum(VerificationCheckType), nullable=False, index=True
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    supplier = relationship("Supplier", back_populates="verification_checks")

    def __repr__(self) -> str:
        return f"<SupplierVerificationCheck(id={self.id}, check_type={self.check_type}, passed={self.passed})>"
