from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class BidCreate(BaseModel):
    tender_id: UUID
    supplier_id: UUID
    bid_amount: float
    currency: str = "KES"
    submitted_at: Optional[datetime] = None
    proposal_text: Optional[str] = None


class BidOut(BidCreate):
    id: UUID
    is_winner: bool
    similarity_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True
