import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProcuringEntityResponse(BaseModel):
    id: uuid.UUID
    entity_code: str
    name: str
    entity_type: str
    county: Optional[str] = None
    total_tenders: int
    total_expenditure: float
    flagged_tenders: int
    average_corruption_score: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProcuringEntityListResponse(BaseModel):
    total: int
    items: list[ProcuringEntityResponse]
