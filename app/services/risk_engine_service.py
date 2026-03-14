"""
Corruption Risk Engine — wires all ML models into a single scoring pipeline.

PIPELINE (per tender)
─────────────────────
  Step 1  price_anomaly.py       IsolationForest   → price outlier score
  Step 2  supplier_risk.py       RF + IF           → ghost supplier score
  Step 3  spec_nlp.py            spaCy NER         → spec restrictiveness score
  Step 4  collusion.py           TF-IDF cosine     → bid collusion score
  Step 5  xgb_risk_model.py      XGBoost           → composite corruption probability
  Step 6  ai_service.py          Claude            → narrative + recommended action
  Step 7  DB save                                  → RiskScore + RedFlag rows
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import RiskLevel
from app.models.red_flag_model import RedFlag
from app.models.risk_score_model import RiskScore
from app.models.supplier_model import Supplier
from app.models.tender_model import Tender
from app.services.price_analyzer_service import compute_price_score


def _risk_level_from_score(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    elif score >= 60:
        return RiskLevel.HIGH
    elif score >= 40:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _method_str(tender: Tender) -> Optional[str]:
    return tender.procurement_method.value if tender.procurement_method else None


def _days_to_deadline(tender: Tender) -> Optional[int]:
    if tender.submission_deadline and tender.created_at:
        return max((tender.submission_deadline - tender.created_at).days, 0)
    return None


def compute_and_save_risk(
    db: Session,
    tender: Tender,
    supplier: Optional[Supplier] = None,
    bids: Optional[list] = None,
    use_ai: bool = True,
) -> RiskScore:
    """Full ML + AI risk pipeline. Saves and returns RiskScore."""
    all_flags = []

    # ── Step 1: Price — rule-based + IsolationForest ─────────────────────────
    price_result = compute_price_score(
        db, tender.estimated_value, tender.category, tender.title
    )
    price_score = price_result["score"]
    all_flags.extend(price_result["flags"])
    benchmark = price_result.get("benchmark_comparison")

    ghost_prob = 0.20  # default for XGBoost input

    if benchmark and tender.estimated_value:
        try:
            from app.ml.price_anomaly import predict as if_price

            if_r = if_price(
                price=tender.estimated_value,
                benchmark_avg=benchmark["market_avg"],
                estimated_value=tender.estimated_value,
                category=tender.category,
                county=tender.county,
            )
            if if_r["is_anomaly"]:
                price_score = max(price_score, if_r["confidence"] * 100)
                if if_r["model_used"] != "fallback_deviation":
                    all_flags.append(
                        f"ML: IsolationForest price anomaly "
                        f"(confidence {if_r['confidence']:.0%})"
                    )
        except Exception:
            pass  # model not trained yet — rule-based score stands

    # ── Step 2: Supplier — rules + RandomForest + IsolationForest ─────────────
    supplier_score = 20.0
    if supplier:
        from app.services.supplier_checker_service import compute_supplier_score

        rule_r = compute_supplier_score(supplier)
        all_flags.extend(rule_r["flags"])
        supplier_score = rule_r["score"]

        try:
            from app.ml.supplier_risk import predict as ml_supplier

            ml_r = ml_supplier(
                company_age_days=supplier.company_age_days,
                tax_filings_count=supplier.tax_filings_count,
                directors=supplier.directors or [],
                has_physical_address=supplier.has_physical_address,
                has_online_presence=supplier.has_online_presence,
                past_contracts_count=supplier.past_contracts_count,
                past_contracts_value=supplier.past_contracts_value,
                employee_count=supplier.employee_count,
            )
            ghost_prob = ml_r.get("ghost_probability") or ml_r["combined_score"] / 100
            supplier_score = max(supplier_score, ml_r["combined_score"])
            if (
                ml_r["model_used"] not in ("rule_based_fallback", "none")
                and ml_r["combined_score"] > rule_r["score"]
            ):
                all_flags.append(
                    f"ML: {ml_r['model_used']} elevated supplier risk score to {ml_r['combined_score']:.0f}/100"
                )
        except Exception:
            pass
    else:
        all_flags.append("MEDIUM: No supplier data available for ML analysis")

    # ── Step 3: Spec — rules + spaCy NER ─────────────────────────────────────
    from app.services.spec_analyzer_service import compute_spec_score

    rule_spec = compute_spec_score(tender.description)
    all_flags.extend(rule_spec["flags"])
    spec_score = rule_spec["score"]

    try:
        from app.ml.spec_nlp import analyse as spacy_analyse

        spacy_r = spacy_analyse(tender.description or "", tender.estimated_value)
        all_flags.extend(spacy_r.get("issues", []))
        spec_score = max(spec_score, spacy_r["restrictiveness_score"])
    except Exception:
        pass

    # ── Step 4: Collusion — TF-IDF cosine similarity ──────────────────────────
    collusion_score = 0.0
    if bids and len(bids) >= 2:
        try:
            from app.ml.collusion import detect_bid_collusion

            bids_data = [
                {
                    "supplier_id": str(b.supplier_id),
                    "bid_amount": b.bid_amount,
                    "proposal_text": b.proposal_text or "",
                }
                for b in bids
            ]
            col_r = detect_bid_collusion(bids_data, tender.description)
            collusion_score = col_r["collusion_risk_score"]
            for pair in col_r.get("collusion_pairs", []):
                all_flags.append(
                    f"HIGH: Bid collusion detected — suppliers "
                    f"{pair['supplier_a'][:8]}... / {pair['supplier_b'][:8]}... "
                    f"similarity {pair['similarity']:.0%} ({pair['collusion_type']})"
                )
        except Exception:
            pass

    # ── Step 5: XGBoost composite ─────────────────────────────────────────────
    contract_score = 0.0
    method_str = _method_str(tender)
    if method_str == "direct_procurement" and tender.estimated_value:
        if tender.estimated_value > 50_000_000:
            contract_score = 80.0
            all_flags.append(
                "CRITICAL: Direct procurement >KES 50M likely violates PPADA Section 103"
            )
        elif tender.estimated_value > 10_000_000:
            contract_score = 50.0
            all_flags.append(
                "HIGH: Direct procurement value may exceed legal threshold"
            )

    try:
        from app.ml.xgb_risk_model import predict as xgb_predict

        xgb_r = xgb_predict(
            price_deviation_pct=benchmark["deviation_pct"] if benchmark else 0.0,
            supplier_ghost_prob=ghost_prob,
            spec_restrictiveness=spec_score,
            estimated_value=tender.estimated_value or 0,
            procurement_method=method_str,
            entity_history_score=(
                tender.entity.corruption_history_score if tender.entity else 0.0
            ),
            deadline_days=_days_to_deadline(tender),
            bid_count=len(bids) if bids else 1,
            single_bidder=(len(bids) == 1) if bids else False,
        )
        if xgb_r["model_used"] == "xgboost":
            total_score = xgb_r["risk_score"]
            total_score = min(max(total_score, contract_score * 0.5), 100.0)
        else:
            raise ValueError("fallback")
    except Exception:
        # Weighted composite fallback
        total_score = (
            price_score * 0.40
            + supplier_score * 0.30
            + spec_score * 0.20
            + contract_score * 0.10
        )
        if collusion_score > 40:
            total_score = min(total_score * 0.8 + collusion_score * 0.2, 100.0)

    total_score = min(round(total_score, 2), 100.0)
    risk_level = _risk_level_from_score(total_score)

    # ── Step 6: Claude AI narrative ───────────────────────────────────────────
    ai_analysis = None
    recommended_action = None
    if use_ai and total_score >= 30:
        try:
            from app.services.ai_service import analyze_tender_risk

            ai_r = analyze_tender_risk(
                tender_title=tender.title,
                tender_description=tender.description,
                estimated_value=tender.estimated_value,
                county=tender.county,
                procurement_method=method_str,
                price_score=price_score,
                supplier_score=supplier_score,
                spec_score=spec_score,
                total_score=total_score,
                risk_flags=all_flags,
                price_benchmark_comparison=benchmark,
            )
            ai_analysis = ai_r["ai_analysis"]
            recommended_action = ai_r["recommended_action"]
        except Exception as e:
            ai_analysis = f"AI narrative unavailable: {e}"

    # ── Step 7: Deduplicate flags & save ──────────────────────────────────────
    seen = set()
    unique_flags = [f for f in all_flags if not (f in seen or seen.add(f))]

    entity_score = tender.entity.corruption_history_score if tender.entity else 0.0

    existing = db.query(RiskScore).filter(RiskScore.tender_id == tender.id).first()
    if existing:
        existing.price_score = price_score
        existing.supplier_score = supplier_score
        existing.spec_score = spec_score
        existing.contract_value_score = contract_score
        existing.entity_history_score = entity_score
        existing.total_score = total_score
        existing.risk_level = risk_level
        existing.flags = unique_flags
        existing.ai_analysis = ai_analysis
        existing.recommended_action = recommended_action
        existing.updated_at = datetime.utcnow()
        rso = existing
    else:
        rso = RiskScore(
            tender_id=tender.id,
            price_score=price_score,
            supplier_score=supplier_score,
            spec_score=spec_score,
            contract_value_score=contract_score,
            entity_history_score=entity_score,
            total_score=total_score,
            risk_level=risk_level,
            flags=unique_flags,
            ai_analysis=ai_analysis,
            recommended_action=recommended_action,
        )
        db.add(rso)

    # Save red flags
    db.query(RedFlag).filter(RedFlag.tender_id == tender.id).delete()
    sev = {
        "CRITICAL": "critical",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
        "ML": "high",
    }
    for flag in unique_flags:
        fl = flag.lower()
        if any(w in fl for w in ["price", "market", "inflation", "benchmark"]):
            ft = "price_inflation"
        elif any(w in fl for w in ["supplier", "ghost", "director", "tax"]):
            ft = "ghost_supplier"
        elif any(w in fl for w in ["brand", "spec", "experience", "deadline", "sole"]):
            ft = "spec_restriction"
        elif any(w in fl for w in ["collusion", "similarity"]):
            ft = "collusion"
        elif any(w in fl for w in ["direct procurement", "ppada"]):
            ft = "procurement_method"
        else:
            ft = "other"
        severity = "medium"
        for pfx, sv in sev.items():
            if flag.startswith(pfx + ":"):
                severity = sv
                break
        db.add(
            RedFlag(
                tender_id=tender.id,
                flag_type=ft,
                severity=severity,
                description=flag,
                evidence={"benchmark": benchmark} if benchmark else {},
            )
        )

    db.commit()
    db.refresh(rso)
    return rso
