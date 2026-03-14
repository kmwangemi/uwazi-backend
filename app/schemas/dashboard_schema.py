from typing import List

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_tenders: int
    high_risk_tenders: int
    critical_tenders: int
    avg_price_deviation_pct: float
    total_contract_value: float
    total_suppliers: int
    flagged_suppliers: int
    tenders_by_risk: dict
    tenders_by_county: List[dict]
    recent_critical_tenders: List[dict]


class CountyHeatmap(BaseModel):
    county: str
    avg_risk_score: float
    tender_count: int
    high_risk_count: int
