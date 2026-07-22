"""
AI Operations Brain — Document Entity Mapper
==============================================
After LLM/regex entity extraction on an uploaded document, this service
maps every detected entity to its proper DB table and knowledge-graph node,
preserving all cross-entity relationships.

Entity types handled
--------------------
  project          → models.Project
  plant            → models.Plant
  equipment        → models.Equipment  (auto-register)
  incident         → models.IncidentReport
  work_order       → models.ManagedWorkOrder
  inspection       → models.QualityInspection
  safety_procedure → models.SafetyProcedure
  defect           → models.Incident  (severity-tagged maintenance incident)
  sensor           → models.SensorHistory  (append reading)

Relationships written to the graph
-----------------------------------
  Document   ──DOCUMENTED_IN──▶  Equipment
  Document   ──REFERENCES──▶     Incident | WorkOrder | Inspection | Procedure | Plant | Project
  Equipment  ──LOCATED_IN──▶     Plant
  Plant      ──BELONGS_TO──▶     Project
  Incident   ──INVOLVES──▶       Equipment
  WorkOrder  ──APPLIES_TO──▶     Equipment
  Inspection ──COVERS──▶         Equipment
  Procedure  ──GOVERNS──▶        Equipment
  Defect     ──DEFECT_ON──▶      Equipment
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from app.services import db_service as db

logger = logging.getLogger(__name__)

_TODAY = lambda: datetime.utcnow().strftime("%Y-%m-%d")   # noqa: E731


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ─────────────────────────────────────────────────────────────────────────────

async def map_and_store(
    doc_id: str,
    filename: str,
    entities: dict[str, Any],
) -> dict[str, int]:
    """
    Map every extracted entity to its DB table + graph node.
    Returns a dict of {entity_type: count} for pipeline progress messages.
    All errors are caught so a single bad entity never aborts the pipeline.
    """
    counts: dict[str, int] = {
        "projects": 0, "plants": 0, "equipment": 0,
        "incidents": 0, "work_orders": 0, "inspections": 0,
        "safety_procedures": 0, "defects": 0, "sensors": 0,
    }

    # ── 1. Projects ───────────────────────────────────────────────────────────
    project_id_map: dict[str, str] = {}   # extracted code → db_id
    for proj in entities.get("projects", []):
        try:
            db_id = await _store_project(proj, doc_id)
            key = proj.get("code") or db_id
            project_id_map[key] = db_id
            counts["projects"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: project store failed (%s): %s", proj, exc)

    # ── 2. Plants ─────────────────────────────────────────────────────────────
    plant_id_map: dict[str, str] = {}    # extracted code → db_id
    for plant in entities.get("plants", []):
        try:
            proj_db_id = _resolve_from_map(plant.get("project_code"), project_id_map)
            db_id = await _store_plant(plant, proj_db_id, doc_id)
            key = plant.get("code") or db_id
            plant_id_map[key] = db_id
            # Link plant → project in graph
            if proj_db_id:
                await _safe_link(db_id, proj_db_id, "BELONGS_TO")
            counts["plants"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: plant store failed (%s): %s", plant, exc)

    # ── 3. Equipment ──────────────────────────────────────────────────────────
    # The rich equipment objects extracted by the LLM allow us to add metadata
    # beyond what the plain equipment_ids pass-through provides.
    eq_id_map: dict[str, str] = {}       # extracted id → db_id (same for equipment)
    for eq in entities.get("equipment", []):
        try:
            eq_id = eq.get("id", "").strip()
            if not eq_id:
                continue
            db_id = await _store_equipment(eq, filename)
            eq_id_map[eq_id] = db_id
            # Link equipment → document
            await _safe_link(eq_id, doc_id, "DOCUMENTED_IN")
            counts["equipment"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: equipment store failed (%s): %s", eq, exc)

    # Also handle equipment_ids that may not be in the rich list (regex fallback path)
    for eq_id in entities.get("equipment_ids", []):
        if eq_id not in eq_id_map:
            try:
                existing = await db.get_equipment(eq_id)
                if existing is None:
                    new_eq = await db.register_equipment(eq_id, filename)
                    if new_eq:
                        await db.upsert_graph_node(
                            {"id": eq_id, "name": f"{eq_id}\n(Discovered)", "type": "equipment", "val": 16}
                        )
                        # Seed default compliance for newly discovered equipment
                        await db.upsert_compliance({
                            "equipment_id": eq_id,
                            "overall_score": 100,
                            "status": "Compliant",
                            "issues": [],
                            "passed": [{"item": f"Auto-registered from document: {filename}"}],
                        })
                else:
                    # Backfill null metrics on existing equipment
                    updates: dict[str, Any] = {"id": eq_id}
                    if existing.get("health_score") is None:
                        updates["health_score"] = 100.0
                    if existing.get("failure_probability") is None:
                        updates["failure_probability"] = 5.0
                    if existing.get("compliance_score") is None:
                        updates["compliance_score"] = 100.0
                    if len(updates) > 1:
                        await db.upsert_equipment(updates)
                await _safe_link(eq_id, doc_id, "DOCUMENTED_IN")
                eq_id_map[eq_id] = eq_id
            except Exception as exc:
                logger.warning("doc_entity_mapper: equipment_ids fallback failed (%s): %s", eq_id, exc)

    # ── 4. Incidents (IncidentReport) ─────────────────────────────────────────
    for inc in entities.get("incidents", []):
        try:
            inc_db_id = await _store_incident_report(inc, eq_id_map, doc_id)
            await _safe_link(doc_id, inc_db_id, "REFERENCES")
            for eq_id in _resolve_eq_ids(inc.get("equipment_ids", []), eq_id_map):
                await _safe_link(inc_db_id, eq_id, "INVOLVES")
            counts["incidents"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: incident store failed (%s): %s", inc, exc)

    # ── 5. Work Orders (ManagedWorkOrder) ─────────────────────────────────────
    for wo in entities.get("work_orders", []):
        try:
            wo_db_id = await _store_work_order(wo, eq_id_map, plant_id_map, project_id_map, doc_id)
            await _safe_link(doc_id, wo_db_id, "REFERENCES")
            for eq_id in _resolve_eq_ids(wo.get("equipment_ids", []), eq_id_map):
                await _safe_link(wo_db_id, eq_id, "APPLIES_TO")
            counts["work_orders"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: work_order store failed (%s): %s", wo, exc)

    # ── 6. Inspections (QualityInspection) ────────────────────────────────────
    for insp in entities.get("inspections", []):
        try:
            qi_db_id = await _store_inspection(insp, eq_id_map, plant_id_map, project_id_map, doc_id)
            await _safe_link(doc_id, qi_db_id, "REFERENCES")
            for eq_id in _resolve_eq_ids(insp.get("equipment_ids", []), eq_id_map):
                await _safe_link(qi_db_id, eq_id, "COVERS")
            counts["inspections"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: inspection store failed (%s): %s", insp, exc)

    # ── 7. Safety Procedures ──────────────────────────────────────────────────
    for sp in entities.get("safety_procedures", []):
        try:
            sp_db_id = await _store_safety_procedure(sp, eq_id_map, plant_id_map, project_id_map, doc_id)
            await _safe_link(doc_id, sp_db_id, "REFERENCES")
            for eq_id in _resolve_eq_ids(sp.get("equipment_ids", []), eq_id_map):
                await _safe_link(sp_db_id, eq_id, "GOVERNS")
            counts["safety_procedures"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: safety_procedure store failed (%s): %s", sp, exc)

    # ── 8. Defects → stored as severity-tagged Incidents ─────────────────────
    for defect in entities.get("defects", []):
        try:
            def_inc_id = await _store_defect_as_incident(defect, eq_id_map, doc_id)
            await _safe_link(doc_id, def_inc_id, "REFERENCES")
            eq_id = defect.get("equipment_id", "")
            if eq_id and eq_id in eq_id_map:
                await _safe_link(def_inc_id, eq_id, "DEFECT_ON")
            counts["defects"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: defect store failed (%s): %s", defect, exc)

    # ── 9. Sensor readings ────────────────────────────────────────────────────
    for sensor in entities.get("sensors", []):
        try:
            await _store_sensor_reading(sensor)
            counts["sensors"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: sensor store failed (%s): %s", sensor, exc)

    return counts


def format_summary(counts: dict[str, int]) -> str:
    """Return a human-readable summary string for the pipeline progress detail."""
    parts = [f"{v} {k.replace('_', ' ')}" for k, v in counts.items() if v > 0]
    return "Mapped: " + ", ".join(parts) if parts else "No structured entities extracted"


# ─────────────────────────────────────────────────────────────────────────────
# Internal entity store helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _store_project(proj: dict[str, Any], doc_id: str) -> str:
    code = proj.get("code") or f"DOC-PRJ-{uuid.uuid4().hex[:6].upper()}"
    data = {
        "code": code,
        "name": proj.get("name") or code,
        "type": proj.get("type", "Industrial"),
        "phase": proj.get("phase", "Operations"),
        "status": "Active",
        "description": proj.get("description", f"Extracted from document {doc_id}"),
    }
    db_id = await db.upsert_project(data)
    label = f"Project\n{data['name'][:20]}"
    await db.upsert_graph_node({"id": db_id, "name": label, "type": "project", "val": 18})
    return db_id


async def _store_plant(plant: dict[str, Any], project_db_id: str | None, doc_id: str) -> str:
    code = plant.get("code") or f"DOC-PLT-{uuid.uuid4().hex[:6].upper()}"
    data: dict[str, Any] = {
        "code": code,
        "name": plant.get("name") or code,
        "type": plant.get("type", "Process Unit"),
        "location": plant.get("location"),
        "area": plant.get("area"),
        "description": plant.get("description", f"Extracted from document {doc_id}"),
        "status": "Operational",
    }
    if project_db_id:
        data["project_id"] = project_db_id
    db_id = await db.upsert_plant(data)
    label = f"Plant\n{data['name'][:20]}"
    await db.upsert_graph_node({"id": db_id, "name": label, "type": "plant", "val": 16})
    return db_id


async def _store_equipment(eq: dict[str, Any], source_doc: str) -> str:
    eq_id = eq["id"]
    existing = await db.get_equipment(eq_id)
    if existing is None:
        # Register with rich metadata + sensible defaults so sensors/dashboard work immediately
        await db.upsert_equipment({
            "id": eq_id,
            "name": eq.get("name") or f"{eq_id} (Discovered)",
            "type": eq.get("type") or "Unknown Equipment",
            "location": eq.get("location") or "Pending — see source document",
            "status": eq.get("status") or "Discovered",
            "manufacturer": eq.get("manufacturer"),
            "model": eq.get("model"),
            # Default metrics — assume healthy until data says otherwise
            "health_score": 100.0,
            "failure_probability": 5.0,
            "compliance_score": 100.0,
            "maintenance_due_days": 30,
            "criticality": eq.get("criticality") or "Unknown",
            "discovered": True,
            "source_documents": [source_doc],
        })
        label = f"{eq_id}\n{(eq.get('name') or 'Equipment')[:18]}"
        await db.upsert_graph_node({"id": eq_id, "name": label, "type": "equipment", "val": 16})
        # Seed a default compliance record so the compliance page shows this equipment
        try:
            await db.upsert_compliance({
                "equipment_id": eq_id,
                "overall_score": 100,
                "status": "Compliant",
                "issues": [],
                "passed": [{"item": f"Auto-registered from document: {source_doc}"}],
            })
        except Exception as exc:
            logger.warning("Could not create default compliance record for %s: %s", eq_id, exc)
    else:
        # Enrich existing record with any new fields from document
        updates: dict[str, Any] = {"id": eq_id}
        for field in ("name", "type", "location", "status", "manufacturer", "model"):
            val = eq.get(field)
            if val and not existing.get(field):
                updates[field] = val
        # Also backfill null metrics on existing discovered equipment
        if existing.get("health_score") is None:
            updates["health_score"] = 100.0
        if existing.get("failure_probability") is None:
            updates["failure_probability"] = 5.0
        if existing.get("compliance_score") is None:
            updates["compliance_score"] = 100.0
        if len(updates) > 1:
            await db.upsert_equipment(updates)
    return eq_id


async def _store_incident_report(inc: dict[str, Any], eq_id_map: dict, doc_id: str) -> str:
    ref = inc.get("ref") or inc.get("incident_number", "")
    data: dict[str, Any] = {
        "incident_number": ref or f"INC-DOC-{uuid.uuid4().hex[:6].upper()}",
        "title": inc.get("title") or ref or "Incident extracted from document",
        "description": inc.get("description", ""),
        "incident_type": _coerce(inc.get("incident_type"), {
            "near_miss", "first_aid", "medical_treatment", "lost_time",
            "fatality", "environmental", "property_damage", "fire", "spill", "other",
        }, "other"),
        "severity": _coerce(inc.get("severity"), {"P1", "P2", "P3", "P4", "P5"}, "P5"),
        "status": "reported",
        "occurred_at": inc.get("occurred_at"),
        "equipment_ids": _resolve_eq_ids(inc.get("equipment_ids", []), eq_id_map),
        "location_description": inc.get("location_description"),
    }
    db_id = await db.upsert_incident_report(data)
    label = f"Incident\n{data['title'][:20]}"
    await db.upsert_graph_node({"id": db_id, "name": label, "type": "incident", "val": 14})
    return db_id


async def _store_work_order(
    wo: dict[str, Any],
    eq_id_map: dict,
    plant_id_map: dict,
    project_id_map: dict,
    doc_id: str,
) -> str:
    ref = wo.get("ref") or wo.get("wo_number", "")
    eq_ids = _resolve_eq_ids(wo.get("equipment_ids", []), eq_id_map)
    data: dict[str, Any] = {
        "wo_number": ref or f"WO-DOC-{uuid.uuid4().hex[:6].upper()}",
        "title": wo.get("title") or ref or "Work Order extracted from document",
        "description": wo.get("description", ""),
        "category": _coerce(wo.get("category"), {
            "preventive", "corrective", "predictive", "emergency", "shutdown", "modification",
        }, "corrective"),
        "priority": _coerce(wo.get("priority"), {"low", "medium", "high", "critical"}, "medium"),
        "status": "draft",
        "equipment_ids": eq_ids,
        "plant_id": _resolve_from_map(wo.get("plant_code"), plant_id_map),
        "project_id": _resolve_from_map(wo.get("project_code"), project_id_map),
    }
    db_id = await db.upsert_managed_work_order(data)
    label = f"WorkOrder\n{data['title'][:20]}"
    await db.upsert_graph_node({"id": db_id, "name": label, "type": "work_order", "val": 14})
    return db_id


async def _store_inspection(
    insp: dict[str, Any],
    eq_id_map: dict,
    plant_id_map: dict,
    project_id_map: dict,
    doc_id: str,
) -> str:
    ref = insp.get("ref") or insp.get("inspection_number", "")
    eq_ids = _resolve_eq_ids(insp.get("equipment_ids", []), eq_id_map)
    data: dict[str, Any] = {
        "inspection_number": ref or f"QI-DOC-{uuid.uuid4().hex[:6].upper()}",
        "title": insp.get("title") or ref or "Inspection extracted from document",
        "inspection_type": _coerce(insp.get("inspection_type"), {
            "equipment", "process", "safety_audit", "environmental", "contractor", "pre_startup",
        }, "equipment"),
        "status": "scheduled",
        "priority": _coerce(insp.get("priority"), {"low", "medium", "high", "critical"}, "medium"),
        "scheduled_date": insp.get("scheduled_date"),
        "summary_notes": insp.get("findings") or insp.get("summary_notes"),
        "equipment_ids": eq_ids,
        "plant_id": _resolve_from_map(insp.get("plant_code"), plant_id_map),
        "project_id": _resolve_from_map(insp.get("project_code"), project_id_map),
    }
    db_id = await db.upsert_quality_inspection(data)
    label = f"Inspection\n{data['title'][:20]}"
    await db.upsert_graph_node({"id": db_id, "name": label, "type": "inspection", "val": 13})
    return db_id


async def _store_safety_procedure(
    sp: dict[str, Any],
    eq_id_map: dict,
    plant_id_map: dict,
    project_id_map: dict,
    doc_id: str,
) -> str:
    code = sp.get("code") or f"SP-DOC-{uuid.uuid4().hex[:6].upper()}"
    eq_ids = _resolve_eq_ids(sp.get("equipment_ids", []), eq_id_map)
    data: dict[str, Any] = {
        "code": code,
        "title": sp.get("title") or code,
        "doc_type": _coerce(sp.get("doc_type"), {
            "SOP", "JSA", "SWMS", "MSDS", "ERP", "Checklist", "Work_Instruction",
        }, "SOP"),
        "category": sp.get("category"),
        "risk_level": _coerce(sp.get("risk_level"), {"Low", "Medium", "High", "Critical"}, None),
        "status": "draft",
        "equipment_ids": eq_ids,
        "plant_id": _resolve_from_map(sp.get("plant_code"), plant_id_map),
        "project_id": _resolve_from_map(sp.get("project_code"), project_id_map),
        "authored_date": _TODAY(),
    }
    db_id = await db.upsert_safety_procedure(data)
    label = f"SOP\n{data['title'][:20]}"
    await db.upsert_graph_node({"id": db_id, "name": label, "type": "safety_procedure", "val": 13})
    return db_id


async def _store_defect_as_incident(
    defect: dict[str, Any],
    eq_id_map: dict,
    doc_id: str,
) -> str:
    """Defects are stored as IncidentReport rows tagged with incident_type='property_damage'."""
    eq_id = defect.get("equipment_id", "")
    severity_map = {"critical": "P2", "major": "P3", "minor": "P4"}
    sev = defect.get("severity", "minor")
    data: dict[str, Any] = {
        "incident_number": f"DEF-DOC-{uuid.uuid4().hex[:6].upper()}",
        "title": defect.get("description", "Defect extracted from document")[:120],
        "description": defect.get("description", ""),
        "incident_type": "property_damage",
        "severity": severity_map.get(sev, "P4"),
        "status": "reported",
        "equipment_ids": [eq_id] if eq_id in eq_id_map else [],
        "location_description": defect.get("location"),
    }
    db_id = await db.upsert_incident_report(data)
    label = f"Defect\n{data['title'][:20]}"
    await db.upsert_graph_node({"id": db_id, "name": label, "type": "defect", "val": 12})
    return db_id


async def _store_sensor_reading(sensor: dict[str, Any]) -> None:
    """Append a sensor reading to SensorHistory AND update equipment.current_readings."""
    eq_id = sensor.get("equipment_id", "").strip()
    parameter = sensor.get("parameter", "").strip()
    if not eq_id or not parameter:
        return
    value_str = sensor.get("value", "")
    unit = sensor.get("unit", "")
    ts = sensor.get("timestamp") or _TODAY()
    try:
        value_float = float(str(value_str).split()[0])
    except (ValueError, IndexError):
        value_float = None

    key = parameter.lower().replace(" ", "_")

    # 1. Append to SensorHistory table
    existing_history = await db.get_sensor_history(eq_id)
    readings: list[dict[str, Any]] = list(existing_history.get(key, []))
    readings.append({"ts": ts, "value": value_float, "unit": unit, "raw": value_str})
    if len(readings) > 500:
        readings = readings[-500:]
    await db.upsert_sensor_history(eq_id, key, readings)

    # 2. Update equipment.current_readings so the sensors page picks it up
    if value_float is not None:
        eq = await db.get_equipment(eq_id)
        if eq is not None:
            current = dict(eq.get("current_readings") or {})
            existing_reading = current.get(key, {})
            current[key] = {
                "value": value_float,
                "unit": unit,
                "normal": existing_reading.get("normal"),
                "alarm":  existing_reading.get("alarm"),
                "trip":   existing_reading.get("trip"),
            }
            await db.upsert_equipment({"id": eq_id, "current_readings": current})


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

async def _safe_link(source: str, target: str, label: str) -> None:
    """Add a graph edge, silently ignoring failures."""
    try:
        await db.add_graph_link(source, target, label)
    except Exception as exc:
        logger.debug("doc_entity_mapper: graph link %s→%s (%s) failed: %s", source, target, label, exc)


def _coerce(value: Any, valid: set, default: Any) -> Any:
    """Return value if it's in the valid set, else default."""
    if value and value in valid:
        return value
    return default


def _resolve_from_map(code: Any, id_map: dict[str, str]) -> str | None:
    """Look up a code in a {code: db_id} map."""
    if not code:
        return None
    return id_map.get(str(code))


def _resolve_eq_ids(raw_ids: list, eq_id_map: dict[str, str]) -> list[str]:
    """Return only equipment IDs that we actually registered in this pipeline run."""
    return [eid for eid in (raw_ids or []) if eid in eq_id_map]
