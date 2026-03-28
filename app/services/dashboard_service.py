from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.red_flag_model import RedFlag
from app.models.risk_score_model import RiskScore
from app.models.supplier_model import Supplier
from app.models.tender_model import Tender
from app.models.investigation_model import Investigation


async def get_dashboard_stats(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    start_curr = now - timedelta(days=30)
    start_prev = now - timedelta(days=60)

    # ── Total tenders ──────────────────────────────────────────────────────────
    total_tenders = (await db.scalar(select(func.count(Tender.id)))) or 0
    total_tenders_prev = (
        await db.scalar(
            select(func.count(Tender.id)).filter(Tender.created_at < start_curr)
        )
    ) or 0

    # ── Critical risk tenders ──────────────────────────────────────────────────
    critical_curr = (
        await db.scalar(
            select(func.count(RiskScore.id))
            .join(Tender, Tender.id == RiskScore.tender_id)
            .filter(RiskScore.risk_level == "critical", Tender.created_at >= start_curr)
        )
    ) or 0
    critical_prev = (
        await db.scalar(
            select(func.count(RiskScore.id))
            .join(Tender, Tender.id == RiskScore.tender_id)
            .filter(
                RiskScore.risk_level == "critical",
                Tender.created_at >= start_prev,
                Tender.created_at < start_curr,
            )
        )
    ) or 0

    # ── Value at risk (estimated value of high/critical tenders) ───────────────
    value_curr = (
        await db.scalar(
            select(func.coalesce(func.sum(Tender.estimated_value), 0))
            .join(RiskScore, RiskScore.tender_id == Tender.id)
            .filter(
                RiskScore.risk_level.in_(["critical", "high"]),
                Tender.created_at >= start_curr,
            )
        )
    ) or 0
    value_prev = (
        await db.scalar(
            select(func.coalesce(func.sum(Tender.estimated_value), 0))
            .join(RiskScore, RiskScore.tender_id == Tender.id)
            .filter(
                RiskScore.risk_level.in_(["critical", "high"]),
                Tender.created_at >= start_prev,
                Tender.created_at < start_curr,
            )
        )
    ) or 0

    # ── Active investigations (tenders with red flags, still open) ─────────────
    investigations = (
        await db.scalar(
            select(func.count(Investigation.id))
            .filter(Investigation.status == "open")
        )
    ) or 0
    investigations_prev = (
        await db.scalar(
            select(func.count(Investigation.id))
            .filter(Investigation.status == "open", Investigation.opened_at < start_curr)
        )
    ) or 0

    def delta(curr, prev) -> float:
        if not prev:
            return 0.0
        return round(((curr - prev) / prev) * 100, 1)

    return {
        "total_tenders": total_tenders,
        "total_tenders_delta": delta(total_tenders, total_tenders_prev),
        "critical_risk_tenders": critical_curr,
        "critical_risk_delta": delta(critical_curr, critical_prev),
        "total_value_at_risk": value_curr,
        "value_at_risk_delta": delta(value_curr, value_prev),
        "active_investigations": investigations,
        "investigations_delta": delta(investigations, investigations_prev),
    }


async def get_dashboard_heatmap(db: AsyncSession) -> list[dict]:
    """County-level risk summary for heatmap."""
    rows = (
        await db.execute(
            select(
                Tender.county,
                func.count(Tender.id).label("tender_count"),
                func.avg(RiskScore.total_score).label("avg_score"),
            )
            .join(RiskScore, RiskScore.tender_id == Tender.id)
            .filter(Tender.county.isnot(None))
            .group_by(Tender.county)
            .order_by(desc(func.avg(RiskScore.total_score)))
        )
    ).all()

    def risk_level(score: float) -> str:
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    return [
        {
            "county": row.county,
            "tender_count": row.tender_count,
            "avg_score": round(row.avg_score or 0, 1),
            "risk_level": risk_level(row.avg_score or 0),
        }
        for row in rows
    ]


async def get_top_risk_suppliers(db: AsyncSession, limit: int = 5) -> list[dict]:
    """Top suppliers ranked by risk score."""
    rows = (
        (
            await db.execute(
                select(Supplier).order_by(desc(Supplier.risk_score)).limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return [
        {
            "supplier_id": str(s.id),
            "name": s.name,
            "risk_score": s.risk_score,
            "ghost_probability": round(min((s.risk_score or 0) / 100, 1.0), 4),
            "rank": idx + 1,
            "county": s.county,
            "is_verified": s.is_verified,
        }
        for idx, s in enumerate(rows)
    ]


async def get_high_risk_tenders(db: AsyncSession, limit: int = 10) -> list[dict]:
    """Most recent high/critical risk tenders for the dashboard table."""
    rows = (
        await db.execute(
            select(Tender, RiskScore)
            .join(RiskScore, RiskScore.tender_id == Tender.id)
            .filter(RiskScore.risk_level.in_(["critical", "high"]))
            .order_by(desc(RiskScore.total_score))
            .limit(limit)
        )
    ).all()

    from app.models.procuring_entity_model import ProcuringEntity

    results = []
    for tender, rs in rows:
        # Load entity name if available
        entity_name = None
        if tender.entity_id:
            entity = (
                (
                    await db.execute(
                        select(ProcuringEntity).filter(
                            ProcuringEntity.id == tender.entity_id
                        )
                    )
                )
                .scalars()
                .first()
            )
            entity_name = entity.name if entity else None

        results.append(
            {
                "id": str(tender.id),
                "title": tender.title,
                "entity": entity_name,
                "county": tender.county,
                "estimated_value": tender.estimated_value,
                "risk_score": rs.total_score,
                "risk_level": (
                    rs.risk_level.value
                    if hasattr(rs.risk_level, "value")
                    else rs.risk_level
                ),
                "created_at": tender.created_at.isoformat(),
            }
        )
    return results


async def ask_ai_query(question: str) -> dict:
    """
    Send a natural language question to Claude and return the answer.
    """
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=(
            "You are a procurement fraud analyst for the Kenyan government. "
            "Answer questions about procurement risks, corruption patterns, "
            "and tender irregularities concisely and factually. "
            "If you cannot answer from available context, say so clearly."
        ),
        messages=[{"role": "user", "content": question}],
    )
    answer = message.content[0].text if message.content else "No response generated."
    return {"answer": answer}
