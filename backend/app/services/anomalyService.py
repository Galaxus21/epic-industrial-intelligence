"""
EPIC — Statistical Anomaly Detection

Fits an Isolation Forest over STORED sensor history (models.SensorHistory) to
surface outliers that threshold comparison cannot reach: drift, variance shift,
and excursions below the configured alarm value.

Design rules:
- Operates ONLY on stored readings. Synthesised history (sensors._generate_history)
  is never an input — detecting anomalies in fabricated data produces findings that
  look real and are not.
- Advisory only. Nothing here may trigger a work order; see threshold_monitor.
"""
from __future__ import annotations

import math
from typing import Any
import numpy as np
from sklearn.ensemble import IsolationForest

from app.services import db_service as db

MIN_SAMPLES_TO_FIT = 30      # below this, return no result — NOT "no anomalies"
CONTAMINATION_RATE = 0.06    # expected outlier fraction
RANDOM_SEED = 42             # pinned: identical input must give identical output
ROLLING_MEDIAN_WINDOW = 5    # points used for the deviation feature


def _compute_rolling_median(values: np.ndarray, window: int = ROLLING_MEDIAN_WINDOW) -> np.ndarray:
    """Compute rolling median for a 1D array over preceding points up to window size."""
    n = len(values)
    medians = np.empty(n, dtype=float)
    for i in range(n):
        start_idx = max(0, i - window + 1)
        medians[i] = np.median(values[start_idx : i + 1])
    return medians


def numericPoints(readings: list[Any]) -> list[dict[str, Any]]:
    """The stored points whose value is a real number, unchanged. None, booleans, text, NaN and non-dicts are
    dropped: history written by an older document upload can hold a figure it could not read (value None)."""
    return [r for r in readings if isinstance(r, dict) and _isNumber(r.get("value"))]


def filter_numeric_readings(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The numeric points reduced to {ts, value} for the model fit."""
    return [{"ts": str(r.get("ts", "")), "value": float(r["value"])} for r in numericPoints(readings)]


def _isNumber(value: Any) -> bool:
    # bool is a subclass of int, so True would otherwise pass as 1.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not math.isnan(value)


def detect_series_anomalies(readings: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """
    Fit IsolationForest on a single sensor's readings array.
    
    Returns:
      list of {"ts": str, "value": float, "score": float} if >= MIN_SAMPLES_TO_FIT
      valid numeric samples exist; otherwise returns None (insufficient data).
    """
    valid = filter_numeric_readings(readings)
    if len(valid) < MIN_SAMPLES_TO_FIT:
        return None

    values = np.array([item["value"] for item in valid], dtype=float)
    medians = _compute_rolling_median(values, ROLLING_MEDIAN_WINDOW)
    # Minimum two-feature matrix: [value, value - rolling_median(value)]
    features = np.column_stack([values, values - medians])

    clf = IsolationForest(contamination=CONTAMINATION_RATE, random_state=RANDOM_SEED)
    preds = clf.fit_predict(features)
    scores = clf.decision_function(features)

    anomalies: list[dict[str, Any]] = []
    for i, (pred, score) in enumerate(zip(preds, scores)):
        if pred == -1:
            anomalies.append({
                "ts": valid[i]["ts"],
                "value": valid[i]["value"],
                "score": float(score),
            })
    return anomalies


async def detect_stored_anomalies(equipment_id: str) -> dict[str, Any]:
    """
    Detect statistical outliers over stored sensor history for an equipment.

    Returns:
      {
        "equipment_id": str,
        "sensors": {sensor_key: {"anomalies": [{ts, value, score}], "n_points": int}},
        "skipped": {sensor_key: reason},   # sensors with too little stored data
      }
    """
    stored = await db.get_sensor_history(equipment_id)   # {sensor_key: [reading, ...]}
    sensors: dict[str, Any] = {}
    skipped: dict[str, str] = {}

    for sensor_key, readings in stored.items():
        if not isinstance(readings, list):
            skipped[sensor_key] = "Sensor history readings is not a list"
            continue

        valid = filter_numeric_readings(readings)
        if len(valid) < MIN_SAMPLES_TO_FIT:
            skipped[sensor_key] = f"Insufficient numeric data points ({len(valid)} < {MIN_SAMPLES_TO_FIT})"
            continue

        anomalies = detect_series_anomalies(valid)
        sensors[sensor_key] = {
            "anomalies": anomalies if anomalies is not None else [],
            "n_points": len(valid),
        }

    return {
        "equipment_id": equipment_id,
        "sensors": sensors,
        "skipped": skipped,
    }
