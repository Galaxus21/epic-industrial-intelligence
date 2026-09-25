"""
AI Operations Brain — Equipment API
REST endpoints for equipment list, detail, brain, timeline, sensor history,
and manual / AI-driven equipment registration.
"""
import math
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from app.core.auth import require_roles
from app.core.roles import APPROVER_ROLES
from app.db import models as m
from app.services import db_service as db
from app.services.alarmEvaluation import alarm_direction, readingStatuses

router = APIRouter()

# Sensor keys follow the seeded ones ("vibration_de"), so labels and the readings-ingress checks work on them.
SENSOR_KEY_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
THRESHOLD_FIELDS = {"normal", "alarm", "trip"}


class SensorConfig(BaseModel):
    unit: str = ""
    normal: float | None = None
    alarm: float | None = None
    trip: float | None = None
    alarm_direction: Literal["low", "high"] | None = None


class EquipmentCreate(BaseModel):
    id: str
    name: str
    type: str = "Unknown Equipment"
    location: str = ""
    criticality: str = "Unknown"
    manufacturer: str = ""
    model: str = ""
    sensors: dict[Annotated[str, StringConstraints(pattern=SENSOR_KEY_PATTERN)], SensorConfig] = {}


@router.get("")
async def list_equipment():
    """Return all equipment from the database, each with the alarm status of every reading."""
    return [_withReadingStatus(eq) for eq in await db.get_all_equipment_list()]


@router.post("")
async def register_equipment(
    body: EquipmentCreate,
    user: m.UserProfile = Depends(require_roles(*APPROVER_ROLES)),
):
    """Manually register a new piece of equipment, optionally with its sensors (unit and alarm limits).

    The readings ingress accepts only sensors declared here, so equipment registered without sensors cannot
    receive live readings. A declared sensor has no value until its first reading arrives."""
    problems = _sensorConfigProblems(body.sensors)
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems))
    existing = await db.get_equipment(body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"{body.id} already registered")
    record: dict[str, Any] = {
        "id": body.id, "name": body.name, "type": body.type,
        "location": body.location or "Pending",
        "criticality": body.criticality,
        "manufacturer": body.manufacturer or None,
        "model": body.model or None,
        "health_score": None, "failure_probability": None,
        "compliance_score": None, "maintenance_due_days": None,
        "status": "Registered",
        "discovered": False, "manually_registered": True,
        "current_readings": {key: _unreadSensor(config) for key, config in body.sensors.items()},
    }
    await db.upsert_equipment(record)
    await db.upsert_graph_node({"id": body.id, "name": f"{body.id}\n{body.type}", "type": "equipment", "val": 16})
    return record


@router.get("/{equipment_id}")
async def get_equipment(equipment_id: str):
    eq = await db.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
    return _withReadingStatus(eq)


def _withReadingStatus(eq: dict[str, Any]) -> dict[str, Any]:
    return {**eq, "reading_status": readingStatuses(eq.get("current_readings"))}


@router.get("/{equipment_id}/brain")
async def get_equipment_brain(equipment_id: str):
    """Return the full knowledge graph context for one equipment."""
    brain = await db.get_equipment_brain(equipment_id)
    if not brain:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
    return brain


@router.get("/{equipment_id}/timeline")
async def get_equipment_timeline(equipment_id: str):
    """Return a chronological timeline of all events for one equipment."""
    eq = await db.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")

    events = []

    # Installation
    if eq.get("installed_date"):
        events.append({
            "date": eq["installed_date"],
            "type": "installation",
            "title": "Equipment Installed",
            "description": f"Installed at {eq.get('location')} — {eq.get('manufacturer')} {eq.get('model', '')}",
            "severity": "info",
        })

    # Incidents
    for inc in await db.get_equipment_incidents(equipment_id):
        events.append({
            "date": inc["date"],
            "type": "incident",
            "title": inc["title"],
            "description": inc.get("symptom", ""),
            "severity": inc.get("severity", "medium").lower(),
            "detail": {
                "root_cause": inc.get("root_cause"),
                "action": inc.get("action_taken"),
                "downtime_hours": inc.get("downtime_hours"),
                "cost_usd": inc.get("cost_usd"),
                "technician": inc.get("technician"),
            },
        })

    # Maintenance
    for mr in await db.get_maintenance_records(equipment_id):
        events.append({
            "date": mr.get("date") or mr.get("scheduled_date"),
            "type": "maintenance",
            "title": mr["description"],
            "description": mr.get("findings", "No findings recorded"),
            "severity": "warning" if mr["status"] == "Overdue" else "success",
            "detail": {
                "type": mr["type"],
                "status": mr["status"],
                "vibration": mr.get("vibration_de"),
                "technician": mr.get("technician"),
            },
        })

    events.sort(key=lambda e: e["date"] or "")
    return {"equipment_id": equipment_id, "events": events}


@router.get("/{equipment_id}/sensors")
async def get_sensor_history(equipment_id: str):
    """Return recent sensor readings for charts."""
    history = await db.get_sensor_history(equipment_id)
    return {"equipment_id": equipment_id, "sensors": history}


def _unreadSensor(config: SensorConfig) -> dict[str, Any]:
    return {"value": None, **config.model_dump(exclude_none=True)}


def _sensorConfigProblems(sensors: dict[str, SensorConfig]) -> list[str]:
    """Checked here, not in the model: FastAPI echoes a failing input into its 422 body, and a NaN there cannot be
    JSON-encoded, which would turn the rejection into a 500 (the same reason as the readings ingress)."""
    problems: list[str] = []
    for key, config in sorted(sensors.items()):
        limits = config.model_dump(include=THRESHOLD_FIELDS, exclude_none=True)
        if not all(math.isfinite(limit) for limit in limits.values()):
            problems.append(f"{key}: normal, alarm and trip must be finite numbers")
        elif _tripInsideAlarm(config):
            problems.append(f"{key}: trip must be at or beyond alarm in the alarm direction")
    return problems


def _tripInsideAlarm(config: SensorConfig) -> bool:
    """Trip is the more severe limit and is evaluated first (alarmEvaluation.sensor_status), so it cannot sit on the
    safe side of the alarm."""
    if config.alarm is None or config.trip is None:
        return False
    if alarm_direction(config.model_dump()) == "low":
        return config.trip > config.alarm
    return config.trip < config.alarm
