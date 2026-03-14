"""
app/models/risk_score.py
────────────────────────
RiskScore model — composite ML + AI corruption analysis for a single tender.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.enums import RiskLevel

if TYPE_CHECKING:
    from app.models.tender_model import Tender


class RiskScore(Base):
    """
    The composite corruption risk assessment for a single Tender.

    One-to-one with Tender (unique=True on tender_id).
    Written and updated by services/risk_engine.py.

    Component scores (0–100 each) — higher = more suspicious:
    ┌──────────────────────┬───────────────────────────────────────────┐
    │ price_score          │ IsolationForest price deviation vs        │
    │                      │ PriceBenchmark market data                │
    ├──────────────────────┼───────────────────────────────────────────┤
    │ supplier_score       │ RandomForest + IsolationForest ghost-     │
    │                      │ supplier probability                      │
    ├──────────────────────┼───────────────────────────────────────────┤
    │ spec_score           │ spaCy NER restrictiveness — brand names,  │
    │                      │ experience reqs, single-source language   │
    ├──────────────────────┼───────────────────────────────────────────┤
    │ contract_value_score │ Post-award value_variation_pct (inflation)│
    ├──────────────────────┼───────────────────────────────────────────┤
    │ entity_history_score │ ProcuringEntity.corruption_history_score  │
    ├──────────────────────┼───────────────────────────────────────────┤
    │ collusion_score      │ TF-IDF cosine similarity across all bids  │
    └──────────────────────┴───────────────────────────────────────────┘

    Composite:
        xgb_score   — XGBoost classifier score when model is trained;
                      replaces the weighted-average formula as primary signal.
        total_score — final composite (0–100) written to risk_level band.

    Risk level bands:
        0–39   LOW
        40–59  MEDIUM
        60–79  HIGH
        80–100 CRITICAL
    """

    __tablename__ = "risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # ── Component scores (0–100) ──────────────────────────────────────────────
    price_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    supplier_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    spec_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contract_value_score: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    entity_history_score: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    collusion_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # ── XGBoost composite (null until model is trained) ───────────────────────
    xgb_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="XGBoost classifier output (0–100). Null until POST /api/ml/train/xgboost-synthetic.",
    )
    # ── Final composite ────────────────────────────────────────────────────────
    total_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        index=True,
    )
    risk_level: Mapped[str] = mapped_column(
        String(10),
        default=RiskLevel.LOW,
        nullable=False,
        index=True,
    )
    # ── AI / ML output ─────────────────────────────────────────────────────────
    flags: Mapped[Optional[list]] = mapped_column(
        JSONB,
        default=list,
        comment='List of human-readable flag strings e.g. ["Price 340% above benchmark"]',
    )
    ai_analysis: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Claude claude-opus-4-6 narrative risk analysis in Markdown.",
    )
    recommended_action: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Claude-generated recommended next step for investigators.",
    )
    # ── Audit trail ────────────────────────────────────────────────────────────
    models_used: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment='Which ML models ran e.g. {"price_anomaly": true, "xgboost": false}',
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="risk_score",
    )

    def __repr__(self) -> str:
        return (
            f"<RiskScore tender={self.tender_id} "
            f"total={self.total_score} level={self.risk_level}>"
        )
