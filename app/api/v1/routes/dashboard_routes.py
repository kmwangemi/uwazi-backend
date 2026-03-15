from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RiskLevel
from app.models.contract_model import Contract
from app.models.risk_score_model import RiskScore
from app.models.supplier_model import Supplier
from app.models.tender_model import Tender

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Main dashboard metrics.
    Public endpoint.
    """
    total_tenders = db.query(Tender).count()
    total_suppliers = db.query(Supplier).count()
    flagged_suppliers = db.query(Supplier).filter(Supplier.risk_score >= 60).count()

    # Risk level counts
    risk_counts = (
        db.query(RiskScore.risk_level, func.count(RiskScore.id))
        .group_by(RiskScore.risk_level)
        .all()
    )
    tenders_by_risk = {str(level.value): count for level, count in risk_counts}

    critical_tenders = tenders_by_risk.get("critical", 0)
    high_risk_tenders = tenders_by_risk.get("high", 0) + critical_tenders

    # Average price score as proxy for price inflation
    avg_price_score = db.query(func.avg(RiskScore.price_score)).scalar() or 0.0

    # Total contract value
    total_contract_value = db.query(func.sum(Contract.contract_value)).scalar() or 0.0

    # Tenders by county
    county_query = (
        db.query(Tender.county, func.count(Tender.id).label("count"))
        .filter(Tender.county.isnot(None))
        .group_by(Tender.county)
        .order_by(desc("count"))
        .limit(15)
        .all()
    )
    tenders_by_county = [{"county": c, "count": n} for c, n in county_query]

    # Recent critical tenders
    recent_critical = (
        db.query(Tender, RiskScore)
        .join(RiskScore)
        .filter(RiskScore.risk_level.in_([RiskLevel.CRITICAL, RiskLevel.HIGH]))
        .order_by(desc(RiskScore.updated_at))
        .limit(10)
        .all()
    )
    recent_critical_out = [
        {
            "id": str(t.id),
            "title": t.title,
            "county": t.county,
            "estimated_value": t.estimated_value,
            "risk_level": rs.risk_level.value,
            "total_score": rs.total_score,
            "flag_count": len(rs.flags),
        }
        for t, rs in recent_critical
    ]

    # Value at risk = sum of estimated values for critical+high risk tenders
    value_at_risk = (
        db.query(func.sum(Tender.estimated_value))
        .join(RiskScore)
        .filter(RiskScore.risk_level.in_([RiskLevel.CRITICAL, RiskLevel.HIGH]))
        .scalar()
        or 0.0
    )

    # Active investigations proxy = critical tenders analyzed in last 30 days
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    active_investigations = (
        db.query(RiskScore)
        .filter(
            RiskScore.risk_level == RiskLevel.CRITICAL, RiskScore.computed_at >= cutoff
        )
        .count()
    )

    return {
        "total_tenders": total_tenders,
        "high_risk_tenders": high_risk_tenders,
        "critical_tenders": critical_tenders,
        "active_investigations": active_investigations,
        "avg_price_deviation_score": round(avg_price_score, 2),
        "total_contract_value": total_contract_value,
        "value_at_risk": value_at_risk,
        "total_suppliers": total_suppliers,
        "flagged_suppliers": flagged_suppliers,
        "tenders_by_risk": tenders_by_risk,
        "tenders_by_county": tenders_by_county,
        "recent_critical_tenders": recent_critical_out,
    }


@router.get("/heatmap")
def get_county_heatmap(db: Session = Depends(get_db)):
    """
    Average risk scores grouped by county for the corruption heatmap.
    """
    rows = (
        db.query(
            Tender.county,
            func.avg(RiskScore.total_score).label("avg_risk"),
            func.count(Tender.id).label("total"),
            func.sum(
                func.cast(
                    RiskScore.risk_level.in_(["high", "critical"]),
                    db.bind.dialect.name == "postgresql" and "int" or "integer",
                )
            ).label("high_risk_count"),
        )
        .join(RiskScore)
        .filter(Tender.county.isnot(None))
        .group_by(Tender.county)
        .all()
    )

    # Simpler version if the above cast doesn't work across DBs:
    all_with_risk = (
        db.query(Tender.county, RiskScore.total_score, RiskScore.risk_level)
        .join(RiskScore)
        .filter(Tender.county.isnot(None))
        .all()
    )

    # Aggregate in Python
    county_data: dict = {}
    for county, score, level in all_with_risk:
        if county not in county_data:
            county_data[county] = {"scores": [], "high_risk": 0, "total": 0}
        county_data[county]["scores"].append(score)
        county_data[county]["total"] += 1
        if level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            county_data[county]["high_risk"] += 1

    heatmap = [
        {
            "county": county,
            "avg_risk_score": round(sum(d["scores"]) / len(d["scores"]), 2),
            "tender_count": d["total"],
            "high_risk_count": d["high_risk"],
        }
        for county, d in sorted(
            county_data.items(),
            key=lambda x: -sum(x[1]["scores"]) / max(len(x[1]["scores"]), 1),
        )
    ]

    return heatmap


@router.get("/top-risk-suppliers")
def get_top_risk_suppliers(limit: int = 10, db: Session = Depends(get_db)):
    """Top suppliers by risk score."""
    suppliers = (
        db.query(Supplier)
        .filter(Supplier.risk_score > 0)
        .order_by(desc(Supplier.risk_score))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "risk_score": s.risk_score,
            "past_contracts_count": s.past_contracts_count,
            "past_contracts_value": s.past_contracts_value,
            "county": s.county,
        }
        for s in suppliers
    ]


@router.post("/ai-query")
def ai_natural_language_query(
    question: str = Body(
        ...,
        embed=True,
        description="Ask anything about procurement data in plain English",
    ),
    db: Session = Depends(get_db),
):
    """
    Natural language query interface.
    Fetches relevant stats and lets Claude answer questions in plain English.
    Example: 'Which county has the most high-risk tenders?'
    """
    # Gather context data from DB
    stats = get_stats(db)
    heatmap = get_county_heatmap(db)
    top_risky = get_top_risk_suppliers(5, db)

    context = {
        "dashboard_summary": stats,
        "county_risk_heatmap": heatmap[:10],
        "top_risky_suppliers": top_risky,
    }

    from app.services.ai_service import natural_language_query

    try:
        answer = natural_language_query(question, context)
        return {"question": question, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")


@router.get("/risk-trend")
def get_risk_trend(
    days: int = 30,
    db: Session = Depends(get_db),
):
    """
    Daily risk level counts for the last N days.
    Used by the dashboard AreaChart (critical/high/medium stacked areas).

    Returns:
    [{
        date: "2026-03-01",
        critical: int,
        high: int,
        medium: int,
        low: int,
        total: int
    }]
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import Date, cast

    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(
            cast(Tender.created_at, Date).label("day"),
            RiskScore.risk_level,
            func.count(RiskScore.id).label("cnt"),
        )
        .join(RiskScore, RiskScore.tender_id == Tender.id)
        .filter(Tender.created_at >= since)
        .group_by("day", RiskScore.risk_level)
        .order_by("day")
        .all()
    )

    # Build a dict keyed by date
    daily: dict = {}
    for day, level, cnt in rows:
        key = str(day)
        if key not in daily:
            daily[key] = {
                "date": key,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "total": 0,
            }
        daily[key][level.value] = cnt
        daily[key]["total"] += cnt

    # Fill gaps with zeros so the chart has a continuous series
    result = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime(
            "%Y-%m-%d"
        )
        if d in daily:
            result.append(daily[d])
        else:
            result.append(
                {"date": d, "critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
            )

    return result
