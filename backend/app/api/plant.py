"""
AI Operations Brain — Plant Digital Twin API

The plant hierarchy is built ENTIRELY from the database:
  • Projects  (from the `projects` table)   → top-level plant name / site
  • Plants    (from the `plants`  table)     → "areas" in the digital twin
  • Equipment (from the `equipment` table)  → leaf nodes

Assignment of equipment to plants:
  1. If a Plant record has `equipment_ids`, those IDs are used directly.
  2. Otherwise equipment is matched to a plant by location-string keywords
     derived from the plant's name, code, and area fields.
  3. Equipment that matches no plant goes into an "Unassigned" bucket
     (only shown if it has real type/status data).

If no Plants exist in the DB the endpoint gracefully returns a single
plant derived from the unique equipment locations (legacy fallback).

Endpoints
─────────
GET /api/v1/plant/tree    — Full plant hierarchy (projects → plants → equipment)
GET /api/v1/plant/areas   — Area-level summary (no equipment detail)
GET /api/v1/plant/status  — Plant-wide KPI snapshot
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services import db_service as db

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Area icon heuristic ───────────────────────────────────────────────────────

_ICON_KEYWORDS: list[tuple[str, str]] = [
    (["cdu", "distill", "crude", "column", "fractionat"], "factory"),
    (["vdu", "vacuum"],                                    "factory"),
    (["pump", "compressor", "rotating", "motor"],          "cog"),
    (["util", "cooling", "steam", "boiler", "power"],      "zap"),
    (["tank", "storage", "farm", "vessel", "drum"],        "database"),
    (["electric", "instrument", "control", "panel"],       "zap"),
]

def _icon_for(name: str, area: str | None) -> str:
    combined = (name + " " + (area or "")).lower()
    for keywords, icon in _ICON_KEYWORDS:
        if any(k in combined for k in keywords):
            return icon
    return "factory"


# ── Equipment helpers ──────────────────────────────────────────────────────────

_TYPE_CATEGORY: dict[str, str] = {
    "pump": "rotating", "compressor": "rotating", "motor": "rotating",
    "turbine": "rotating", "heat exchanger": "static", "vessel": "static",
    "drum": "static", "tank": "static", "column": "static", "furnace": "fired",
    "heater": "fired", "valve": "instrument", "filter": "static",
}

def _categorize(eq_type: str) -> str:
    t = (eq_type or "").lower()
    for key, cat in _TYPE_CATEGORY.items():
        if key in t:
            return cat
    return "other"

def _status_color(eq: dict) -> str:
    hs = eq.get("health_score")
    status = (eq.get("status") or "").lower()
    if "alarm" in status or "alert" in status:
        return "red"
    if "shutdown" in status or "offline" in status or "stopped" in status:
        return "gray"
    if hs is None:
        return "gray"
    return "green" if hs >= 85 else "amber" if hs >= 65 else "orange" if hs >= 45 else "red"

def _alerts(eq: dict) -> list[str]:
    alerts: list[str] = []
    for sname, reading in (eq.get("current_readings") or {}).items():
        if isinstance(reading, dict):
            val, alarm = reading.get("value"), reading.get("alarm")
            if val is not None and alarm is not None and val > alarm:
                alerts.append(f"{sname} {val}{reading.get('unit', '')}")
    if eq.get("maintenance_due_days") is not None and eq["maintenance_due_days"] <= 0:
        alerts.append("Maintenance overdue")
    return alerts

def _area_health(equip_list: list[dict]) -> int | None:
    scores = [e["health_score"] for e in equip_list if e.get("health_score") is not None]
    return round(sum(scores) / len(scores)) if scores else None

def _area_status(equip_list: list[dict]) -> str:
    colors = [e["status_color"] for e in equip_list]
    if "red" in colors:   return "alarm"
    if "orange" in colors: return "degraded"
    if "amber" in colors:  return "warning"
    return "offline" if colors and all(c == "gray" for c in colors) else "normal"

def _eq_node(eq: dict) -> dict:
    return {
        "id": eq["id"],
        "name": eq.get("name", eq["id"]),
        "type": eq.get("type", "Unknown"),
        "category": _categorize(eq.get("type", "")),
        "status": eq.get("status", "Unknown"),
        "status_color": _status_color(eq),
        "health_score": eq.get("health_score"),
        "failure_probability": eq.get("failure_probability"),
        "compliance_score": eq.get("compliance_score"),
        "criticality": eq.get("criticality", "Unknown"),
        "location": eq.get("location", ""),
        "manufacturer": eq.get("manufacturer"),
        "alerts": _alerts(eq),
        "maintenance_due_days": eq.get("maintenance_due_days"),
    }


# ── Dynamic plant keywords ─────────────────────────────────────────────────────

def _keywords_for_plant(plant: dict) -> list[str]:
    """Derive fuzzy-match keywords from plant DB record."""
    kws: list[str] = []
    for field in ["name", "code", "area", "location", "description"]:
        v = (plant.get(field) or "").strip().lower()
        if v:
            kws.append(v)
            # Also add the individual words (>= 3 chars)
            kws.extend(w for w in v.split() if len(w) >= 3)
    return list(set(kws))

def _match_plant(eq_loc: str, keywords: list[str]) -> bool:
    loc = eq_loc.lower()
    return any(k in loc for k in keywords)


# ── Load plants & projects from DB ────────────────────────────────────────────

async def _load_plants_and_projects() -> tuple[list[dict], list[dict]]:
    async with AsyncSessionLocal() as session:
        plant_rows   = (await session.execute(select(m.Plant).order_by(m.Plant.name))).scalars().all()
        project_rows = (await session.execute(select(m.Project).order_by(m.Project.name))).scalars().all()

    plants = [
        {
            "id":            p.id,
            "code":          p.code,
            "name":          p.name,
            "project_id":    p.project_id,
            "type":          p.type,
            "location":      p.location,
            "area":          p.area,
            "description":   p.description,
            "equipment_ids": p.equipment_ids or [],
            "status":        p.status,
        }
        for p in plant_rows
    ]
    projects = [
        {
            "id":       p.id,
            "code":     p.code,
            "name":     p.name,
            "location": p.location,
            "status":   p.status,
            "type":     p.type,
        }
        for p in project_rows
    ]
    return plants, projects


# ── Fallback: derive virtual areas from equipment locations ───────────────────

def _virtual_areas_from_equipment(all_eq: list[dict]) -> list[dict]:
    """When no Plant records exist, group equipment by unique location strings."""
    from collections import defaultdict
    buckets: dict[str, list] = defaultdict(list)
    for eq in all_eq:
        loc = (eq.get("location") or "Unknown Location").strip()
        buckets[loc].append(eq)

    areas = []
    for idx, (loc, equip) in enumerate(sorted(buckets.items())):
        areas.append({
            "id":           f"AREA-AUTO-{idx:03d}",
            "code":         f"A{idx+1:03d}",
            "name":         loc,
            "full_name":    loc,
            "type":         "Process Unit",
            "location":     loc,
            "area":         None,
            "description":  None,
            "equipment_ids": [],
            "_keywords":    [loc.lower()] + [w for w in loc.lower().split() if len(w) >= 3],
            "icon":         _icon_for(loc, None),
            "status":       "Operational",
        })
    return areas


# ── Core tree builder ─────────────────────────────────────────────────────────

async def _build_tree() -> dict:
    all_eq_raw = await db.get_all_equipment_list()
    # Include all equipment that has an ID — even "Unknown Equipment" discovered items
    active_eq  = [e for e in all_eq_raw if e.get("id")]

    plants, projects = await _load_plants_and_projects()

    # If no plants in DB → derive from equipment locations
    use_virtual = len(plants) == 0
    if use_virtual:
        plants = _virtual_areas_from_equipment(active_eq)

    # Enrich each plant with match keywords
    for pl in plants:
        if "_keywords" not in pl:
            pl["_keywords"] = _keywords_for_plant(pl)

    # Assign equipment to plants
    # Priority: explicit equipment_ids → then location fuzzy match
    eq_by_id = {e["id"]: e for e in active_eq}
    plant_eq: dict[str, list] = {pl["id"]: [] for pl in plants}
    assigned_ids: set[str] = set()

    # Pass 1: explicit equipment_ids
    for pl in plants:
        for eid in pl.get("equipment_ids") or []:
            if eid in eq_by_id and eid not in assigned_ids:
                plant_eq[pl["id"]].append(_eq_node(eq_by_id[eid]))
                assigned_ids.add(eid)

    # Pass 2: location keyword matching for unassigned equipment
    for eq in active_eq:
        if eq["id"] in assigned_ids:
            continue
        loc = eq.get("location") or ""
        matched = False
        for pl in plants:
            if _match_plant(loc, pl["_keywords"]):
                plant_eq[pl["id"]].append(_eq_node(eq))
                assigned_ids.add(eq["id"])
                matched = True
                break
        if not matched and plants:
            # Put unmatched into the first plant (catch-all)
            plant_eq[plants[0]["id"]].append(_eq_node(eq))
            assigned_ids.add(eq["id"])

    # Build plant-level name / site from projects
    if projects:
        # Use the first active project as the plant name
        active_proj = next((p for p in projects if p["status"] == "Active"), projects[0])
        plant_name = active_proj["name"]
        plant_site = active_proj.get("location") or "Site"
    else:
        plant_name = "Plant Digital Twin"
        plant_site  = "Operations Site"

    # Build areas output
    areas_out  = []
    total_alerts = 0
    health_all: list[int] = []

    for pl in plants:
        eq_in_area  = plant_eq[pl["id"]]
        area_health = _area_health(eq_in_area)
        area_status = _area_status(eq_in_area) if eq_in_area else "empty"
        n_alerts    = sum(1 for e in eq_in_area if e["alerts"])
        total_alerts += n_alerts
        if area_health is not None:
            health_all.append(area_health)

        areas_out.append({
            "id":             pl["id"],
            "name":           pl["name"],
            "full_name":      pl.get("description") or f"{pl['name']} ({pl.get('type', 'Process Unit')})",
            "code":           pl.get("code", ""),
            "type":           pl.get("type", "Process Unit"),
            "location":       pl.get("location", ""),
            "status":         area_status,
            "plant_status":   pl.get("status", "Operational"),
            "icon":           pl.get("icon") or _icon_for(pl["name"], pl.get("area")),
            "equipment_count": len(eq_in_area),
            "health":         area_health,
            "alert_count":    n_alerts,
            "equipment":      eq_in_area,
        })

    plant_health = round(sum(health_all) / len(health_all)) if health_all else None
    total_eq     = len(active_eq)

    return {
        "id":              "PLANT-MAIN",
        "name":            plant_name,
        "site":            plant_site,
        "equipment_count": total_eq,
        "health":          plant_health,
        "status":          "alarm" if total_alerts > 0 else "normal",
        "alert_count":     total_alerts,
        "areas":           areas_out,
        # Extra context
        "projects":        [{"id": p["id"], "name": p["name"]} for p in projects],
        "plant_count":     len(plants),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/tree")
async def get_plant_tree():
    """Full plant hierarchy — Plants and Equipment from DB."""
    return await _build_tree()


@router.get("/areas")
async def get_areas_summary():
    """Area-level summary without equipment details."""
    tree = await _build_tree()
    return {
        "plant_id":   tree["id"],
        "plant_name": tree["name"],
        "health":     tree["health"],
        "status":     tree["status"],
        "alert_count": tree["alert_count"],
        "areas": [
            {k: v for k, v in area.items() if k != "equipment"}
            for area in tree["areas"]
        ],
    }


@router.get("/status")
async def get_plant_status():
    """Plant-wide KPI snapshot for the dashboard header."""
    all_eq = await db.get_all_equipment_list()
    active = [e for e in all_eq if e.get("id")]

    health_scores = [e["health_score"] for e in active if e.get("health_score") is not None]
    in_alarm = sum(
        1 for e in active
        if any(
            isinstance(r, dict)
            and r.get("value") is not None
            and r.get("alarm") is not None
            and r["value"] > r["alarm"]
            for r in (e.get("current_readings") or {}).values()
        )
    )
    avg_health = round(sum(health_scores) / len(health_scores)) if health_scores else None
    _, projects = await _load_plants_and_projects()

    return {
        "plant_name":      projects[0]["name"] if projects else "Plant",
        "equipment_count": len(active),
        "in_alarm":        in_alarm,
        "avg_health":      avg_health,
        "status":          "alarm" if in_alarm > 0 else "normal",
    }
