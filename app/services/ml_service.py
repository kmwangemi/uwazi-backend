"""
ML Service — wraps all ML model status, training, and forecast calls
for the ML status page.
"""

import os

WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "weights")


def _exists(filename: str) -> bool:
    return os.path.exists(os.path.join(WEIGHTS_DIR, filename))


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
    try:
        from app.core.config import settings

        return bool(settings.ANTHROPIC_API_KEY)
    except Exception:
        return False


def get_model_status() -> list[dict]:
    """
    Returns list of model status dicts matching the frontend model card shape.
    """
    return [
        {
            "id": "xgboost_risk_model",
            "name": "XGBoost Risk Model",
            "library": "XGBoost",
            "layer": "Layer 5 — Corruption Risk Score",
            "trained": _exists("xgb_risk_model.pkl"),
            "trainable": True,
            "train_endpoint": "/ml/train/xgboost-synthetic",
        },
        {
            "id": "price_anomaly_isolation_forest",
            "name": "Price Anomaly Detector",
            "library": "Isolation Forest",
            "layer": "Layer 2 — Price Inflation",
            "trained": _exists("price_anomaly_if.pkl"),
            "trainable": True,
            "train_endpoint": "/ml/train/price-anomaly",
        },
        {
            "id": "collusion_tfidf_vectorizer",
            "name": "Collusion Vectorizer",
            "library": "TF-IDF + Cosine Similarity",
            "layer": "Layer 4 — Bid Collusion",
            "trained": _exists("collusion_tfidf.pkl"),
            "trainable": True,
            "train_endpoint": "/ml/train/collusion-vectorizer",
        },
        {
            "id": "spec_spacy_nlp",
            "name": "Specification Analyzer",
            "library": "spaCy NER",
            "layer": "Layer 4 — Spec Analysis",
            "trained": _spacy_available(),
            "trainable": False,
            "train_endpoint": None,
        },
        {
            "id": "supplier_random_forest",
            "name": "Ghost Company Detector (RF)",
            "library": "Random Forest",
            "layer": "Layer 3 — Ghost Supplier",
            "trained": _exists("supplier_rf.pkl"),
            "trainable": True,
            "train_endpoint": "/ml/train/supplier-rf",
        },
        {
            "id": "supplier_isolation_forest",
            "name": "Supplier Anomaly Detector",
            "library": "Isolation Forest",
            "layer": "Layer 3 — Ghost Supplier",
            "trained": _exists("supplier_if.pkl"),
            "trainable": True,
            "train_endpoint": "/ml/train/supplier-if",
        },
        {
            "id": "prophet_spending",
            "name": "Trend Forecaster",
            "library": "Prophet",
            "layer": "Layer 6 — Temporal Patterns",
            "trained": _prophet_available(),
            "trainable": False,
            "train_endpoint": None,
        },
        {
            "id": "claude_llm",
            "name": "Claude AI Narratives",
            "library": "Anthropic Claude",
            "layer": "Cross-cutting — AI Analysis",
            "trained": _claude_available(),
            "trainable": False,
            "train_endpoint": None,
        },
    ]


async def train_supplier_rf(db) -> dict:
    """Train Random Forest + IsolationForest on supplier records from DB."""
    from sqlalchemy import select

    from app.models.supplier_model import Supplier

    result = await db.execute(select(Supplier))
    suppliers = result.scalars().all()

    if len(suppliers) < 20:
        raise ValueError(
            f"Need at least 20 suppliers to train. Currently have {len(suppliers)}."
        )

    records = [
        {
            "company_age_days": s.company_age_days,
            "tax_filings_count": s.tax_filings_count,
            "directors": [],  # directors not eager-loaded here
            "has_physical_address": s.has_physical_address,
            "has_online_presence": s.has_online_presence,
            "past_contracts_count": s.past_contracts_count,
            "past_contracts_value": s.past_contracts_value,
            "employee_count": s.employee_count,
            "is_ghost": s.is_blacklisted,  # proxy label
        }
        for s in suppliers
    ]

    from app.ml.supplier_risk import train
    from fastapi.concurrency import run_in_threadpool

    await run_in_threadpool(train, records)
    return {"status": "success", "records_used": len(records)}


async def train_supplier_if(db) -> dict:
    """Train only the IsolationForest on supplier records (unsupervised)."""
    from sqlalchemy import select

    from app.models.supplier_model import Supplier

    result = await db.execute(select(Supplier))
    suppliers = result.scalars().all()

    if len(suppliers) < 20:
        raise ValueError(f"Need at least 20 suppliers. Have {len(suppliers)}.")

    records = [
        {
            "company_age_days": s.company_age_days,
            "tax_filings_count": s.tax_filings_count,
            "directors": [],
            "has_physical_address": s.has_physical_address,
            "has_online_presence": s.has_online_presence,
            "past_contracts_count": s.past_contracts_count,
            "past_contracts_value": s.past_contracts_value,
            "employee_count": s.employee_count,
        }
        for s in suppliers
    ]

    from app.ml.supplier_risk import train_unsupervised_only
    from fastapi.concurrency import run_in_threadpool

    await run_in_threadpool(train_unsupervised_only, records)
    return {"status": "success", "records_used": len(records)}
