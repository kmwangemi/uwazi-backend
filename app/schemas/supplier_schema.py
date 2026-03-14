from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class SupplierBase(BaseModel):
    name: str
    registration_number: Optional[str] = None
    kra_pin: Optional[str] = None
    incorporation_date: Optional[datetime] = None
    address: Optional[str] = None
    county: Optional[str] = None
    directors: Optional[List[Any]] = []
    tax_filings_count: int = 0
    employee_count: Optional[int] = None
    has_physical_address: Optional[bool] = None
    has_online_presence: Optional[bool] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierOut(SupplierBase):
    id: UUID
    company_age_days: Optional[int]
    past_contracts_count: int
    past_contracts_value: float
    risk_score: float
    is_verified: bool
    verification_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        from_attributes = True
