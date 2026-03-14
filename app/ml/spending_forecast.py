"""
Model: Prophet — Temporal Spending Pattern Analysis
Proposal Layer: 6 (Time-Series: ARIMA and Prophet for spending pattern analysis)
Library: prophet (Facebook/Meta)

FROM PROPOSAL
-------------
"ARIMA and Prophet for spending pattern analysis"
"LSTM networks for sequential corruption patterns"

PURPOSE
-------
Detect abnormal procurement spend patterns over time:
  1. Year-end budget rushes (unspent funds released in bulk in June)
  2. Pre-election spending spikes (inflated contracts awarded near elections)
  3. Entity-specific anomalies (sudden 5× spend increase in a department)

These temporal patterns are a key corruption signal identified in the proposal
and are distinct from per-tender analysis.

INSTALL
-------
  pip install prophet

INPUTS
------
  df: DataFrame with columns [ds (date), y (spend_amount)]
  entity: Optional entity/county name for context

OUTPUTS
-------
  {
    forecast: DataFrame  (ds, yhat, yhat_lower, yhat_upper, trend)
    anomalies: [
        {date, actual_spend, expected_spend, deviation_pct, severity}
    ]
    anomaly_dates: [str]
    pattern_summary: str
    anomaly_risk_score: float  0-100
  }
"""

from datetime import datetime
from typing import Optional


def detect_spending_anomalies(
    spend_records: list[dict],  # [{date: str/datetime, amount: float}]
    entity_name: Optional[str] = None,
    forecast_periods: int = 90,  # days to forecast ahead
) -> dict:
    """
    Fit Prophet on historical spending data and detect anomalies.

    spend_records: list of {date, amount} dicts, at least 60 records recommended
    """
    if len(spend_records) < 30:
        return {
            "forecast": [],
            "anomalies": [],
            "anomaly_dates": [],
            "pattern_summary": "Insufficient data for time-series analysis (need 30+ records)",
            "anomaly_risk_score": 0.0,
            "model_used": "none",
        }

    try:
        import numpy as np
        import pandas as pd
        from prophet import Prophet

        # Build DataFrame in Prophet format
        df = (
            pd.DataFrame(
                [
                    {"ds": pd.to_datetime(r["date"]), "y": float(r["amount"])}
                    for r in spend_records
                ]
            )
            .sort_values("ds")
            .dropna()
        )

        if len(df) < 30:
            return {
                "forecast": [],
                "anomalies": [],
                "anomaly_dates": [],
                "pattern_summary": "Insufficient valid records after cleaning",
                "anomaly_risk_score": 0.0,
                "model_used": "none",
            }

        # Prophet with Kenya-specific seasonality
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,  # procurement is not weekly-seasonal
            daily_seasonality=False,
            changepoint_prior_scale=0.05,  # less flexible — procurement is lumpy
            seasonality_mode="multiplicative",
            interval_width=0.95,
        )

        # Add Kenya fiscal year seasonality (July-June)
        model.add_seasonality(
            name="fiscal_year_end",
            period=365.25,
            fourier_order=5,
        )

        model.fit(df)

        # Forecast for in-sample + future
        future = model.make_future_dataframe(periods=forecast_periods, freq="D")
        forecast = model.predict(future)

        # Detect anomalies in historical data
        # Actual outside 95% prediction interval = anomaly
        merged = df.merge(
            forecast[["ds", "yhat", "yhat_lower", "yhat_upper", "trend"]],
            on="ds",
            how="left",
        )

        anomalies = []
        for _, row in merged.iterrows():
            if row["y"] > row["yhat_upper"]:
                deviation = (row["y"] - row["yhat"]) / max(row["yhat"], 1) * 100
                severity = (
                    "critical"
                    if deviation > 200
                    else "high" if deviation > 100 else "medium"
                )
                anomalies.append(
                    {
                        "date": row["ds"].strftime("%Y-%m-%d"),
                        "actual_spend": round(row["y"], 2),
                        "expected_spend": round(row["yhat"], 2),
                        "deviation_pct": round(deviation, 2),
                        "severity": severity,
                    }
                )
            elif row["y"] < row["yhat_lower"] and row["y"] > 0:
                pass  # Under-spend is less suspicious in this context

        anomaly_dates = [a["date"] for a in anomalies]

        # Risk score based on anomaly count and severity
        if not anomalies:
            risk_score = 0.0
        else:
            critical_count = sum(1 for a in anomalies if a["severity"] == "critical")
            high_count = sum(1 for a in anomalies if a["severity"] == "high")
            risk_score = min(
                critical_count * 30 + high_count * 15 + len(anomalies) * 5, 100.0
            )

        # Check for pre-election spike (within 90 days of election)
        election_signal = _check_election_proximity(anomalies)
        if election_signal:
            risk_score = min(risk_score + 25, 100.0)

        # Summary
        pattern_summary = _build_summary(
            entity_name, anomalies, risk_score, election_signal
        )

        # Serialise forecast tail (last 90 days + future)
        forecast_out = (
            forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
            .tail(90 + forecast_periods)
            .to_dict("records")
        )
        forecast_out = [
            {
                k: (
                    v.strftime("%Y-%m-%d")
                    if hasattr(v, "strftime")
                    else round(float(v), 2)
                )
                for k, v in row.items()
            }
            for row in forecast_out
        ]

        return {
            "forecast": forecast_out,
            "anomalies": anomalies,
            "anomaly_dates": anomaly_dates,
            "pattern_summary": pattern_summary,
            "anomaly_risk_score": round(risk_score, 2),
            "election_proximity_signal": election_signal,
            "model_used": "prophet",
        }

    except ImportError:
        return {
            "forecast": [],
            "anomalies": [],
            "anomaly_dates": [],
            "pattern_summary": "Prophet not installed. Run: pip install prophet",
            "anomaly_risk_score": 0.0,
            "model_used": "unavailable",
        }


# ── Kenya election calendar ─────────────────────────────────────────────────

KENYA_ELECTION_DATES = [
    datetime(2017, 8, 8),
    datetime(2022, 8, 9),
    datetime(2027, 8, 10),  # projected
]


def _check_election_proximity(anomalies: list[dict]) -> bool:
    """Check if anomaly dates fall within 90 days of a Kenya general election."""
    for anomaly in anomalies:
        anomaly_dt = datetime.strptime(anomaly["date"], "%Y-%m-%d")
        for election_dt in KENYA_ELECTION_DATES:
            delta = abs((anomaly_dt - election_dt).days)
            if delta <= 90:
                return True
    return False


def _build_summary(entity, anomalies, risk_score, election_signal) -> str:
    if not anomalies:
        return (
            f"{entity or 'Entity'}: No spending anomalies detected in historical data."
        )

    worst = max(anomalies, key=lambda a: a["deviation_pct"])
    base = (
        f"{entity or 'Entity'}: {len(anomalies)} spending anomalies detected. "
        f"Worst: {worst['deviation_pct']:.0f}% above forecast on {worst['date']}. "
        f"Risk score: {risk_score:.0f}/100."
    )
    if election_signal:
        base += " ⚠️ Anomalies coincide with election period — high corruption risk."
    return base
