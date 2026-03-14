"""
app/models/price_benchmark.py
──────────────────────────────
PriceBenchmark model — market reference prices used for deviation analysis.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceBenchmark(Base):
    """
    A market reference price for a category of goods or services.

    Used by services/price_analyzer.py and the IsolationForest price anomaly
    model (ml/price_anomaly.py) to calculate how far a tender's estimated
    value deviates from expected market pricing.

    Deviation formula:
        deviation_pct = ((tender_price - avg_price) / avg_price) × 100

    Seeded with 24 Kenya-specific benchmarks in app/seed.py, including:
        - Cement (KES 750/bag)
        - Road construction (KES 21.5M/km)
        - Laptops (KES 80K each)
        - Land Cruiser (KES 9.5M)
        - Textbooks, drugs, medical equipment, etc.

    Data sources:
        - Kenya National Treasury price schedules
        - PPIP historical contract award data
        - Kenya National Bureau of Statistics (KNBS) price indices

    std_dev enables z-score calculation for more precise anomaly detection
    once enough historical data is available.
    """

    __tablename__ = "price_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    item_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(200),
        index=True,
    )
    subcategory: Mapped[Optional[str]] = mapped_column(String(200))
    unit: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Unit of measure: 'per bag', 'per km', 'each', 'per m²', etc.",
    )
    # Price statistics (all in KES)
    avg_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Market average price in KES.",
    )
    min_price: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Observed minimum price in KES.",
    )
    max_price: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Observed maximum price in KES.",
    )
    std_dev: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Standard deviation for z-score anomaly detection.",
    )
    # Source metadata
    source: Mapped[Optional[str]] = mapped_column(
        String(300),
        comment="e.g. 'Kenya Treasury Price Schedule 2025', 'PPIP Historical Awards'",
    )
    county: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="For region-specific benchmarks; null = national average.",
    )
    year: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Reference year for this price data.",
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # ── Composite indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_price_benchmarks_item_category", "item_name", "category"),
        Index("ix_price_benchmarks_category", "category"),
    )

    def __repr__(self) -> str:
        return (
            f"<PriceBenchmark item={self.item_name!r} "
            f"avg={self.avg_price} unit={self.unit!r}>"
        )
