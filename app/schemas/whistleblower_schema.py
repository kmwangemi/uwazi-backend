from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WhistleblowerCreate(BaseModel):
    report_text: Optional[str] = Field(None, min_length=50)
    description: Optional[str] = Field(None, min_length=50)
    allegation_type: Optional[str] = None
    tender_id: Optional[UUID] = None
    tender_reference: Optional[str] = None
    entity_name: Optional[str] = None
    evidence_description: Optional[str] = None
    contact_preference: Optional[str] = "none"

    def get_report_text(self) -> str:
        return self.report_text or self.description or ""


class WhistleblowerOut(BaseModel):
    id: UUID
    allegation_type: Optional[str]
    ai_triage_summary: Optional[str]
    credibility_score: Optional[float]
    is_reviewed: bool
    submitted_at: datetime

    class Config:
        from_attributes = True
