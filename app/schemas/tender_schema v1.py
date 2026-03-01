import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums_model import RiskLevel, TenderStatus


class TenderCreate(BaseModel):
    tender_number: str
    title: str
    description: Optional[str] = None
    technical_requirements: Optional[str] = None
    # Procuring entity
    procuring_entity: str
    entity_type: Optional[str] = None
    # Classification
    category: Optional[str] = None
    procurement_method: Optional[str] = None
    # Financial
    amount: float
    currency: str = "KES"
    source_of_funds: Optional[str] = None
    # Tender security
    tender_security_form: Optional[str] = None
    tender_security_amount: Optional[float] = None
    # Location & contact
    county: Optional[str] = None
    contact_email: Optional[str] = None
    # Dates
    publication_date: Optional[date] = None
    submission_deadline: Optional[date] = None
    opening_date: Optional[date] = None

    model_config = {"from_attributes": True}


class TenderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    technical_requirements: Optional[str] = None
    procuring_entity: Optional[str] = None
    entity_type: Optional[str] = None
    category: Optional[str] = None
    procurement_method: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    source_of_funds: Optional[str] = None
    tender_security_form: Optional[str] = None
    tender_security_amount: Optional[float] = None
    county: Optional[str] = None
    contact_email: Optional[str] = None
    publication_date: Optional[date] = None
    submission_deadline: Optional[date] = None
    opening_date: Optional[date] = None
    award_date: Optional[date] = None
    awarded_supplier_id: Optional[uuid.UUID] = None
    status: Optional[TenderStatus] = None
    risk_score: Optional[int] = None
    risk_level: Optional[RiskLevel] = None
    is_flagged: Optional[bool] = None

    model_config = {"from_attributes": True}


class TenderResponse(BaseModel):
    id: uuid.UUID
    tender_number: str
    title: str
    description: Optional[str] = None
    technical_requirements: Optional[str] = None
    procuring_entity: str
    entity_type: Optional[str] = None
    category: Optional[str] = None
    procurement_method: Optional[str] = None
    amount: float
    currency: str
    source_of_funds: Optional[str] = None
    tender_security_form: Optional[str] = None
    tender_security_amount: Optional[float] = None
    county: Optional[str] = None
    contact_email: Optional[str] = None
    publication_date: Optional[date] = None
    submission_deadline: Optional[date] = None
    opening_date: Optional[date] = None
    award_date: Optional[date] = None
    awarded_supplier_id: Optional[uuid.UUID] = None
    status: TenderStatus
    risk_score: int
    risk_level: Optional[RiskLevel] = None
    is_flagged: bool
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
