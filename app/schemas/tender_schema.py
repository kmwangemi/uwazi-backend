from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.enums import ProcurementMethod, RiskLevel, TenderStatus


class TenderBase(BaseModel):
    reference_number: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    estimated_value: Optional[float] = None
    currency: str = "KES"
    county: Optional[str] = None
    procurement_method: Optional[ProcurementMethod] = None
    status: Optional[TenderStatus] = TenderStatus.OPEN
    submission_deadline: Optional[datetime] = None
    source_url: Optional[str] = None
    source: Optional[str] = None
    entity_id: Optional[UUID] = None


class TenderCreate(TenderBase):
    pass


class TenderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_value: Optional[float] = None
    status: Optional[TenderStatus] = None
    submission_deadline: Optional[datetime] = None


class RiskScoreOut(BaseModel):
    id: UUID
    price_score: float
    supplier_score: float
    spec_score: float
    contract_value_score: float
    entity_history_score: float
    total_score: float
    risk_level: RiskLevel
    flags: List[str]
    ai_analysis: Optional[str]
    recommended_action: Optional[str]
    computed_at: datetime

    class Config:
        from_attributes = True


class RedFlagOut(BaseModel):
    id: UUID
    flag_type: str
    severity: str
    description: str
    evidence: Any
    created_at: datetime

    class Config:
        from_attributes = True


class TenderOut(TenderBase):
    id: UUID
    is_scraped: bool
    created_at: datetime
    updated_at: datetime
    risk_score: Optional[RiskScoreOut] = None
    red_flags: Optional[List[RedFlagOut]] = []

    class Config:
        from_attributes = True


class TenderListOut(BaseModel):
    id: UUID
    reference_number: Optional[str]
    title: str
    category: Optional[str]
    estimated_value: Optional[float]
    county: Optional[str]
    status: Optional[TenderStatus]
    submission_deadline: Optional[datetime]
    risk_level: Optional[RiskLevel] = None  # joined from risk_scores
    total_risk_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True
