"""
AI Operations Brain — Autonomous Threshold Monitor
Phase 8 of the IndustrialGPT vision: automatic work-order generation when
sensor readings exceed alarm thresholds.

Run as an asyncio background task started from main.py lifespan.
Checks all equipment every POLL_INTERVAL_SECONDS. If any sensor exceeds its
alarm threshold and no open work order already exists for that equipment,
it automatically creates a corrective work order.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from app.services import db_service as db

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60   # check every 60 seconds

# Track auto-created WO IDs to avoid duplicate WOs within the same run
_auto_created: dict[str, str] = {}   # equipment_id → work_order_id


async def _auto_create_work_order(eq: dict[str, Any], anomalies: list[dict[str, Any]]) -> None:
    """Create an auto-generated corrective work order for a threshold breach."""
    eq_id = eq["id"]

    # Build description from anomalies
    anomaly_summary = "; ".join(
        f"{a['sensor']} {a['value']}{a['unit']} (alarm {a['alarm']})"
        for a in anomalies
    )
    description = (
        f"AUTO-GENERATED: Sensor threshold exceeded on {eq_id} ({eq.get('name', '')}). "
        f"Anomalies detected: {anomaly_summary}. Immediate inspection required."
    )

    # Determine urgency
    trip_breach = any(
        a.get("value") is not None and a.get("trip") is not None and a["value"] >= a["trip"]
        for a in anomalies
    )
    wo_type = "Emergency" if trip_breach else "Corrective"

    # Build safety precautions based on equipment type
    equip_type = (eq.get("type") or "").lower()
    safety: list[str] = ["Review active permits before starting work", "Ensure LOTO is in place"]
    if "pump" in equip_type or "compressor" in equip_type:
        safety.append("Isolate suction and discharge valves before opening")
        safety.append("Verify gas-free atmosphere if handling flammable fluids")

    steps = [
        {
            "step": 1, "phase": "Preparation",
            "title": "Notify supervisor and issue PTW",
            "description": "Alert shift supervisor immediately. Issue PTW Class C (Machinery). Document readings.",
            "safety_note": "Do not start work without valid permit.", "expected_duration_minutes": 15,
        },
        {
            "step": 2, "phase": "Isolation",
            "title": "Isolate and LOTO",
            "description": f"Shut down {eq_id} safely per SOP. Apply LOTO on all energy sources.",
            "safety_note": "Verify zero energy state before proceeding.", "expected_duration_minutes": 20,
        },
        {
            "step": 3, "phase": "Execution",
            "title": "Inspect and diagnose",
            "description": f"Physical inspection of reported anomaly: {anomaly_summary}. Collect measurements.",
            "safety_note": None, "expected_duration_minutes": 60,
        },
        {
            "step": 4, "phase": "Verification",
            "title": "Verify and document findings",
            "description": "Record all findings in CMMS. Determine if further repair is needed.",
            "safety_note": None, "expected_duration_minutes": 20,
        },
        {
            "step": 5, "phase": "Restart",
            "title": "Controlled restart",
            "description": "Remove LOTO, restart equipment per startup procedure. Monitor for 30 minutes.",
            "safety_note": "Verify all personnel clear before re-energizing.", "expected_duration_minutes": 30,
        },
    ]

    wo_data = {
        "id": f"AUTO-WO-{uuid.uuid4().hex[:8].upper()}",
        "equipment_id": eq_id,
        "query_text": description,
        "risk_level": "Critical" if trip_breach else "High",
        "wo_type": wo_type,
        "description": description,
        "estimated_duration_hours": 3.0,
        "required_technicians": 2,
        "steps": steps,
        "spare_parts": [],
        "safety_precautions": safety,
        "required_permits": ["PTW Class C — Machinery"],
        "status": "Open",
        "auto_generated": True,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        saved_id = await db.create_work_order(wo_data)
        _auto_created[eq_id] = saved_id
        logger.info(
            "AUTO-WO created for %s (%s) → %s | anomalies: %s",
            eq_id, wo_type, saved_id, anomaly_summary,
        )
    except Exception as exc:
        logger.error("Failed to auto-create WO for %s: %s", eq_id, exc)


async def _has_open_work_order(equipment_id: str) -> bool:
    """Return True if the equipment already has an open work order."""
    try:
        wos = await db.get_work_orders(equipment_id=equipment_id)
        return any(wo.get("status") in ("Open", "In Progress") for wo in wos)
    except Exception:
        return False


async def _check_thresholds() -> None:
    """One scan pass: check all equipment sensors against thresholds."""
    try:
        all_eq = await db.get_all_equipment_list()
    except Exception as exc:
        logger.warning("Threshold monitor: could not fetch equipment: %s", exc)
        return

    for eq in all_eq:
        if eq.get("_discovered"):
            continue
        readings: dict = eq.get("current_readings") or {}
        anomalies: list[dict] = []

        for sensor_name, reading in readings.items():
            if not isinstance(reading, dict):
                continue
            val = reading.get("value")
            alarm = reading.get("alarm")
            trip = reading.get("trip")

            if val is None:
                continue
            if alarm is not None and val > alarm:
                anomalies.append({
                    "sensor": sensor_name,
                    "value": val,
                    "unit": reading.get("unit", ""),
                    "alarm": alarm,
                    "trip": trip,
                })

        if not anomalies:
            # Equipment is normal — clear auto-created tracking so re-alarm creates new WO
            _auto_created.pop(eq["id"], None)
            continue

        # Already auto-created a WO this cycle?
        if eq["id"] in _auto_created:
            continue

        # Avoid duplicate if WO already open from manual creation
        if await _has_open_work_order(eq["id"]):
            continue

        await _auto_create_work_order(eq, anomalies)


async def run_threshold_monitor() -> None:
    """Entry point: run the threshold monitor loop indefinitely."""
    logger.info("Threshold monitor started (interval: %ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _check_thresholds()
        except Exception as exc:
            logger.error("Threshold monitor error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
