import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BidDocumentMeta(BaseModel):
    url: str
    public_id: str
    file_name: str
    file_type: Optional[str] = None
    size: Optional[int] = None


class BidCreate(BaseModel):
    tender_id: uuid.UUID
    supplier_id: uuid.UUID
    quote_price: float = Field(gt=0)
    delivery_timeline: int = Field(gt=0)  # days
    payment_terms: str
    warranty: Optional[str] = None
    technical_proposal: Optional[str] = None
    risk_mitigation: Optional[str] = None
    quality_approach: Optional[str] = None
    terms_accepted: bool

    model_config = {"from_attributes": True}


class BidResponse(BaseModel):
    id: uuid.UUID
    tender_id: uuid.UUID
    supplier_id: uuid.UUID
    submitted_by: uuid.UUID
    quote_price: float
    delivery_timeline: int
    payment_terms: str
    warranty: Optional[str] = None
    technical_proposal: Optional[str] = None
    risk_mitigation: Optional[str] = None
    quality_approach: Optional[str] = None
    technical_documents: Optional[list[BidDocumentMeta]] = []
    financial_documents: Optional[list[BidDocumentMeta]] = []
    compliance_documents: Optional[list[BidDocumentMeta]] = []
    terms_accepted: bool
    bid_reference: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BidUpdate(BaseModel):
    status: Optional[str] = None  # admin use: accept / reject
    quote_price: Optional[float] = None
    delivery_timeline: Optional[int] = None
    payment_terms: Optional[str] = None
    warranty: Optional[str] = None
    technical_proposal: Optional[str] = None
    risk_mitigation: Optional[str] = None
    quality_approach: Optional[str] = None

    model_config = {"from_attributes": True}
