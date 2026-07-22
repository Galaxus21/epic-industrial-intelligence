"""
AI Operations Brain — Sensors & Telemetry API
Dedicated sensor layer with 30-day history, anomaly detection,
and cross-referencing to maintenance records, incidents, and checklists.

Endpoints:
  GET /api/v1/sensors                         — all equipment sensor overview
  GET /api/v1/sensors/{equipment_id}          — full sensor dashboard for one equipment
  GET /api/v1/sensors/{equipment_id}/{sensor} — single sensor detail + history
"""
from __future__ import annotations

import math
import random
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from app.services import db_service as db

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Sensor status classification ──────────────────────────────────────────────

def _sensor_status(val: float, reading: dict) -> str:
    trip  = reading.get("trip")
    alarm = reading.get("alarm")
    normal = reading.get("normal", val)
    if trip  is not None and val >= trip:  return "trip"
    if alarm is not None and val > alarm:  return "alarm"
    if val > normal * 1.1:                 return "high"
    if val < normal * 0.9:                 return "low"
    return "normal"


def _sensor_status_color(status: str) -> str:
    return {"trip": "#ef4444", "alarm": "#f97316", "high": "#f59e0b",
            "low": "#60a5fa", "normal": "#10b981"}.get(status, "#6b7280")


# ── 30-day history generator ──────────────────────────────────────────────────

def _generate_history(
    current_value: float,
    reading: dict,
    days: int = 30,
    interval_hours: int = 4,
) -> list[dict[str, Any]]:
    """
    Synthesise a realistic 30-day sensor history that:
      - starts at a healthy baseline (normal * 0.9)
      - trends smoothly toward the current value
      - adds diurnal oscillation and gaussian noise
      - keeps last two points matching current to show the live anomaly
    """
    rng = random.Random(hash(str(current_value) + str(days)))

    normal = reading.get("normal", current_value)
    alarm  = reading.get("alarm")
    trip   = reading.get("trip")
    n_pts  = (days * 24) // interval_hours   # e.g. 30d × 6pt/day = 180

    # Baseline: start healthy then degrade toward current
    start = min(normal * 0.88, current_value * 0.75)
    if current_value < normal:          # sensor is improving (e.g. after maintenance)
        start = max(current_value * 1.15, normal * 1.05)

    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    points: list[dict] = []

    for i in range(n_pts):
        t = i / (n_pts - 1)           # 0 → 1

        # Piecewise trend: stable in first 60%, accelerating in last 40%
        if t < 0.6:
            trend_factor = t / 0.6 * 0.3    # slow rise 0→0.3
        else:
            trend_factor = 0.3 + ((t - 0.6) / 0.4) ** 1.8 * 0.7   # fast rise 0.3→1.0

        trend = start + (current_value - start) * trend_factor

        # Gaussian noise ±3% of normal
        noise = rng.gauss(0, normal * 0.025)

        # Diurnal: ±1% sinusoidal over 24h (thermal / load effects)
        hour_of_day = ((n_pts - i) * interval_hours) % 24
        diurnal = normal * 0.01 * math.sin(2 * math.pi * hour_of_day / 24)

        value = round(max(0.0, trend + noise + diurnal), 2)
        ts = now - timedelta(hours=(n_pts - 1 - i) * interval_hours)
        points.append({"ts": ts.strftime("%Y-%m-%dT%H:%M"), "value": value})

    # Force last point to match live reading
    points[-1]["value"] = current_value
    return points


def _anomaly_periods(history: list[dict], alarm: float | None, trip: float | None) -> list[dict]:
    """Find contiguous stretches where value ≥ alarm (or trip) threshold."""
    if not alarm:
        return []
    periods: list[dict] = []
    in_period = False
    start_ts = ""
    for pt in history:
        if pt["value"] > alarm:
            if not in_period:
                in_period = True
                start_ts = pt["ts"]
                level = "trip" if trip and pt["value"] >= trip else "alarm"
        else:
            if in_period:
                periods.append({"start": start_ts, "end": pt["ts"], "level": level})
                in_period = False
    if in_period:
        periods.append({"start": start_ts, "end": history[-1]["ts"], "level": level})
    return periods


def _trend(history: list[dict]) -> tuple[str, float]:
    """Calculate trend direction and % change over last 7 data points."""
    if len(history) < 8:
        return "stable", 0.0
    recent = [p["value"] for p in history[-7:]]
    older  = [p["value"] for p in history[-14:-7]]
    if not recent:
        return "stable", 0.0
    avg_r  = sum(recent) / len(recent)
    avg_o  = sum(older)  / len(older) if older else avg_r
    if avg_o == 0:
        return "stable", 0.0
    pct = round((avg_r - avg_o) / avg_o * 100, 1)
    if pct > 3:  return "rising",  pct
    if pct < -3: return "falling", pct
    return "stable", pct


def _stats(history: list[dict]) -> dict:
    vals = [p["value"] for p in history]
    if not vals:
        return {}
    last_7 = [p["value"] for p in history[-42:]]  # 42 pts = 7 days at 4h interval
    return {
        "current":   vals[-1],
        "max_30d":   round(max(vals), 2),
        "min_30d":   round(min(vals), 2),
        "avg_7d":    round(sum(last_7) / len(last_7), 2) if last_7 else vals[-1],
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
    status  = _sensor_status(val, reading)
    history = stored_history if (stored_history and len(stored_history) >= 30) \
              else _generate_history(val, reading)
    trend_dir, trend_pct = _trend(history)
    anomaly_periods = _anomaly_periods(history, reading.get("alarm"), reading.get("trip"))

    return {
        "key":            sensor_key,
        "label":          sensor_key.replace("_", " ").title().replace(" De", " DE").replace(" Nde", " NDE"),
        "current":        val,
        "unit":           reading.get("unit", ""),
        "normal":         reading.get("normal"),
        "alarm":          reading.get("alarm"),
        "trip":           reading.get("trip"),
        "status":         status,
        "status_color":   _sensor_status_color(status),
        "trend":          trend_dir,
        "trend_pct":      trend_pct,
        "history":        history,
        "anomaly_periods": anomaly_periods,
        "stats":          _stats(history),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_all_sensors():
    """Return a compact sensor status matrix across all equipment."""
    all_eq = await db.get_all_equipment_list()
    result = []
    for eq in all_eq:
        readings: dict = eq.get("current_readings") or {}
        if not readings:
            # Fall back to SensorHistory table for discovered equipment
            stored_hist = await db.get_sensor_history(eq["id"])
            if not stored_hist:
                continue
            # Reconstruct minimal current_readings from the latest stored reading per key
            for key, hist in stored_hist.items():
                if hist:
                    last = hist[-1]
                    readings[key] = {"value": last.get("value"), "unit": last.get("unit", "")}
            if not readings:
                continue
        sensors = []
        for key, r in readings.items():
            if not isinstance(r, dict):
                continue
            val = r.get("value")
            if val is None:
                continue
            status = _sensor_status(val, r)
            sensors.append({
                "key":    key,
                "label":  key.replace("_", " ").title().replace(" De", " DE").replace(" Nde", " NDE"),
                "value":  val,
                "unit":   r.get("unit", ""),
                "status": status,
                "status_color": _sensor_status_color(status),
                "alarm":  r.get("alarm"),
            })
        if sensors:
            result.append({
                "equipment_id":   eq["id"],
                "equipment_name": eq.get("name", eq["id"]),
                "equipment_type": eq.get("type", ""),
                "health_score":   eq.get("health_score"),
                "sensors":        sensors,
                "alarm_count":    sum(1 for s in sensors if s["status"] in ("alarm", "trip")),
            })
    result.sort(key=lambda x: -x["alarm_count"])
    return result


@router.get("/{equipment_id}")
async def get_equipment_sensors(equipment_id: str):
    """
    Return the full sensor dashboard for one equipment:
    current readings, 30-day history, anomaly periods, maintenance, incidents, checklists.
    """
    eq = await db.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")

    readings: dict = eq.get("current_readings") or {}
    stored   = await db.get_sensor_history(equipment_id)

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

    # Checklists from DB (only open)
    try:
        from app.db.database import AsyncSessionLocal
        from app.db import models as m
        from sqlalchemy import select
        async with AsyncSessionLocal() as s:
            cl_result = await s.execute(
                select(m.SavedChecklist)
                .where(m.SavedChecklist.equipment_id == equipment_id)
                .order_by(m.SavedChecklist.created_at.desc())
                .limit(5)
            )
            def _cl(row) -> dict:
                return {
                    "id": row.id,
                    "risk_level": row.risk_level,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "item_count": len(row.items or []),
                    "checked_count": sum(1 for it in (row.items or []) if it.get("checked")),
                }
            checklists = [_cl(r) for r in cl_result.scalars().all()]
    except Exception:
        checklists = []

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
        "checklists": checklists,
    }


@router.get("/{equipment_id}/{sensor_key}")
async def get_single_sensor(equipment_id: str, sensor_key: str):
    """Return detailed history + metadata for a single sensor."""
    eq = await db.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
    readings: dict = eq.get("current_readings") or {}
    reading = readings.get(sensor_key)
    if reading is None or not isinstance(reading, dict):
        raise HTTPException(status_code=404, detail=f"Sensor {sensor_key} not found on {equipment_id}")
    stored = (await db.get_sensor_history(equipment_id)).get(sensor_key) or []
    return await _build_sensor_detail(equipment_id, sensor_key, reading, stored if stored else None)
