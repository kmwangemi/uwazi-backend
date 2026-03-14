"""
Risk Analysis Routes
  POST /api/analyze/price-check        → price vs benchmark
  POST /api/analyze/specifications     → spec restrictiveness analysis
  GET  /api/analyze/county-risk        → county-level risk overview table
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.enums import RiskLevel
from app.models.risk_score_model import RiskScore
from app.models.tender_model import Tender

router = APIRouter(prefix="/api/analyze", tags=["Risk Analysis"])


# ── POST /api/analyze/price-check ────────────────────────────────────────────


@router.post("/price-check")
def check_price(
    item_name: str = Body(..., embed=True, description="Item/tender description"),
    tender_price: float = Body(..., embed=True, description="Estimated price in KES"),
    category: Optional[str] = Body(None, embed=True),
    county: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
):
    """
    Compare a price against market benchmarks.

    Returns:
    {
        score: float,              risk score 0-100
        risk_level: str,           low/medium/high/critical
        deviation_pct: float,      % above/below market
        benchmark: {               null if no match found
            item_name, category, unit,
            avg_price, min_price, max_price, source
        },
        flags: [str],              human-readable issues
        verdict: str               plain English summary
    }
    """
    from app.services.price_analyzer_service import compute_price_score

    result = compute_price_score(db, tender_price, category or "", item_name)

    # Shape response to match frontend type PriceCheckResult
    benchmark = result.get("benchmark_comparison")
    score = result.get("score", 0)

    if score >= 80:
        risk_level = "critical"
    elif score >= 60:
        risk_level = "high"
    elif score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    deviation_pct = benchmark["deviation_pct"] if benchmark else 0.0

    # Plain English verdict
    if not benchmark:
        verdict = f"No benchmark data available for '{item_name}'. Cannot assess price."
    elif deviation_pct > 100:
        verdict = f"Price is {deviation_pct:.0f}% above market average — extremely suspicious."
    elif deviation_pct > 50:
        verdict = (
            f"Price is {deviation_pct:.0f}% above market average — high inflation risk."
        )
    elif deviation_pct > 20:
        verdict = (
            f"Price is {deviation_pct:.0f}% above market average — warrants scrutiny."
        )
    elif deviation_pct < -20:
        verdict = f"Price is {abs(deviation_pct):.0f}% below market — possible low-quality goods."
    else:
        verdict = (
            f"Price is within normal market range ({deviation_pct:+.1f}% vs benchmark)."
        )

    return {
        "score": score,
        "risk_level": risk_level,
        "deviation_pct": round(deviation_pct, 2),
        "benchmark": (
            {
                "item_name": benchmark["item_name"],
                "category": benchmark["category"],
                "unit": benchmark.get("unit", ""),
                "avg_price": benchmark["market_avg"],
                "min_price": benchmark["market_min"],
                "max_price": benchmark["market_max"],
                "source": benchmark.get("source", "PPIP / Kenya Treasury"),
            }
            if benchmark
            else None
        ),
        "flags": result.get("flags", []),
        "verdict": verdict,
        "item_name": item_name,
        "tender_price": tender_price,
    }


# ── POST /api/analyze/specifications ─────────────────────────────────────────


@router.post("/specifications")
def analyze_specifications(
    spec_text: str = Body(
        ..., embed=True, description="Full specification text to analyse"
    ),
    tender_value: Optional[float] = Body(None, embed=True),
    use_ai: bool = Body(False, embed=True, description="Use Claude for deep analysis"),
):
    """
    Analyse tender specification text for restrictive or anti-competitive patterns.

    Returns:
    {
        restrictiveness_score: float  0-100
        risk_level: str
        issues: [{type, description, severity, excerpt}]
        brand_names_found: [str]
        single_source_detected: bool
        verdict: str
        ai_analysis: str | null      (only if use_ai=true)
    }
    """
    from app.services.spec_analyzer_service import compute_spec_score

    # Rule-based analysis
    rule_result = compute_spec_score(spec_text, use_ai=False, tender_value=tender_value)
    score = rule_result.get("score", 0)

    # spaCy NER enhancement
    spacy_result = {
        "restrictiveness_score": 0,
        "issues": [],
        "brand_names_found": [],
        "single_source_detected": False,
    }
    try:
        from app.ml.spec_nlp import analyse as spacy_analyse

        spacy_result = spacy_analyse(spec_text, tender_value)
        score = max(score, spacy_result["restrictiveness_score"])
    except Exception:
        pass

    # Merge issues
    all_issues = []
    for flag in rule_result.get("flags", []):
        # Parse "SEVERITY: description" format
        parts = flag.split(":", 1)
        severity = parts[0].strip().lower() if len(parts) == 2 else "medium"
        description = parts[1].strip() if len(parts) == 2 else flag
        all_issues.append(
            {
                "type": "keyword_match",
                "severity": severity,
                "description": description,
                "excerpt": "",
            }
        )
    for issue in spacy_result.get("issues", []):
        parts = issue.split(":", 1)
        severity = parts[0].strip().lower() if len(parts) == 2 else "medium"
        description = parts[1].strip() if len(parts) == 2 else issue
        all_issues.append(
            {
                "type": "nlp_detection",
                "severity": severity,
                "description": description,
                "excerpt": "",
            }
        )

    if score >= 80:
        risk_level = "critical"
    elif score >= 60:
        risk_level = "high"
    elif score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    # AI deep analysis
    ai_analysis = None
    if use_ai:
        try:
            from app.services.ai_service import analyze_tender_specifications

            ai_r = analyze_tender_specifications(spec_text, tender_value)
            ai_analysis = ai_r.get("analysis") or str(ai_r)
            ai_score = ai_r.get("restrictiveness_score", score)
            score = max(score, ai_score)
        except Exception as e:
            ai_analysis = f"AI analysis unavailable: {e}"

    brand_names = list(
        set(
            rule_result.get("brand_names", [])
            + spacy_result.get("brand_names_found", [])
        )
    )
    single_source = rule_result.get(
        "single_source_detected", False
    ) or spacy_result.get("single_source_detected", False)

    if not all_issues:
        verdict = "No significant restrictive patterns detected."
    elif single_source:
        verdict = "CRITICAL: Sole-source indicators detected — specification may be written for a specific vendor."
    elif brand_names:
        verdict = f"Specification names specific brands ({', '.join(brand_names[:3])}) which restricts competition."
    else:
        verdict = f"{len(all_issues)} restrictive pattern(s) detected. Review required."

    return {
        "restrictiveness_score": round(score, 2),
        "risk_level": risk_level,
        "issues": all_issues,
        "brand_names_found": brand_names,
        "single_source_detected": single_source,
        "verdict": verdict,
        "ai_analysis": ai_analysis,
        "spec_length": len(spec_text),
    }


# ── GET /api/analyze/county-risk ─────────────────────────────────────────────


@router.get("/county-risk")
def get_county_risk_overview(
    limit: int = Query(47, ge=1, le=47, description="Number of counties to return"),
    db: Session = Depends(get_db),
):
    """
    County-level risk overview table.
    Used on the /risk page county risk section.

    Returns list of counties sorted by avg_risk_score desc:
    [{
        county: str,
        tender_count: int,
        avg_risk_score: float,
        total_value_kes: float,
        critical_count: int,
        high_count: int,
        highest_risk_tender: { id, title, total_score } | null
    }]
    """
    # Aggregate risk data by county
    rows = (
        db.query(
            Tender.county,
            func.count(Tender.id).label("tender_count"),
            func.avg(RiskScore.total_score).label("avg_risk"),
            func.sum(Tender.estimated_value).label("total_value"),
        )
        .join(RiskScore, RiskScore.tender_id == Tender.id)
        .filter(Tender.county.isnot(None))
        .group_by(Tender.county)
        .order_by(desc("avg_risk"))
        .limit(limit)
        .all()
    )

    if not rows:
        return []

    # Get critical/high counts per county
    level_counts = (
        db.query(
            Tender.county,
            RiskScore.risk_level,
            func.count(RiskScore.id).label("cnt"),
        )
        .join(RiskScore, RiskScore.tender_id == Tender.id)
        .filter(
            Tender.county.isnot(None),
            RiskScore.risk_level.in_([RiskLevel.CRITICAL, RiskLevel.HIGH]),
        )
        .group_by(Tender.county, RiskScore.risk_level)
        .all()
    )

    level_map: dict = {}
    for county, level, cnt in level_counts:
        if county not in level_map:
            level_map[county] = {"critical": 0, "high": 0}
        level_map[county][level.value] = cnt

    # Highest risk tender per county
    highest: dict = {}
    for county, _, _, _ in rows:
        top = (
            db.query(Tender, RiskScore)
            .join(RiskScore, RiskScore.tender_id == Tender.id)
            .filter(Tender.county == county)
            .order_by(desc(RiskScore.total_score))
            .first()
        )
        if top:
            t, rs = top
            highest[county] = {
                "id": str(t.id),
                "title": t.title[:60] + ("..." if len(t.title) > 60 else ""),
                "total_score": rs.total_score,
                "risk_level": rs.risk_level.value,
            }

    return [
        {
            "county": county,
            "tender_count": tender_count,
            "avg_risk_score": round(float(avg_risk or 0), 2),
            "total_value_kes": float(total_value or 0),
            "critical_count": level_map.get(county, {}).get("critical", 0),
            "high_count": level_map.get(county, {}).get("high", 0),
            "highest_risk_tender": highest.get(county),
        }
        for county, tender_count, avg_risk, total_value in rows
    ]
