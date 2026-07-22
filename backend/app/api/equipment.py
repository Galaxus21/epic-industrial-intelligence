"""
AI Operations Brain — Equipment API
REST endpoints for equipment list, detail, brain, timeline, sensor history,
and manual / AI-driven equipment registration.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
from app.services import db_service as db

router = APIRouter()


class EquipmentCreate(BaseModel):
    id: str
    name: str
    type: str = "Unknown Equipment"
    location: str = ""
    criticality: str = "Unknown"
    manufacturer: str = ""
    model: str = ""


@router.get("")
async def list_equipment():
    """Return all equipment from the database."""
    return await db.get_all_equipment_list()


@router.get("/discovered")
async def list_discovered():
    """Return only equipment auto-discovered from document uploads."""
    return await db.get_discovered_equipment()


@router.post("")
async def register_equipment(body: EquipmentCreate):
    """Manually register a new piece of equipment."""
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
    }
    await db.upsert_equipment(record)
    await db.upsert_graph_node({"id": body.id, "name": f"{body.id}\n{body.type}", "type": "equipment", "val": 16})
    return record


@router.get("/{equipment_id}")
async def get_equipment(equipment_id: str):
    eq = await db.get_equipment(equipment_id)
    if eq is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
    return eq


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


@router.get("/{equipment_id}/subgraph")
async def get_equipment_subgraph(equipment_id: str):
    """Return knowledge graph nodes/links centred on this equipment."""
    return await db.get_equipment_subgraph(equipment_id)
