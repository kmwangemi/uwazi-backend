from datetime import datetime, timedelta, timezone

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.red_flag_model import RedFlag
from app.models.risk_score_model import RiskScore
from app.models.tender_model import Tender

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


async def get_spending_trend(db: AsyncSession, months: int = 6) -> list[dict]:
    """
    Monthly budgeted vs actual spend vs flagged spend.
    budgeted  = sum of estimated_value on all tenders
    actual    = sum of contract values (awarded)
    flagged   = sum of estimated_value on tenders that have red flags
    All values in millions KES.
    """
    since = datetime.now(timezone.utc) - timedelta(days=30 * months)

    # Budgeted per month
    budgeted_rows = (
        await db.execute(
            select(
                extract("year", Tender.created_at).label("year"),
                extract("month", Tender.created_at).label("month"),
                func.coalesce(func.sum(Tender.estimated_value), 0).label("total"),
            )
            .filter(Tender.created_at >= since)
            .group_by("year", "month")
            .order_by("year", "month")
        )
    ).all()

    # Actual (awarded contract values) per month
    # Import Contract inside to avoid circular at module level
    from app.models.contract_model import Contract

    actual_rows = (
        await db.execute(
            select(
                extract("year", Contract.created_at).label("year"),
                extract("month", Contract.created_at).label("month"),
                func.coalesce(func.sum(Contract.contract_value), 0).label("total"),
            )
            .filter(Contract.created_at >= since)
            .group_by("year", "month")
            .order_by("year", "month")
        )
    ).all()

    # Flagged spend per month (tenders that have ≥1 red flag)
    flagged_rows = (
        await db.execute(
            select(
                extract("year", Tender.created_at).label("year"),
                extract("month", Tender.created_at).label("month"),
                func.coalesce(func.sum(Tender.estimated_value), 0).label("total"),
            )
            .join(RedFlag, RedFlag.tender_id == Tender.id)
            .filter(Tender.created_at >= since)
            .group_by("year", "month")
            .order_by("year", "month")
            .distinct()
        )
    ).all()

    # Build maps keyed by "YYYY-MM"
    def to_map(rows) -> dict[str, float]:
        return {
            f"{int(r.year)}-{int(r.month):02d}": round((r.total or 0) / 1_000_000, 1)
            for r in rows
        }

    budgeted_map = to_map(budgeted_rows)
    actual_map = to_map(actual_rows)
    flagged_map = to_map(flagged_rows)

    all_keys = sorted(set(budgeted_map) | set(actual_map) | set(flagged_map))
    return [
        {
            "month": MONTH_ABBR[int(k.split("-")[1]) - 1],
            "budgeted": budgeted_map.get(k, 0),
            "actual": actual_map.get(k, 0),
            "flagged": flagged_map.get(k, 0),
        }
        for k in all_keys
    ]


async def get_risk_distribution(db: AsyncSession) -> dict:
    """Counts of tenders per risk level."""
    rows = (
        await db.execute(
            select(
                RiskScore.risk_level,
                func.count(RiskScore.id).label("count"),
            ).group_by(RiskScore.risk_level)
        )
    ).all()

    dist = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for row in rows:
        level = (
            row.risk_level.value
            if hasattr(row.risk_level, "value")
            else str(row.risk_level)
        )
        if level in dist:
            dist[level] = row.count
    return dist


async def get_analytics_kpis(db: AsyncSession) -> dict:
    """
    Top-level KPI cards:
      total_value, flagged_count, avg_risk_score
    Deltas are vs the previous equivalent period (last 30 days vs prior 30 days).
    """
    now = datetime.now(timezone.utc)
    start_curr = now - timedelta(days=30)
    start_prev = now - timedelta(days=60)

    # Total procurement value (all time)
    total_value = (
        await db.scalar(select(func.coalesce(func.sum(Tender.estimated_value), 0)))
    ) or 0

    # Flagged tenders (have ≥1 red flag)
    flagged_curr = (
        await db.scalar(
            select(func.count(func.distinct(RedFlag.tender_id))).filter(
                RedFlag.created_at >= start_curr
            )
        )
    ) or 0
    flagged_prev = (
        await db.scalar(
            select(func.count(func.distinct(RedFlag.tender_id))).filter(
                RedFlag.created_at >= start_prev, RedFlag.created_at < start_curr
            )
        )
    ) or 0

    # Average risk score
    avg_curr = (
        await db.scalar(
            select(func.avg(RiskScore.total_score))
            .join(Tender, Tender.id == RiskScore.tender_id)
            .filter(Tender.created_at >= start_curr)
        )
    ) or 0
    avg_prev = (
        await db.scalar(
            select(func.avg(RiskScore.total_score))
            .join(Tender, Tender.id == RiskScore.tender_id)
            .filter(Tender.created_at >= start_prev, Tender.created_at < start_curr)
        )
    ) or 0

    def delta_pct(curr, prev) -> str:
        if not prev:
            return "+0.0%"
        pct = ((curr - prev) / prev) * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    def trend(curr, prev) -> str:
        return "up" if curr >= prev else "down"

    return {
        "total_value": round(total_value / 1_000_000_000, 2),  # in billions
        "flagged_count": flagged_curr,
        "flagged_delta": delta_pct(flagged_curr, flagged_prev),
        "flagged_trend": trend(flagged_curr, flagged_prev),
        "avg_risk_score": round(avg_curr, 1),
        "avg_risk_delta": delta_pct(avg_curr, avg_prev),
        "avg_risk_trend": trend(avg_curr, avg_prev),
    }


async def get_daily_trend(db: AsyncSession, days: int = 7) -> list[dict]:
    """
    Daily counts of tenders by risk level for TrendChart (area chart).
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        await db.execute(
            select(
                func.date(Tender.created_at).label("date"),
                RiskScore.risk_level,
                func.count(Tender.id).label("count"),
            )
            .join(RiskScore, RiskScore.tender_id == Tender.id)
            .filter(Tender.created_at >= since)
            .group_by(func.date(Tender.created_at), RiskScore.risk_level)
            .order_by(func.date(Tender.created_at))
        )
    ).all()

    day_map: dict[str, dict[str, int]] = {}
    for row in rows:
        key = str(row.date)  # "2026-03-19"
        day_map.setdefault(key, {"critical": 0, "high": 0, "medium": 0})
        level = (
            row.risk_level.value
            if hasattr(row.risk_level, "value")
            else str(row.risk_level)
        )
        if level in day_map[key]:
            day_map[key][level] = row.count

    return [
        {
            "date": f"{k[5:7]}/{k[8:10]}",  # "MM/DD" e.g. "03/19"
            "critical": v["critical"],
            "high": v["high"],
            "medium": v["medium"],
        }
        for k, v in sorted(day_map.items())
    ]
