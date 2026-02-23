import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums_model import RiskLevel


class SupplierCreate(BaseModel):
    # Company details
    name: str
    registration_number: str
    business_type: Optional[str] = None
    year_registered: Optional[int] = None
    # Tax & Compliance
    tax_pin: Optional[str] = None
    # NCA
    nca_registration_number: Optional[str] = None
    nca_category: Optional[str] = None
    # Classification
    supply_category: Optional[str] = None
    # AGPO
    agpo_group: Optional[str] = None
    agpo_cert_number: Optional[str] = None
    # Location
    county: Optional[str] = None
    physical_address: Optional[str] = None
    postal_address: Optional[str] = None
    business_address: Optional[str] = None
    website: Optional[str] = None
    # Contact
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    # Authorised representative
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None
    # Directors & Ownership
    directors: Optional[list] = None
    beneficial_owners: Optional[list] = None

    model_config = {"from_attributes": True}


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    business_type: Optional[str] = None
    year_registered: Optional[int] = None
    tax_pin: Optional[str] = None
    tax_compliant: Optional[bool] = None
    tax_compliance_date: Optional[date] = None
    nca_registration_number: Optional[str] = None
    nca_category: Optional[str] = None
    supply_category: Optional[str] = None
    agpo_group: Optional[str] = None
    agpo_cert_number: Optional[str] = None
    county: Optional[str] = None
    physical_address: Optional[str] = None
    postal_address: Optional[str] = None
    business_address: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None
    directors: Optional[list] = None
    beneficial_owners: Optional[list] = None
    is_verified: Optional[bool] = None
    is_blacklisted: Optional[bool] = None
    blacklist_reason: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[RiskLevel] = None
    is_ghost_likely: Optional[bool] = None
    performance_rating: Optional[float] = None

    model_config = {"from_attributes": True}


class SupplierResponse(BaseModel):
    id: uuid.UUID
    name: str
    registration_number: str
    business_type: Optional[str] = None
    year_registered: Optional[int] = None
    registration_date: Optional[date] = None
    tax_pin: Optional[str] = None
    tax_compliant: bool
    tax_compliance_date: Optional[date] = None
    nca_registration_number: Optional[str] = None
    nca_category: Optional[str] = None
    supply_category: Optional[str] = None
    agpo_group: Optional[str] = None
    agpo_cert_number: Optional[str] = None
    county: Optional[str] = None
    physical_address: Optional[str] = None
    postal_address: Optional[str] = None
    business_address: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None
    directors: Optional[list] = None
    beneficial_owners: Optional[list] = None
    is_verified: bool
    verification_date: Optional[datetime] = None
    risk_score: int
    risk_level: Optional[RiskLevel] = None
    is_ghost_likely: bool
    is_blacklisted: bool
    blacklist_reason: Optional[str] = None
    total_contracts_won: int
    total_contract_value: float
    performance_rating: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
