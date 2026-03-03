import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums_model import RiskLevel, TenderStatus


class TenderAttachment(BaseModel):
    url: str
    public_id: str
    file_name: str
    file_type: Optional[str] = None
    size: Optional[int] = None


class TenderCreate(BaseModel):
    tender_number: str
    title: str
    description: Optional[str] = None
    technical_requirements: Optional[str] = None
    # Procuring entity — matches model column `entity_name`
    entity_name: str = Field(alias="entityName")
    entity_type: Optional[str] = Field(default=None, alias="entityType")
    # Classification
    category: Optional[str] = None
    procurement_method: Optional[str] = Field(default=None, alias="procurementMethod")
    # Financial
    amount: float
    currency: str = "KES"
    source_of_funds: Optional[str] = Field(default=None, alias="sourceOfFunds")
    # Tender security
    tender_security_form: Optional[str] = Field(
        default=None, alias="tenderSecurityForm"
    )
    tender_security_amount: Optional[float] = Field(
        default=None, alias="tenderSecurityAmount"
    )
    # Location & contact
    county: Optional[str] = None
    contact_email: Optional[str] = Field(default=None, alias="contactEmail")
    # Dates — matches model column `deadline`
    publication_date: Optional[date] = Field(default=None, alias="publicationDate")
    deadline: Optional[date] = None
    opening_date: Optional[date] = Field(default=None, alias="openingDate")
    attachments: Optional[list[TenderAttachment]] = []  # populated after upload

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,  # allows both snake_case and camelCase
    }


class TenderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    technical_requirements: Optional[str] = None
    entity_name: Optional[str] = None  # was procuring_entity
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
    deadline: Optional[date] = None  # was submission_deadline
    opening_date: Optional[date] = None
    award_date: Optional[date] = None
    awarded_supplier_id: Optional[uuid.UUID] = None
    status: Optional[TenderStatus] = None
    risk_score: Optional[int] = None
    risk_level: Optional[RiskLevel] = None
    is_flagged: Optional[bool] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class TenderResponse(BaseModel):
    id: uuid.UUID
    tender_number: str
    title: str
    description: Optional[str] = None
    technical_requirements: Optional[str] = None
    entity_name: str  # was procuring_entity
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
    deadline: Optional[date] = None  # was submission_deadline
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
