"""
AI Operations Brain — Autonomous Threshold Monitor
Automatic work-order generation when sensor readings exceed alarm thresholds.

Telemetry Decoupling Contract:
`equipment.current_readings` is reserved strictly for authenticated live telemetry ingress
(POST /api/v1/sensors/{equipment_id}/readings).
Model-parsed or document-extracted values written to `SensorHistory` (source="document_extraction")
never mutate `equipment.current_readings` and therefore never trigger automated work orders here.

Run as an asyncio background task started from main.py lifespan.
Checks all equipment every POLL_INTERVAL_SECONDS. If any sensor exceeds its
alarm threshold and no open work order already exists for that equipment, it
automatically creates a corrective work order (status "open") for the crew to work.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select

from app.db import models as m
from app.db.database import AsyncSessionLocal
from app.services import db_service as db
from app.services.audit import record as audit_record
from app.services.alarmEvaluation import alarm_direction, is_in_alarm, is_in_trip

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60
AUTO_WORK_ORDER_PREFIX = "AUTO-WO-"
MONITOR_ACTOR = "threshold_monitor"
MINUTES_PER_HOUR = 60

_OPEN_STATUSES = frozenset({"open", "in_progress"})


async def _get_all_open_wo_equipment_ids() -> set[str]:
    """Single SQL query to get all equipment IDs that currently have an open work order."""
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(m.SavedWorkOrder.equipment_id)
            .where(m.SavedWorkOrder.status.in_(_OPEN_STATUSES))
            .distinct()
        )
        return {eq_id for eq_id in result.scalars().all() if eq_id}


def _anomaly_summary(anomalies: list[dict[str, Any]]) -> str:
    return "; ".join(
        f"{a['sensor']} {a['value']}{a['unit']} (alarm {a['alarm']})"
        for a in anomalies
    )


def _procedure_steps(eq_id: str, anomaly_summary: str) -> list[dict[str, Any]]:
    return [
        {"step": 1, "phase": "Preparation", "title": "Notify supervisor and document readings",
         "description": "Alert the shift supervisor immediately. Document the alarming readings.",
         "safety_note": None, "expected_duration_minutes": 15},
        {"step": 2, "phase": "Isolation", "title": "Isolate and LOTO",
         "description": f"Shut down {eq_id} safely per SOP. Apply LOTO on all energy sources.",
         "safety_note": "Verify zero energy before opening any equipment.", "expected_duration_minutes": 20},
        {"step": 3, "phase": "Execution", "title": "Inspect and diagnose",
         "description": f"Physical inspection of reported anomaly: {anomaly_summary}. Collect measurements.",
         "safety_note": None, "expected_duration_minutes": 60},
        {"step": 4, "phase": "Verification", "title": "Verify and document findings",
         "description": "Record all findings in CMMS. Determine if further repair is needed.",
         "safety_note": None, "expected_duration_minutes": 20},
        {"step": 5, "phase": "Restart", "title": "Controlled restart",
         "description": "Remove LOTO, restart equipment per startup procedure. Monitor for 30 minutes.",
         "safety_note": None, "expected_duration_minutes": 30},
    ]


def _safety_precautions(eq: dict[str, Any]) -> list[str]:
    precautions = ["Confirm work authorisation with the shift supervisor before starting work",
                   "Ensure LOTO is in place"]
    equip_type = (eq.get("type") or "").lower()
    if "pump" in equip_type or "compressor" in equip_type:
        precautions.append("Isolate suction and discharge valves before opening")
        precautions.append("Verify gas-free atmosphere if handling flammable fluids")
    return precautions


def _build_work_order(eq: dict[str, Any], anomalies: list[dict[str, Any]]) -> dict[str, Any]:
    eq_id = eq["id"]
    summary = _anomaly_summary(anomalies)
    trip_breach = any(a["tripped"] for a in anomalies)
    steps = _procedure_steps(eq_id, summary)
    total_minutes = sum(step["expected_duration_minutes"] for step in steps)
    return {
        "id": f"{AUTO_WORK_ORDER_PREFIX}{uuid.uuid4().hex[:8].upper()}",
        "equipment_id": eq_id,
        "query_text": f"Automatic threshold breach: {summary}",
        "risk_level": "Critical" if trip_breach else "High",
        "wo_type": "Emergency" if trip_breach else "Corrective",
        "description": (
            f"AUTO-GENERATED: Sensor threshold exceeded on {eq_id} ({eq.get('name', '')}). "
            f"Anomalies detected: {summary}. Immediate inspection required."
        ),
        "estimated_duration_hours": round(total_minutes / MINUTES_PER_HOUR, 2),
        "status": "open",
        "steps": steps,
        "safety_precautions": _safety_precautions(eq),
    }


async def _auto_create_work_order(eq: dict[str, Any], anomalies: list[dict[str, Any]]) -> None:
    """Create a work order for a threshold breach and record who created it."""
    eq_id = eq["id"]
    wo_data = _build_work_order(eq, anomalies)
    try:
        wo_id = await db.create_work_order(wo_data)
    except Exception as exc:
        logger.error("Failed to auto-create work order for %s: %s", eq_id, exc)
        return
    logger.info(
        "Auto work order created for %s (%s, %s) → %s | %s",
        eq_id, wo_data["wo_type"], wo_data["risk_level"], wo_id, wo_data["query_text"],
    )
    await audit_record(
        "create", "work_order", wo_id,
        equipment_id=eq_id, actor=MONITOR_ACTOR, actor_type="system",
        risk_level=wo_data["risk_level"], notes=wo_data["query_text"], critical=False,
    )


def _collect_anomalies(readings: dict) -> list[dict]:
    anomalies: list[dict] = []
    for sensor_name, reading in readings.items():
        if not isinstance(reading, dict):
            continue
        val = reading.get("value")
        alarm = reading.get("alarm")
        # Invariant: NaN compares False both ways and must never count as a breach (handled inside is_in_alarm).
        if not is_in_alarm(val, reading):
            continue
        anomalies.append({
            "sensor": sensor_name,
            "value": val,
            "unit": reading.get("unit", ""),
            "alarm": alarm,
            "trip": reading.get("trip"),
            "tripped": is_in_trip(val, reading),
            "alarm_direction": alarm_direction(reading),
        })
    return anomalies


async def _check_thresholds() -> None:
    """One scan pass: check all equipment sensors against thresholds."""
    try:
        all_eq = await db.get_all_equipment_list()
        open_wo_eq_ids = await _get_all_open_wo_equipment_ids()
    except Exception as exc:
        logger.warning("Threshold monitor: could not fetch data: %s", exc, exc_info=True)
        return

    for eq in all_eq:
        if eq.get("discovered"):
            continue
        anomalies = _collect_anomalies(eq.get("current_readings") or {})
        if not anomalies or eq["id"] in open_wo_eq_ids:
            continue

        await _auto_create_work_order(eq, anomalies)
        open_wo_eq_ids.add(eq["id"])


async def run_threshold_monitor() -> None:
    """Entry point: run the threshold monitor loop indefinitely."""
    logger.info("Threshold monitor started (interval: %ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _check_thresholds()
        except Exception as exc:
            logger.error("Threshold monitor error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
