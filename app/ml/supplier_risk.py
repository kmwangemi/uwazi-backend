"""
Models: RandomForestClassifier + IsolationForest — Ghost Supplier Detection
Proposal Layer: 3 (Ghost Supplier Detection)
Libraries: sklearn.ensemble

PURPOSE
-------
Two-model approach from the proposal:
  1. RandomForestClassifier  — SUPERVISED: trained on known ghost/legit suppliers
     from EACC prosecutions, Auditor-General findings.
  2. IsolationForest         — UNSUPERVISED: flags structural outliers when
     no labeled data is available (new system bootstrap).

Both run in parallel; the higher risk score wins.

FEATURES (X) — 8 features
--------------------------
  0  company_age_days         int    days since incorporation
  1  tax_filings_count        int    number of KRA returns filed
  2  director_company_count   int    max companies per director
  3  has_physical_address     int    0/1
  4  has_online_presence      int    0/1
  5  past_contracts_count     int    prior government contracts
  6  past_contracts_value_log float  log1p(total prior contract value)
  7  employee_count           int    0 if unknown

OUTPUTS
-------
  ghost_probability:   float  0.0–1.0  (RF supervised)
  anomaly_confidence:  float  0.0–1.0  (IF unsupervised)
  combined_score:      float  0–100    max(RF, IF) scaled
  model_used:          str
"""

import os
import pickle
from typing import Optional

import numpy as np

RF_MODEL_PATH = os.path.join(os.path.dirname(__file__), "weights", "supplier_rf.pkl")
IF_MODEL_PATH = os.path.join(os.path.dirname(__file__), "weights", "supplier_if.pkl")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "weights", "supplier_scaler.pkl")

FEATURE_NAMES = [
    "company_age_days",
    "tax_filings_count",
    "director_company_count",
    "has_physical_address",
    "has_online_presence",
    "past_contracts_count",
    "past_contracts_value_log",
    "employee_count",
]


def _build_features(
    company_age_days: Optional[int],
    tax_filings_count: int,
    directors: list,
    has_physical_address: Optional[bool],
    has_online_presence: Optional[bool],
    past_contracts_count: int,
    past_contracts_value: float,
    employee_count: Optional[int],
) -> np.ndarray:
    # Max companies any single director is linked to
    max_dir_companies = max(
        (len(d.get("other_companies", [])) for d in (directors or [])), default=0
    )

    return np.array(
        [
            [
                company_age_days if company_age_days is not None else 365,
                tax_filings_count,
                max_dir_companies,
                1 if has_physical_address else 0,
                1 if has_online_presence else 0,
                past_contracts_count,
                float(np.log1p(max(past_contracts_value, 0))),
                employee_count if employee_count is not None else 0,
            ]
        ]
    )


# ── Training ──────────────────────────────────────────────────────────────────


def train(labeled_records: list[dict]) -> None:
    """
    Train both RF and IF models.

    Each labeled record:
    {
        company_age_days, tax_filings_count, directors, has_physical_address,
        has_online_presence, past_contracts_count, past_contracts_value,
        employee_count,
        is_ghost: bool   ← label (True = confirmed ghost/fraudulent)
    }
    """
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.preprocessing import StandardScaler

    X = np.vstack(
        [
            _build_features(
                r.get("company_age_days"),
                r.get("tax_filings_count", 0),
                r.get("directors", []),
                r.get("has_physical_address"),
                r.get("has_online_presence"),
                r.get("past_contracts_count", 0),
                r.get("past_contracts_value", 0.0),
                r.get("employee_count"),
            )
            for r in labeled_records
        ]
    )
    y = np.array([1 if r.get("is_ghost") else 0 for r in labeled_records])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # RF — class weight balanced because ghost suppliers are minority
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_scaled, y)

    # IF — unsupervised on full dataset
    isolation_f = IsolationForest(
        n_estimators=200,
        contamination=0.20,  # ~20% ghost estimate from proposal
        random_state=42,
        n_jobs=-1,
    )
    isolation_f.fit(X_scaled)

    os.makedirs(os.path.dirname(RF_MODEL_PATH), exist_ok=True)
    with open(RF_MODEL_PATH, "wb") as f:
        pickle.dump(rf, f)
    with open(IF_MODEL_PATH, "wb") as f:
        pickle.dump(isolation_f, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

    # Print feature importances
    importances = sorted(
        zip(FEATURE_NAMES, rf.feature_importances_), key=lambda x: -x[1]
    )
    print("Feature importances (RF):")
    for name, imp in importances:
        print(f"  {name:35s} {imp:.4f}")


def train_unsupervised_only(records: list[dict]) -> None:
    """
    Train only the IsolationForest when no labels are available (bootstrap phase).
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    X = np.vstack(
        [
            _build_features(
                r.get("company_age_days"),
                r.get("tax_filings_count", 0),
                r.get("directors", []),
                r.get("has_physical_address"),
                r.get("has_online_presence"),
                r.get("past_contracts_count", 0),
                r.get("past_contracts_value", 0.0),
                r.get("employee_count"),
            )
            for r in records
        ]
    )

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    isolation_f = IsolationForest(n_estimators=200, contamination=0.20, random_state=42)
    isolation_f.fit(X_scaled)

    os.makedirs(os.path.dirname(IF_MODEL_PATH), exist_ok=True)
    with open(IF_MODEL_PATH, "wb") as f:
        pickle.dump(isolation_f, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)


# ── Inference ──────────────────────────────────────────────────────────────────


def _load_models():
    scaler = rf = if_model = None
    if os.path.exists(SCALER_PATH):
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)
    if os.path.exists(RF_MODEL_PATH):
        with open(RF_MODEL_PATH, "rb") as f:
            rf = pickle.load(f)
    if os.path.exists(IF_MODEL_PATH):
        with open(IF_MODEL_PATH, "rb") as f:
            if_model = pickle.load(f)
    return scaler, rf, if_model


def predict(
    company_age_days: Optional[int],
    tax_filings_count: int,
    directors: list,
    has_physical_address: Optional[bool],
    has_online_presence: Optional[bool],
    past_contracts_count: int = 0,
    past_contracts_value: float = 0.0,
    employee_count: Optional[int] = None,
) -> dict:
    """
    Returns:
    {
        ghost_probability: float   0-1  (RandomForest, None if not trained)
        anomaly_confidence: float  0-1  (IsolationForest, None if not trained)
        combined_score: float      0-100
        model_used: str
    }
    """
    scaler, rf, if_model = _load_models()

    X = _build_features(
        company_age_days,
        tax_filings_count,
        directors,
        has_physical_address,
        has_online_presence,
        past_contracts_count,
        past_contracts_value,
        employee_count,
    )

    ghost_prob = None
    anomaly_conf = None
    models_used = []

    if scaler is not None:
        X_scaled = scaler.transform(X)

        if rf is not None:
            ghost_prob = float(rf.predict_proba(X_scaled)[0][1])  # P(ghost=1)
            models_used.append("random_forest")

        if if_model is not None:
            raw = float(if_model.decision_function(X_scaled)[0])
            anomaly_conf = max(0.0, min(1.0, -raw + 0.5))
            models_used.append("isolation_forest")

    # Combined score: take max of available predictions, scaled to 0-100
    scores = [s for s in [ghost_prob, anomaly_conf] if s is not None]
    if scores:
        combined = max(scores) * 100
    else:
        # Pure rule-based fallback
        combined = _rule_based_score(
            company_age_days,
            tax_filings_count,
            directors,
            has_physical_address,
            has_online_presence,
        )
        models_used.append("rule_based_fallback")

    return {
        "ghost_probability": round(ghost_prob, 4) if ghost_prob is not None else None,
        "anomaly_confidence": (
            round(anomaly_conf, 4) if anomaly_conf is not None else None
        ),
        "combined_score": round(combined, 2),
        "model_used": "+".join(models_used) if models_used else "none",
    }


def _rule_based_score(age, tax_filings, directors, has_address, has_online) -> float:
    """Fallback when no model is trained — mirrors supplier_checker.py logic."""
    score = 0.0
    if age is not None and age < 180:
        score += 40
    if tax_filings == 0:
        score += 30
    if has_address is False:
        score += 20
    if has_online is False:
        score += 10
    return min(score, 100.0)
