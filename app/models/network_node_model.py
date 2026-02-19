import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums_model import NetworkNodeType


class NetworkNode(Base):
    """Network graph nodes for relationship mapping."""

    __tablename__ = "network_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    node_type: Mapped[NetworkNodeType] = mapped_column(
        SQLEnum(NetworkNodeType), nullable=False, index=True
    )
    node_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Additional data
    node_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Risk
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return (
            f"<NetworkNode(id={self.id}, node_type={self.node_type}, name={self.name})>"
        )
