import uuid
from datetime import UTC, date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums_model import NetworkRelationshipType


class NetworkEdge(Base):
    """Network graph edges for relationships."""

    __tablename__ = "network_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_nodes.id"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_nodes.id"), nullable=False, index=True
    )
    relationship_type: Mapped[NetworkRelationshipType] = mapped_column(
        SQLEnum(NetworkRelationshipType), nullable=False, index=True
    )
    # Relationship details
    edge_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    strength: Mapped[int] = mapped_column(Integer, default=1)
    # Validity
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<NetworkEdge(id={self.id}, source={self.source_node_id}, relationship={self.relationship_type}, target={self.target_node_id})>"
