from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PriceBenchmarkCreate(BaseModel):
    item_name: str
    category: Optional[str] = None
    unit: Optional[str] = None
    avg_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    source: Optional[str] = None
    county: Optional[str] = None


class PriceBenchmarkOut(PriceBenchmarkCreate):
    id: UUID
    last_updated: datetime

    class Config:
        from_attributes = True
