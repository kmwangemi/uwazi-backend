"""
ML Management routes:
  POST /api/ml/train/xgboost-synthetic   Bootstrap XGBoost with synthetic data
  POST /api/ml/train/price-anomaly       Train IF on current DB price records
  GET  /api/ml/status                    Which models are trained

Spending forecast route:
  GET  /api/ml/spending-forecast/{entity_id}  Prophet time-series for entity
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contract_model import Contract
from app.models.procuring_entity_model import ProcuringEntity
from app.core.dependencies import require_role

router = APIRouter(prefix="/ml", tags=["ML Models"])


@router.get("/status")
def model_status():
    """Which ML models are trained and available."""
    import os

    weights_dir = os.path.join(os.path.dirname(__file__), "..", "ml", "weights")

    def exists(name):
        return os.path.exists(os.path.join(weights_dir, name))

    return {
        "models": {
            "price_anomaly_isolation_forest": {
                "trained": exists("price_anomaly_if.pkl"),
                "layer": "Layer 2 — Price Inflation",
                "library": "sklearn.IsolationForest",
            },
            "supplier_random_forest": {
                "trained": exists("supplier_rf.pkl"),
                "layer": "Layer 3 — Ghost Supplier",
                "library": "sklearn.RandomForestClassifier",
            },
            "supplier_isolation_forest": {
                "trained": exists("supplier_if.pkl"),
                "layer": "Layer 3 — Ghost Supplier",
                "library": "sklearn.IsolationForest",
            },
            "collusion_tfidf_vectorizer": {
                "trained": exists("collusion_tfidf.pkl"),
                "layer": "Layer 4 — Collusion",
                "library": "sklearn.TfidfVectorizer",
            },
            "spec_spacy_nlp": {
                "trained": _spacy_available(),
                "layer": "Layer 4 — Spec Analysis",
                "library": "spacy.en_core_web_sm",
            },
            "xgboost_risk_model": {
                "trained": exists("xgb_risk_model.pkl"),
                "layer": "Layer 5 — Corruption Risk Score",
                "library": "xgboost.XGBClassifier",
            },
            "prophet_spending": {
                "trained": _prophet_available(),
                "layer": "Layer 6 — Temporal Patterns",
                "library": "prophet",
            },
            "claude_llm": {
                "trained": _claude_available(),
                "layer": "Cross-cutting — Narratives & Triage",
                "library": "anthropic.claude-opus-4-6",
            },
        }
    }


@router.post("/train/xgboost-synthetic")
def train_xgboost_synthetic(user=Depends(require_role("admin"))):
    """
    Bootstrap XGBoost with synthetic data based on known Kenya corruption patterns.
    Use until real EACC-labeled data is available.
    """
    try:
        from app.ml.xgb_risk_model import train_with_synthetic_data

        train_with_synthetic_data()
        return {
            "status": "success",
            "message": "XGBoost trained on 500 synthetic records",
        }
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"xgboost not installed: {e}")


@router.post("/train/price-anomaly")
def train_price_anomaly(
    user=Depends(require_role("admin")), db: Session = Depends(get_db)
):
    """
    Train IsolationForest on current DB tender+benchmark records.
    Requires at least 100 tenders with benchmark matches.
    """
    from app.models.price_benchmark_model import PriceBenchmark
    from app.models.tender_model import Tender

    tenders = (
        db.query(Tender)
        .filter(
            Tender.estimated_value.isnot(None),
            Tender.category.isnot(None),
        )
        .all()
    )

    if len(tenders) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 50 tenders to train. Currently have {len(tenders)}.",
        )

    records = []
    for t in tenders:
        # Find benchmark
        bench = (
            db.query(PriceBenchmark)
            .filter(PriceBenchmark.category.ilike(f"%{t.category}%"))
            .first()
        )
        if bench:
            records.append(
                {
                    "price": t.estimated_value,
                    "benchmark_avg": bench.avg_price,
                    "estimated_value": t.estimated_value,
                    "category": t.category,
                    "county": t.county,
                }
            )

    if len(records) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"Only {len(records)} tenders matched benchmarks. Need 30+.",
        )

    try:
        from app.ml.price_anomaly import train

        train(records)
        return {"status": "success", "records_used": len(records)}
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"sklearn not installed: {e}")


@router.post("/train/collusion-vectorizer")
def train_collusion_vectorizer(
    user=Depends(require_role("admin")), db: Session = Depends(get_db)
):
    """Fit TF-IDF vectorizer on all bid proposal texts in DB."""
    from app.models.bid_model import Bid

    bids = db.query(Bid).filter(Bid.proposal_text.isnot(None)).all()
    texts = [
        b.proposal_text for b in bids if b.proposal_text and len(b.proposal_text) > 50
    ]

    if len(texts) < 20:
        raise HTTPException(
            status_code=400, detail=f"Need 20+ bid texts. Have {len(texts)}."
        )

    try:
        from app.ml.collusion import fit_vectorizer

        fit_vectorizer(texts)
        return {"status": "success", "texts_used": len(texts)}
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/spending-forecast/{entity_id}")
def get_spending_forecast(
    entity_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """
    Prophet time-series spending forecast + anomaly detection for a procuring entity.
    Detects year-end budget rushes and pre-election spending spikes.
    """
    entity = db.query(ProcuringEntity).filter(ProcuringEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Aggregate contract awards by date
    from app.models.tender_model import Tender

    contracts = (
        db.query(Contract)
        .join(Tender)
        .filter(Tender.entity_id == entity_id, Contract.awarded_at.isnot(None))
        .all()
    )

    if len(contracts) < 10:
        return {
            "entity": entity.name,
            "message": f"Insufficient data: {len(contracts)} contracts. Need 30+ for forecast.",
            "anomalies": [],
        }

    spend_records = [
        {"date": c.awarded_at.strftime("%Y-%m-%d"), "amount": c.contract_value}
        for c in contracts
    ]

    from app.ml.spending_forecast import detect_spending_anomalies

    result = detect_spending_anomalies(spend_records, entity_name=entity.name)
    result["entity_id"] = str(entity_id)
    result["entity_name"] = entity.name
    return result


# ── Collusion analysis for a specific tender ──────────────────────────────────

collusion_router = APIRouter(prefix="/tenders", tags=["Collusion Detection"])


@collusion_router.get("/{tender_id}/collusion-analysis")
def analyse_tender_collusion(
    tender_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    """Run TF-IDF collusion analysis on all bids for a tender."""
    from app.models.bid_model import Bid
    from app.models.tender_model import Tender

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    bids = db.query(Bid).filter(Bid.tender_id == tender_id).all()
    if len(bids) < 2:
        return {
            "tender_id": str(tender_id),
            "message": "Need at least 2 bids for collusion analysis",
        }

    from app.ml.collusion import detect_bid_collusion

    bids_data = [
        {
            "supplier_id": str(b.supplier_id),
            "bid_amount": b.bid_amount,
            "proposal_text": b.proposal_text or "",
        }
        for b in bids
    ]
    result = detect_bid_collusion(bids_data, tender.description)
    result["tender_id"] = str(tender_id)
    result["bid_count"] = len(bids)
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────


def _spacy_available() -> bool:
    try:
        import spacy

        spacy.load("en_core_web_sm")
        return True
    except Exception:
        return False


def _prophet_available() -> bool:
    try:
        from prophet import Prophet  # noqa

        return True
    except ImportError:
        return False


def _claude_available() -> bool:
    from app.core.config import settings

    return bool(settings.ANTHROPIC_API_KEY)
