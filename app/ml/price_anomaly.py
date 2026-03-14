"""
Model: IsolationForest — Price Anomaly Detection
Proposal Layer: 2 (Intelligent Price Inflation Detection)
Library: sklearn.ensemble.IsolationForest

PURPOSE
-------
Goes beyond simple deviation comparison. IsolationForest detects price
outliers in a multivariate space (price × category × county × contract_size).
A cement purchase priced at KES 750/bag in Nairobi might be normal, but
KES 750/bag in a remote county with 5x logistics costs is suspicious at a
*different* threshold. IF captures this context automatically.

FEATURES (X)
------------
  0  price_per_unit          float   actual price / quantity
  1  benchmark_avg           float   market benchmark avg_price
  2  deviation_ratio         float   (price - benchmark) / benchmark
  3  log_contract_value      float   log1p(estimated_value)
  4  category_code           int     label-encoded category
  5  county_code             int     label-encoded county

OUTPUT
------
  anomaly_score: float  raw decision_function score (higher = more normal)
  is_anomaly:   bool    True if score < threshold (contamination=0.1)
  confidence:   float   0.0–1.0 scaled anomaly confidence
"""

import os
import pickle
from typing import Optional

import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "weights", "price_anomaly_if.pkl")
ENCODER_PATH = os.path.join(
    os.path.dirname(__file__), "weights", "price_anomaly_encoders.pkl"
)

# Contamination = expected fraction of corrupt tenders in training data
# Proposal estimates 30-40% of tenders have some price anomaly
CONTAMINATION = 0.15


# ── Feature engineering ────────────────────────────────────────────────────────

CATEGORY_MAP = {
    "construction": 0,
    "infrastructure": 1,
    "ict equipment": 2,
    "medical supplies": 3,
    "vehicles": 4,
    "furniture": 5,
    "stationery": 6,
    "fuel": 7,
    "consulting services": 8,
    "professional services": 9,
    "other": 10,
}

COUNTY_MAP = {
    "nairobi": 0,
    "mombasa": 1,
    "kisumu": 2,
    "nakuru": 3,
    "eldoret": 4,
    "thika": 5,
    "meru": 6,
    "nyeri": 7,
    "garissa": 8,
    "turkana": 9,
    "national": 10,
    "other": 11,
}


def build_feature_vector(
    price: float,
    benchmark_avg: float,
    estimated_value: float,
    category: Optional[str],
    county: Optional[str],
) -> np.ndarray:
    deviation_ratio = (price - benchmark_avg) / max(benchmark_avg, 1.0)
    log_value = np.log1p(max(estimated_value, 0))
    cat_code = CATEGORY_MAP.get((category or "").lower(), CATEGORY_MAP["other"])
    county_code = COUNTY_MAP.get((county or "").lower(), COUNTY_MAP["other"])

    return np.array(
        [
            [
                price,
                benchmark_avg,
                deviation_ratio,
                log_value,
                cat_code,
                county_code,
            ]
        ]
    )


# ── Training (run once with labeled data) ────────────────────────────────────


def train(training_records: list[dict]) -> None:
    """
    Train the IsolationForest on historical tender records.

    Each record: {
        price: float,
        benchmark_avg: float,
        estimated_value: float,
        category: str,
        county: str,
    }

    Saves model to app/ml/weights/price_anomaly_if.pkl
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    X = np.vstack(
        [
            build_feature_vector(
                r["price"],
                r["benchmark_avg"],
                r["estimated_value"],
                r.get("category"),
                r.get("county"),
            )
            for r in training_records
        ]
    )

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=CONTAMINATION,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(ENCODER_PATH, "wb") as f:
        pickle.dump({"scaler": scaler}, f)

    print(
        f"Price anomaly model trained on {len(training_records)} records → {MODEL_PATH}"
    )


# ── Inference ──────────────────────────────────────────────────────────────────


def _load_model():
    if not os.path.exists(MODEL_PATH):
        return None, None
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(ENCODER_PATH, "rb") as f:
        encoders = pickle.load(f)
    return model, encoders


def predict(
    price: float,
    benchmark_avg: float,
    estimated_value: float,
    category: Optional[str] = None,
    county: Optional[str] = None,
) -> dict:
    """
    Returns:
      {
        is_anomaly: bool,
        anomaly_score: float,    # raw IF score; negative = anomalous
        confidence: float,       # 0-1, how anomalous (0=normal, 1=extremely anomalous)
        model_used: str
      }
    """
    model, encoders = _load_model()

    if model is None:
        # Model not trained yet — fall back to simple deviation
        deviation = (price - benchmark_avg) / max(benchmark_avg, 1.0)
        is_anomaly = deviation > 0.5
        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": -deviation if is_anomaly else deviation,
            "confidence": min(abs(deviation), 1.0),
            "model_used": "fallback_deviation",
        }

    X = build_feature_vector(price, benchmark_avg, estimated_value, category, county)
    X_scaled = encoders["scaler"].transform(X)

    # decision_function: negative = anomaly, positive = normal
    raw_score = float(model.decision_function(X_scaled)[0])
    is_anomaly = model.predict(X_scaled)[0] == -1

    # Normalise to 0-1 confidence (how anomalous)
    # Raw scores typically range from -0.5 to +0.5
    confidence = max(0.0, min(1.0, (-raw_score + 0.5)))

    return {
        "is_anomaly": is_anomaly,
        "anomaly_score": round(raw_score, 4),
        "confidence": round(confidence, 4),
        "model_used": "isolation_forest",
    }
