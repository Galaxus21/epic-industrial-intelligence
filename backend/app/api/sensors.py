"""
AI Operations Brain — Sensors & Telemetry API
Dedicated sensor layer with stored history, anomaly detection,
and cross-referencing to maintenance records and incidents.

Endpoints:
  GET /api/v1/sensors/{equipment_id}          — full sensor dashboard for one equipment
  POST /api/v1/sensors/{equipment_id}/readings — authenticated live-telemetry ingress (value + stored history)
"""
from __future__ import annotations

import math
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.core.auth import require_roles
from app.core.roles import FIELD_ROLES
from app.db import models as m
from app.services import db_service as db
from app.services.anomalyService import detect_series_anomalies, numericPoints
from app.services.audit import record as audit_record
from app.services.sensorLabel import sensorLabel
from app.services.sensorReadings import recordLiveReadings
from app.services.alarmEvaluation import (
    is_in_alarm,
    is_in_trip,
    sensor_status,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Stored readings arrive at whatever interval their source used (daily demo seed, live telemetry), so the trend
# and the recent average are defined over a count of readings, never over a calendar window.
recentReadingCount = 7
trendThresholdPct = 3

# ── Stored history analysis ───────────────────────────────────────────────────

def _anomaly_periods(history: list[dict], reading_or_alarm: Any, trip: float | None = None) -> list[dict]:
    """Find contiguous stretches where value breaches alarm (or trip) threshold. A stretch that reaches trip at any
    point is a trip period, however it started."""
    if isinstance(reading_or_alarm, dict):
        reading = reading_or_alarm
    else:
        reading = {"alarm": reading_or_alarm, "trip": trip}
    if reading.get("alarm") is None:
        return []
    periods: list[dict] = []
    in_period = False
    start_ts = ""
    level = "alarm"
    for pt in history:
        val = pt.get("value")
        if is_in_alarm(val, reading):
            if not in_period:
                in_period = True
                start_ts = pt.get("ts", "")
                level = "alarm"
            if is_in_trip(val, reading):
                level = "trip"
        else:
            if in_period:
                periods.append({"start": start_ts, "end": pt.get("ts", ""), "level": level})
                in_period = False
    if in_period:
        periods.append({"start": start_ts, "end": history[-1].get("ts", "") if history else "", "level": level})
    return periods


def _trend(history: list[dict]) -> tuple[str, float]:
    """Trend direction and % change: the last recentReadingCount readings against the ones before them. The change
    is divided by the size of the older average, so a rising value reads as rising when the average is negative."""
    if len(history) <= recentReadingCount:
        return "stable", 0.0
    recent = [p["value"] for p in history[-recentReadingCount:]]
    older  = [p["value"] for p in history[-2 * recentReadingCount:-recentReadingCount]]
    avg_r  = sum(recent) / len(recent)
    avg_o  = sum(older)  / len(older)
    if avg_o == 0:
        return "stable", 0.0
    pct = round((avg_r - avg_o) / abs(avg_o) * 100, 1)
    if pct > trendThresholdPct:  return "rising",  pct
    if pct < -trendThresholdPct: return "falling", pct
    return "stable", pct


def _stats(history: list[dict]) -> dict:
    """Max and min over every stored reading, and the average of the last recentReadingCount readings."""
    vals = [p["value"] for p in history]
    if not vals:
        return {}
    recent = vals[-recentReadingCount:]
    return {
        "current":     vals[-1],
        "max":         round(max(vals), 2),
        "min":         round(min(vals), 2),
        "avg_recent":  round(sum(recent) / len(recent), 2),
        "recent_count": len(recent),
        "data_points": len(vals),
    }


# ── Helper: enrich sensor entry ───────────────────────────────────────────────

async def _build_sensor_detail(
    equipment_id: str,
    sensor_key: str,
    reading: dict,
    stored_history: list[dict] | None,
) -> dict[str, Any]:
    val     = reading.get("value", 0)
    status  = sensor_status(val, reading)
    history = stored_history or []
    trend_dir, trend_pct = _trend(history)
    anomaly_periods = _anomaly_periods(history, reading)
    # None, not [], when there are too few stored points to fit: "not evaluated" is not "no anomalies".
    ml_anomalies = detect_series_anomalies(history)

    return {
        "key":            sensor_key,
        "label":          sensorLabel(sensor_key),
        "current":        val,
        "unit":           reading.get("unit", ""),
        "normal":         reading.get("normal"),
        "alarm":          reading.get("alarm"),
        "trip":           reading.get("trip"),
        "status":         status,
        "trend":          trend_dir,
        "trend_pct":      trend_pct,
        "history":        history,
        "anomaly_periods": anomaly_periods,
        "ml_anomalies":   ml_anomalies,
        "stats":          _stats(history),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{equipment_id}")
async def get_equipment_sensors(equipment_id: str):
    """
    Return the full sensor dashboard for one equipment:
    current readings, stored history, anomaly periods, maintenance, and incidents.
    """
    eq = await db.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")

    readings: dict = eq.get("current_readings") or {}
    stored   = {key: numericPoints(hist or []) for key, hist in (await db.get_sensor_history(equipment_id)).items()}

    # Merge SensorHistory keys not present in current_readings (e.g. from document upload)
    for key, hist in stored.items():
        if key not in readings and hist:
            last = hist[-1]
            readings[key] = {"value": last.get("value"), "unit": last.get("unit", "")}

    sensors = {}
    for key, r in readings.items():
        if not isinstance(r, dict) or r.get("value") is None:
            continue
        hist = stored.get(key) or []
        sensors[key] = await _build_sensor_detail(equipment_id, key, r, hist if hist else None)

    # Related records
    maintenance = await db.get_maintenance_records(equipment_id)
    incidents   = await db.get_equipment_incidents(equipment_id)

    return {
        "equipment_id":   equipment_id,
        "equipment_name": eq.get("name"),
        "equipment_type": eq.get("type"),
        "location":       eq.get("location"),
        "health_score":   eq.get("health_score"),
        "sensors":        sensors,
        "maintenance_records": sorted(
            [{"id": m.get("id"), "date": m.get("date") or m.get("scheduled_date"),
              "type": m.get("type"), "status": m.get("status"),
              "description": m.get("description"), "technician": m.get("technician"),
              "findings": m.get("findings")} for m in maintenance],
            key=lambda x: x["date"] or "", reverse=True,
        )[:10],
        "incidents": sorted(
            [{"id": i.get("id"), "date": i.get("date"), "title": i.get("title"),
              "severity": i.get("severity"), "symptom": i.get("symptom"),
              "root_cause": i.get("root_cause")} for i in incidents],
            key=lambda x: x["date"] or "", reverse=True,
        )[:8],
    }


# ── Live telemetry ingress ────────────────────────────────────────────────────

# Sensors whose reading cannot be below zero. Pressure and flow are left out on purpose: gauge
# pressure is negative under vacuum, and a flow meter reads negative when the flow reverses.
nonNegativeSensorWords = ("vibration", "level", "speed", "rpm")

class LiveReadings(BaseModel):
    readings: dict[str, float]

    @field_validator("readings")
    @classmethod
    def _non_empty(cls, readings: dict[str, float]) -> dict[str, float]:
        if not readings:
            raise ValueError("readings must not be empty")
        return readings


@router.post("/{equipment_id}/readings")
async def ingest_live_readings(
    equipment_id: str,
    body: LiveReadings,
    user: m.UserProfile = Depends(require_roles(*FIELD_ROLES)),
):
    """Write live sensor values into equipment.current_readings and append each to its sensor's stored history.

    The only writer of current_readings, and therefore the only input the
    threshold monitor acts on (see the Telemetry Decoupling Contract in
    threshold_monitor.py). Only sensors already configured for the equipment
    are accepted, so a caller cannot invent a sensor or change its thresholds.
    """
    non_finite = sorted(key for key, value in body.readings.items() if not math.isfinite(value))
    if non_finite:
        # Checked here, not in the model: FastAPI echoes a failing input into its 422 body, and a NaN
        # in that body cannot be JSON-encoded, which would turn this rejection into a 500.
        raise HTTPException(status_code=422, detail=f"readings must be finite numbers: {', '.join(non_finite)}")
    negative_magnitude = sorted(
        key for key, value in body.readings.items()
        if value < 0 and any(word in key.lower() for word in nonNegativeSensorWords)
    )
    if negative_magnitude:
        raise HTTPException(
            status_code=422,
            detail=f"readings must not be negative for magnitude sensors: {', '.join(negative_magnitude)}",
        )
    eq = await db.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
    configured = set(eq.get("current_readings") or {})
    unknown = sorted(set(body.readings) - configured)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Sensors not configured on {equipment_id}: {', '.join(unknown)}",
        )
    readAt = datetime.now(timezone.utc).replace(tzinfo=None)
    written = await recordLiveReadings(equipment_id, body.readings, readAt)
    await audit_record(
        "update", "sensor", equipment_id,
        equipment_id=equipment_id, actor=user.name, actor_type="user",
        changes={"readings": body.readings}, notes="Live telemetry ingress",
    )
    return {"equipment_id": equipment_id, "updated": written}
