"""
app/models/tender_document.py
──────────────────────────────
TenderDocument model — PDFs and other files attached to a tender.
"""

from __future__ import annotations

import uuid
from datetime import timezone, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tender_model import Tender


class TenderDocument(Base):
    """
    A document file attached to a Tender.

    Documents are either:
        - Scraped from PPIP alongside the tender notice (is_scraped=True)
        - Uploaded manually by an investigator

    OCR pipeline:
        1. Document uploaded / scraped → extraction_status = 'pending'
        2. Background task runs Tesseract / pdfplumber
        3. extracted_text populated → extraction_status = 'done'
        4. spec_nlp.py analyses extracted_text for restrictive spec patterns

    extracted_text feeds:
        - spec_analyzer.py  → spec restrictiveness score
        - spec_nlp.py       → spaCy NER for brand names, experience reqs
        - collusion.py      → if doc_type = 'bid_submission'
    """

    __tablename__ = "tender_documents"

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
    # File metadata
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(
        String(1000),
        comment="Relative path in the file storage volume.",
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="e.g. 'application/pdf', 'application/vnd.openxmlformats-officedocument'",
    )
    doc_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="DocumentType enum value.",
    )
    # OCR / extraction
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="OCR / pdfplumber output; fed to spec analysis and collusion detection.",
    )
    extraction_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="pending / done / failed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTtimezone.utcC)
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="documents",
    )

    def __repr__(self) -> str:
        return (
            f"<TenderDocument id={self.id} filename={self.filename!r} "
            f"type={self.doc_type} status={self.extraction_status}>"
        )
