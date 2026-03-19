from datetime import datetime, timedelta, timezone

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.red_flag_model import RedFlag
from app.models.risk_score_model import RiskScore
from app.models.tender_model import Tender


def _risk_level(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


LABEL_MAP = {
    "ghost_supplier": "Ghost Suppliers",
    "price_inflation": "Price Deviation",
    "collusion": "Bid Rigging",
    "spec_restriction": "Specification Issue",
    "contract_variation": "Contract Variation",
}

COLOR_MAP = {
    "ghost_supplier": "#00ff88",
    "price_inflation": "#ef4444",
    "collusion": "#f59e0b",
    "spec_restriction": "#64748b",
    "contract_variation": "#818cf8",
}

MONTH_ABBR = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


async def get_county_risk(db: AsyncSession) -> list[dict]:
    # Tender counts + total value per county
    county_stats = (
        await db.execute(
            select(
                Tender.county,
                func.count(Tender.id).label("tender_count"),
                func.coalesce(func.sum(Tender.estimated_value), 0).label("total_value"),
            )
            .filter(Tender.county.isnot(None))
            .group_by(Tender.county)
        )
    ).all()

    # Average risk score per county
    risk_rows = (
        await db.execute(
            select(
                Tender.county,
                func.avg(RiskScore.total_score).label("avg_risk_score"),
            )
            .join(RiskScore, RiskScore.tender_id == Tender.id)
            .filter(Tender.county.isnot(None))
            .group_by(Tender.county)
        )
    ).all()
    risk_score_map = {r.county: round(r.avg_risk_score or 0, 1) for r in risk_rows}

    # Red flag counts per county per type
    flag_rows = (
        await db.execute(
            select(
                Tender.county,
                RedFlag.flag_type,
                func.count(RedFlag.id).label("count"),
            )
            .join(RedFlag, RedFlag.tender_id == Tender.id)
            .filter(Tender.county.isnot(None))
            .group_by(Tender.county, RedFlag.flag_type)
        )
    ).all()
    flag_map: dict[str, dict[str, int]] = {}
    for row in flag_rows:
        flag_map.setdefault(row.county, {})
        flag_map[row.county][row.flag_type] = row.count

    items = []
    for row in county_stats:
        county = row.county
        score = risk_score_map.get(county, 0)
        flags = flag_map.get(county, {})
        items.append(
            {
                "county": county,
                "riskScore": score,
                "riskLevel": _risk_level(score),
                "tenderCount": row.tender_count,
                "totalValue": row.total_value,
                "ghostSuppliers": flags.get("ghost_supplier", 0),
                "priceDeviations": flags.get("price_inflation", 0),
                "bidRigging": flags.get("collusion", 0),
            }
        )

    items.sort(key=lambda x: x["riskScore"], reverse=True)
    return items


async def get_risk_trend(db: AsyncSession, months: int = 6) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=30 * months)

    rows = (
        await db.execute(
            select(
                extract("year", Tender.created_at).label("year"),
                extract("month", Tender.created_at).label("month"),
                RiskScore.risk_level,
                func.count(Tender.id).label("count"),
            )
            .join(RiskScore, RiskScore.tender_id == Tender.id)
            .filter(Tender.created_at >= since)
            .group_by("year", "month", RiskScore.risk_level)
            .order_by("year", "month")
        )
    ).all()

    month_map: dict[str, dict[str, int]] = {}
    for row in rows:
        key = f"{int(row.year)}-{int(row.month):02d}"
        month_map.setdefault(key, {"critical": 0, "high": 0, "medium": 0, "low": 0})
        level = (
            row.risk_level.value
            if hasattr(row.risk_level, "value")
            else str(row.risk_level)
        )
        if level in month_map[key]:
            month_map[key][level] = row.count

    return [
        {
            "month": MONTH_ABBR[int(k.split("-")[1]) - 1],
            "year": k.split("-")[0],
            "criticalCount": v["critical"],
            "highCount": v["high"],
            "mediumCount": v["medium"],
            "lowCount": v["low"],
        }
        for k, v in sorted(month_map.items())
    ]


async def get_risk_type_distribution(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(
                RedFlag.flag_type,
                func.count(RedFlag.id).label("count"),
            )
            .group_by(RedFlag.flag_type)
            .order_by(func.count(RedFlag.id).desc())
        )
    ).all()

    return [
        {
            "name": LABEL_MAP.get(row.flag_type, row.flag_type),
            "value": row.count,
            "color": COLOR_MAP.get(row.flag_type, "#94a3b8"),
        }
        for row in rows
    ]
