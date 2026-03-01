import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums_model import RiskLevel


class SupplierCreate(BaseModel):
    # ── Company Identity ─────────────────────────────────────────────────────
    name: str = Field(..., min_length=2)
    business_type: Optional[str] = Field(None, alias="businessType")
    registration_number: str = Field(..., alias="registrationNumber", min_length=3)
    tax_pin: Optional[str] = Field(None, alias="taxNumber")
    year_registered: Optional[int] = Field(None, alias="yearRegistered")
    # ── Supply Classification ────────────────────────────────────────────────
    supply_category: Optional[str] = Field(None, alias="category")
    agpo_group: Optional[str] = Field(None, alias="agpoGroup")
    agpo_cert_number: Optional[str] = Field(None, alias="agpoCertNumber")
    # ── Contact Details ──────────────────────────────────────────────────────
    contact_email: Optional[EmailStr] = Field(None, alias="email")
    contact_phone: Optional[str] = Field(None, alias="phone")
    county: Optional[str] = None
    physical_address: Optional[str] = Field(None, alias="physicalAddress")
    postal_address: Optional[str] = Field(None, alias="postalAddress")
    # ── Authorised Representative ────────────────────────────────────────────
    contact_person_name: Optional[str] = Field(None, alias="contactPersonName")
    contact_person_title: Optional[str] = Field(None, alias="contactPersonTitle")
    # ── Compliance (validated, not persisted) ────────────────────────────────
    declaration_accepted: bool = Field(..., alias="declarationAccepted")

    @field_validator("declaration_accepted")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Compliance declaration must be accepted")
        return v

    @field_validator("year_registered", mode="before")
    @classmethod
    def coerce_year(cls, v: str | int | None) -> Optional[int]:
        """Frontend sends yearRegistered as a string e.g. '2021'."""
        if v is None or v == "":
            return None
        return int(v)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,  # allows snake_case internally too
    }


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
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None
    directors: Optional[list] = None
    beneficial_owners: Optional[list] = None
    is_verified: Optional[bool] = None
    is_blacklisted: Optional[bool] = None
    blacklist_reason: Optional[str] = None
    risk_score: Optional[int] = Field(None, ge=0, le=100)
    risk_level: Optional[RiskLevel] = None
    is_ghost_likely: Optional[bool] = None
    performance_rating: Optional[float] = Field(None, ge=0, le=5)

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
