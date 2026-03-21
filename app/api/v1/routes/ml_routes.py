"""
ML Management routes:
  GET  /api/ml/status
  GET  /api/ml/performance
  POST /api/ml/train/xgboost-synthetic
  POST /api/ml/train/price-anomaly
  POST /api/ml/train/collusion-vectorizer
  POST /api/ml/train/supplier-rf
  POST /api/ml/train/supplier-if
  GET  /api/ml/spending-forecast/{entity_id}
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.contract_model import Contract
from app.models.procuring_entity_model import ProcuringEntity
from app.services.ml_service import (
    get_model_status,
    train_supplier_if,
    train_supplier_rf,
)

router = APIRouter(prefix="/ml", tags=["ML Models"])


# ── Status ─────────────────────────────────────────────────────────────────────


@router.get("/status")
async def model_status():
    """Which ML models are trained and available."""
    models = get_model_status()
    trained_count = sum(1 for m in models if m["trained"])
    untrained_count = sum(1 for m in models if not m["trained"] and m["trainable"])
    return {
        "models": models,
        "total": len(models),
        "trained_count": trained_count,
        "untrained_count": untrained_count,
    }


# ── Performance (synthetic scores until eval pipeline exists) ──────────────────


@router.get("/performance")
async def model_performance():
    """
    Per-model performance metrics.
    Returns real accuracy from model metadata if available,
    otherwise returns None so the frontend can show 'Not evaluated'.
    """
    import os
    import pickle

    WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "ml", "weights")

    def load_score(pkl_path: str, metric_key: str = "cv_score") -> float | None:
        meta_path = pkl_path.replace(".pkl", "_meta.pkl")
        if os.path.exists(meta_path):
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)
            return meta.get(metric_key)
        return None

    models = get_model_status()
    performance = []
    for m in models:
        if not m["trained"]:
            continue
        performance.append(
            {
                "id": m["id"],
                "name": m["name"],
                "accuracy": load_score(
                    os.path.join(WEIGHTS_DIR, f"{m['id']}.pkl")
                ),  # None if not saved
            }
        )
    return {"items": performance}


# ── Training endpoints ─────────────────────────────────────────────────────────


@router.post("/train/xgboost-synthetic")
async def train_xgboost_synthetic(user=Depends(require_role("admin"))):
    try:
        from app.ml.xgb_risk_model import train_with_synthetic_data

        train_with_synthetic_data()
        return {
            "status": "success",
            "message": "XGBoost trained on 500 synthetic records",
        }
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"xgboost not installed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/price-anomaly")
async def train_price_anomaly(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.price_benchmark_model import PriceBenchmark
    from app.models.tender_model import Tender

    result = await db.execute(
        select(Tender).filter(
            Tender.estimated_value.isnot(None),
            Tender.category.isnot(None),
        )
    )
    tenders = result.scalars().all()

    if len(tenders) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 50 tenders. Currently have {len(tenders)}.",
        )

    records = []
    for t in tenders:
        bench_result = await db.execute(
            select(PriceBenchmark).filter(
                PriceBenchmark.category.ilike(f"%{t.category}%")
            )
        )
        bench = bench_result.scalars().first()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/collusion-vectorizer")
async def train_collusion_vectorizer(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.bid_model import Bid

    result = await db.execute(select(Bid).filter(Bid.proposal_text.isnot(None)))
    bids = result.scalars().all()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/supplier-rf")
async def train_supplier_rf_route(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await train_supplier_rf(db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"sklearn not installed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/supplier-if")
async def train_supplier_if_route(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await train_supplier_if(db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"sklearn not installed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Spending forecast ──────────────────────────────────────────────────────────


@router.get("/spending-forecast/{entity_id}")
async def get_spending_forecast(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    entity_result = await db.execute(
        select(ProcuringEntity).filter(ProcuringEntity.id == entity_id)
    )
    entity = entity_result.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    from app.models.tender_model import Tender

    contract_result = await db.execute(
        select(Contract)
        .join(Tender)
        .filter(Tender.entity_id == entity_id, Contract.awarded_at.isnot(None))
    )
    contracts = contract_result.scalars().all()

    if len(contracts) < 10:
        return {
            "entity_id": str(entity_id),
            "entity_name": entity.name,
            "message": f"Insufficient data: {len(contracts)} contracts. Need 30+.",
            "anomalies": [],
            "forecast": [],
        }

    spend_records = [
        {"date": c.awarded_at.strftime("%Y-%m-%d"), "amount": c.contract_value}
        for c in contracts
    ]

    from app.ml.spending_forecast import detect_spending_anomalies

    anomaly_result = detect_spending_anomalies(spend_records, entity_name=entity.name)
    anomaly_result["entity_id"] = str(entity_id)
    anomaly_result["entity_name"] = entity.name
    return anomaly_result


# ── Collusion analysis ─────────────────────────────────────────────────────────

collusion_router = APIRouter(prefix="/tenders", tags=["Collusion Detection"])


@collusion_router.get("/{tender_id}/collusion-analysis")
async def analyse_tender_collusion(
    tender_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "investigator")),
):
    from app.models.bid_model import Bid
    from app.models.tender_model import Tender

    tender_result = await db.execute(select(Tender).filter(Tender.id == tender_id))
    tender = tender_result.scalars().first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    bids_result = await db.execute(select(Bid).filter(Bid.tender_id == tender_id))
    bids = bids_result.scalars().all()
    if len(bids) < 2:
        return {"tender_id": str(tender_id), "message": "Need at least 2 bids"}

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


@router.get("/entities")
async def list_entities_for_forecast(db: AsyncSession = Depends(get_db)):
    """Lightweight entity list for the spending forecast dropdown."""
    from sqlalchemy import select

    from app.models.procuring_entity_model import ProcuringEntity

    result = await db.execute(
        select(ProcuringEntity.id, ProcuringEntity.name).order_by(ProcuringEntity.name)
    )
    rows = result.all()
    return {"items": [{"id": str(r.id), "name": r.name} for r in rows]}
