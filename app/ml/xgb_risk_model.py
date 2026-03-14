"""
Model: XGBClassifier — Corruption Risk Scoring (PRIMARY ML MODEL)
Proposal Layer: 5 (Predictive Risk Modeling)
Library: xgboost

FROM PROPOSAL
-------------
"XGBoost model trained on historical corruption cases (EACC prosecutions,
Auditor General findings, known scandals) predicts corruption likelihood.
Input features include price deviation, supplier red flags, specification
restrictiveness, entity's historical corruption record, contract value,
procurement method, and political calendar proximity."
"85-90% accuracy"

FEATURES (10 features) — exactly as listed in the proposal
-----------------------------------------------------------
  0  price_deviation_pct       float  deviation from market benchmark (%)
  1  supplier_ghost_prob       float  ghost supplier probability (0-1)
  2  spec_restrictiveness      float  spec score (0-100)
  3  contract_value_log        float  log1p(estimated_value_KES)
  4  procurement_method_enc    int    0=open, 1=restricted, 2=direct, 3=RFQ
  5  entity_history_score      float  entity corruption history score (0-100)
  6  deadline_days             int    days from publication to submission deadline
  7  bid_count                 int    number of bids received
  8  single_bidder             int    1 if only 1 bid received
  9  political_proximity       int    days to nearest election (0=unknown)

OUTPUT
------
  corruption_probability: float  0.0–1.0
  risk_score:             float  0–100  (probability × 100)
  risk_level:             str    low / medium / high / critical
  feature_importance:     dict   {feature_name: importance} (available after training)

TRAINING DATA SOURCES (from proposal)
--------------------------------------
  - EACC prosecution records
  - Auditor-General annual reports
  - Known scandals: NYS, Afya House, COVID PPE
  - Negative class: clean tenders from low-corruption entities
"""

import os
import pickle
from typing import Optional

import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "weights", "xgb_risk_model.pkl")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "weights", "xgb_scaler.pkl")

FEATURE_NAMES = [
    "price_deviation_pct",
    "supplier_ghost_prob",
    "spec_restrictiveness",
    "contract_value_log",
    "procurement_method_enc",
    "entity_history_score",
    "deadline_days",
    "bid_count",
    "single_bidder",
    "political_proximity",
]

PROCUREMENT_METHOD_ENC = {
    "open_tender": 0,
    "restricted": 1,
    "direct_procurement": 2,
    "request_for_quotation": 3,
    "request_for_proposal": 3,
    None: 0,
}

RISK_THRESHOLDS = {
    "critical": 0.80,
    "high": 0.60,
    "medium": 0.40,
}


def _build_features(
    price_deviation_pct: float,
    supplier_ghost_prob: float,
    spec_restrictiveness: float,
    estimated_value: float,
    procurement_method: Optional[str],
    entity_history_score: float,
    deadline_days: Optional[int],
    bid_count: int,
    single_bidder: bool,
    political_proximity_days: Optional[int],
) -> np.ndarray:
    return np.array(
        [
            [
                price_deviation_pct,
                supplier_ghost_prob,
                spec_restrictiveness / 100.0,  # normalise to 0-1
                float(np.log1p(max(estimated_value, 0))),
                PROCUREMENT_METHOD_ENC.get(procurement_method, 0),
                entity_history_score / 100.0,  # normalise to 0-1
                deadline_days if deadline_days is not None else 30,
                bid_count,
                1 if single_bidder else 0,
                (
                    political_proximity_days
                    if political_proximity_days is not None
                    else 365
                ),
            ]
        ]
    )


# ── Training ──────────────────────────────────────────────────────────────────


def train(labeled_records: list[dict]) -> None:
    """
    Train XGBoost on historically labeled tenders.

    Each record:
    {
        price_deviation_pct: float,
        supplier_ghost_prob: float,
        spec_restrictiveness: float,
        estimated_value: float,
        procurement_method: str,
        entity_history_score: float,
        deadline_days: int,
        bid_count: int,
        single_bidder: bool,
        political_proximity_days: int,
        is_corrupt: bool     ← label
    }
    """
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier

    X = np.vstack(
        [
            _build_features(
                r.get("price_deviation_pct", 0),
                r.get("supplier_ghost_prob", 0),
                r.get("spec_restrictiveness", 0),
                r.get("estimated_value", 0),
                r.get("procurement_method"),
                r.get("entity_history_score", 0),
                r.get("deadline_days"),
                r.get("bid_count", 1),
                r.get("single_bidder", False),
                r.get("political_proximity_days"),
            )
            for r in labeled_records
        ]
    )

    y = np.array([1 if r.get("is_corrupt") else 0 for r in labeled_records])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Class imbalance: corrupt tenders are minority
    n_neg = (y == 0).sum()
    n_pos = (y == 1).sum()
    scale_pos_weight = n_neg / max(n_pos, 1)

    model = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,  # handle class imbalance
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled, y)

    # Cross-validation score
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="roc_auc")
    print(f"XGBoost CV ROC-AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # Feature importances
    importances = sorted(
        zip(FEATURE_NAMES, model.feature_importances_), key=lambda x: -x[1]
    )
    print("Feature importances:")
    for name, imp in importances:
        print(f"  {name:30s} {imp:.4f}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

    print(f"XGBoost model saved → {MODEL_PATH}")


def train_with_synthetic_data() -> None:
    """
    Bootstrap training with synthetic data based on known corruption patterns.
    Use until real labeled data from EACC is available.

    Generates ~500 synthetic records: corrupt + clean tenders
    based on the corruption schemes described in the proposal.
    """
    rng = np.random.default_rng(42)
    records = []

    # Corrupt tenders (250) — based on proposal corruption patterns
    for _ in range(250):
        records.append(
            {
                "price_deviation_pct": rng.uniform(50, 500),  # 50-500% inflation
                "supplier_ghost_prob": rng.uniform(0.5, 1.0),  # ghost supplier likely
                "spec_restrictiveness": rng.uniform(40, 100),  # restrictive specs
                "estimated_value": rng.uniform(5_000_000, 500_000_000),
                "procurement_method": rng.choice(["direct_procurement", "restricted"]),
                "entity_history_score": rng.uniform(50, 100),
                "deadline_days": rng.integers(1, 10),  # very short
                "bid_count": rng.integers(1, 3),  # few bids
                "single_bidder": bool(rng.integers(0, 2)),
                "political_proximity_days": rng.integers(0, 90),  # near election
                "is_corrupt": True,
            }
        )

    # Clean tenders (250) — normal procurement
    for _ in range(250):
        records.append(
            {
                "price_deviation_pct": rng.uniform(-10, 20),  # near-market pricing
                "supplier_ghost_prob": rng.uniform(0.0, 0.2),  # legitimate supplier
                "spec_restrictiveness": rng.uniform(0, 25),  # open specs
                "estimated_value": rng.uniform(500_000, 50_000_000),
                "procurement_method": rng.choice(
                    ["open_tender", "request_for_quotation"]
                ),
                "entity_history_score": rng.uniform(0, 30),
                "deadline_days": rng.integers(21, 60),  # reasonable
                "bid_count": rng.integers(3, 15),  # competitive
                "single_bidder": False,
                "political_proximity_days": rng.integers(180, 365),
                "is_corrupt": False,
            }
        )

    print(f"Training XGBoost on {len(records)} synthetic records...")
    train(records)
    print("Note: Replace with real EACC/Auditor-General labeled data for production.")


# ── Inference ──────────────────────────────────────────────────────────────────


def _load_model():
    if not os.path.exists(MODEL_PATH):
        return None, None
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    return model, scaler


def predict(
    price_deviation_pct: float,
    supplier_ghost_prob: float,
    spec_restrictiveness: float,
    estimated_value: float,
    procurement_method: Optional[str] = None,
    entity_history_score: float = 0.0,
    deadline_days: Optional[int] = None,
    bid_count: int = 1,
    single_bidder: bool = False,
    political_proximity_days: Optional[int] = None,
) -> dict:
    """
    Predict corruption probability for a tender.

    Returns:
    {
        corruption_probability: float  0.0-1.0
        risk_score:             float  0-100
        risk_level:             str    low/medium/high/critical
        model_used:             str
    }
    """
    model, scaler = _load_model()

    X = _build_features(
        price_deviation_pct,
        supplier_ghost_prob,
        spec_restrictiveness,
        estimated_value,
        procurement_method,
        entity_history_score,
        deadline_days,
        bid_count,
        single_bidder,
        political_proximity_days,
    )

    if model is None:
        # Fallback to weighted composite (mirrors risk_engine.py rules)
        prob = _rule_based_probability(
            price_deviation_pct,
            supplier_ghost_prob,
            spec_restrictiveness,
            procurement_method,
        )
        model_name = "rule_based_fallback"
    else:
        X_scaled = scaler.transform(X)
        prob = float(model.predict_proba(X_scaled)[0][1])
        model_name = "xgboost"

    risk_score = round(prob * 100, 2)

    if prob >= RISK_THRESHOLDS["critical"]:
        risk_level = "critical"
    elif prob >= RISK_THRESHOLDS["high"]:
        risk_level = "high"
    elif prob >= RISK_THRESHOLDS["medium"]:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "corruption_probability": round(prob, 4),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "model_used": model_name,
    }


def _rule_based_probability(
    price_dev: float, ghost_prob: float, spec_score: float, method: Optional[str]
) -> float:
    score = (
        min(price_dev / 500, 1.0) * 0.40
        + ghost_prob * 0.30
        + (spec_score / 100) * 0.20
        + (0.8 if method == "direct_procurement" else 0.1) * 0.10
    )
    return min(score, 1.0)
