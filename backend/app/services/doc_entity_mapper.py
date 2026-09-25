"""
AI Operations Brain — Document Entity Mapper
==============================================
After LLM/regex entity extraction on an uploaded document, this service
maps every detected entity to its proper DB table and knowledge-graph node,
preserving all cross-entity relationships.

Entity types handled
--------------------
  equipment        → models.Equipment  (auto-register)
  incident         → models.Incident   (one row per equipment it names)
  defect           → models.Incident   (severity-tagged maintenance incident)
  sensor           → models.SensorHistory  (append reading)

Relationships written to the graph
-----------------------------------
  Document   ──DOCUMENTED_IN──▶  Equipment
  Document   ──REFERENCES──▶     Incident
  Incident   ──INVOLVES──▶       Equipment
  Defect     ──DEFECT_ON──▶      Equipment
"""
from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.services import db_service as db
from app.services.incidentWriter import saveIncident
from app.services.sensorReadings import DOCUMENT_KEY, DOCUMENT_SOURCE, appendSensorHistory

logger = logging.getLogger(__name__)

_TODAY = lambda: datetime.utcnow().strftime("%Y-%m-%d")   # noqa: E731

INCIDENT_SEVERITIES = {"Critical", "High", "Medium", "Low"}
DEFAULT_INCIDENT_SEVERITY = "Medium"
DEFECT_SEVERITY_LABELS = {"critical": "Critical", "major": "High", "minor": "Medium"}
MAX_TITLE_CHARS = 120
ROW_ID_DIGEST_CHARS = 8
DOCUMENT_INCIDENT_PREFIX = "INC-DOC"
DOCUMENT_DEFECT_PREFIX = "DEF-DOC"
DATE_CHARS = len("YYYY-MM-DD")


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ─────────────────────────────────────────────────────────────────────────────

async def _hold_for_review(doc_id: str, filename: str, entities: dict[str, Any]) -> dict[str, int]:
    """Review gate (AUTO_REGISTER_ENTITIES=false, the default).

    Extraction confidence is not master-data stewardship: a document must not
    be able to create equipment, incidents, or default
    health/compliance values on its own. This path only links the document to
    equipment that ALREADY exists; every extracted entity that would have
    created a new record is held on the document as pending_review for a human
    to accept (re-run with AUTO_REGISTER_ENTITIES=true, or create manually).
    """
    counts: dict[str, int] = {"linked_existing_equipment": 0, "pending_review": 0}
    unknownEqIds: list[str] = []
    for eq_id in entities.get("equipment_ids", []) or []:
        try:
            if await db.get_equipment(eq_id):
                await _safe_link(eq_id, doc_id, "DOCUMENTED_IN")
                counts["linked_existing_equipment"] += 1
            else:
                unknownEqIds.append(eq_id)
        except Exception as exc:
            logger.warning("doc_entity_mapper: link check failed (%s): %s", eq_id, exc)

    held = _heldEntityLabels(unknownEqIds, entities)
    counts["pending_review"] = len(held)
    if held:
        await db.save_document({
            "id": doc_id,
            "entities_pending_review": True,
            "held_entities": held,
            "pending_review_note": (
                f"{len(held)} extracted entit(ies) held for review — "
                "auto-registration is disabled (AUTO_REGISTER_ENTITIES=false)"
            ),
        })
        logger.info("Document %s: %d extracted entities held for review",
                    doc_id, counts["pending_review"])
    return counts


async def map_and_store(
    doc_id: str,
    filename: str,
    entities: dict[str, Any],
) -> dict[str, int]:
    """
    Map every extracted entity to its DB table + graph node.
    Returns a dict of {entity_type: count} for pipeline progress messages.
    All errors are caught so a single bad entity never aborts the pipeline.

    When AUTO_REGISTER_ENTITIES is false (default) no new master-data records
    are created — see _hold_for_review.
    """
    if not settings.auto_register_entities:
        return await _hold_for_review(doc_id, filename, entities)
    counts: dict[str, int] = {"equipment": 0, "incidents": 0, "defects": 0, "sensors": 0}

    # ── 1. Equipment ──────────────────────────────────────────────────────────
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
                await _safe_link(eq_id, doc_id, "DOCUMENTED_IN")
                eq_id_map[eq_id] = eq_id
            except Exception as exc:
                logger.warning("doc_entity_mapper: equipment_ids fallback failed (%s): %s", eq_id, exc)

    # ── 2. Incidents ──────────────────────────────────────────────────────────
    for inc in entities.get("incidents", []):
        try:
            for inc_db_id, eq_id in await _store_incident(inc, eq_id_map, doc_id):
                await _safe_link(doc_id, inc_db_id, "REFERENCES")
                await _safe_link(inc_db_id, eq_id, "INVOLVES")
                counts["incidents"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: incident store failed (%s): %s", inc, exc)

    # ── 3. Defects → stored as severity-tagged Incidents ─────────────────────
    for defect in entities.get("defects", []):
        try:
            def_inc_id = await _store_defect(defect, eq_id_map, doc_id)
            if def_inc_id is None:
                continue
            await _safe_link(doc_id, def_inc_id, "REFERENCES")
            await _safe_link(def_inc_id, defect["equipment_id"], "DEFECT_ON")
            counts["defects"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: defect store failed (%s): %s", defect, exc)

    # ── 4. Sensor readings ────────────────────────────────────────────────────
    for sensor in entities.get("sensors", []):
        try:
            await _store_sensor_reading(sensor, doc_id)
            counts["sensors"] += 1
        except Exception as exc:
            logger.warning("doc_entity_mapper: sensor store failed (%s): %s", sensor, exc)

    return counts


def format_summary(counts: dict[str, int]) -> str:
    """Return a human-readable summary string for the pipeline progress detail."""
    if "pending_review" in counts:
        linked = counts.get("linked_existing_equipment", 0)
        pending = counts.get("pending_review", 0)
        bits = []
        if linked:
            bits.append(f"linked {linked} existing equipment")
        if pending:
            bits.append(f"{pending} new entit(ies) held for review")
        return "; ".join(bits).capitalize() if bits else "No structured entities extracted"
    parts = [f"{v} {k.replace('_', ' ')}" for k, v in counts.items() if v > 0]
    return "Mapped: " + ", ".join(parts) if parts else "No structured entities extracted"


# ─────────────────────────────────────────────────────────────────────────────
# Internal entity store helpers
# ─────────────────────────────────────────────────────────────────────────────


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
            # No health, failure probability, compliance or due date: nothing has measured this equipment yet.
            "criticality": eq.get("criticality") or "Unknown",
            "discovered": True,
            "source_documents": [source_doc],
        })
        label = f"{eq_id}\n{(eq.get('name') or 'Equipment')[:18]}"
        await db.upsert_graph_node({"id": eq_id, "name": label, "type": "equipment", "val": 16})
    else:
        # Enrich existing record with any new fields from document
        updates: dict[str, Any] = {"id": eq_id}
        for field in ("name", "type", "location", "status", "manufacturer", "model"):
            val = eq.get(field)
            if val and not existing.get(field):
                updates[field] = val
        if len(updates) > 1:
            await db.upsert_equipment(updates)
    return eq_id


def _document_row_id(prefix: str, *parts: str) -> str:
    """Row id derived from the source document, never from model-supplied text alone.

    A document that names an existing incident (e.g. INC-2022-034) must not be able
    to overwrite that curated row, and re-processing the same document must not
    create duplicates — so the id is a digest of the document and what it says."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:ROW_ID_DIGEST_CHARS].upper()
    return f"{prefix}-{digest}"


async def _store_incident(inc: dict[str, Any], eq_id_map: dict, doc_id: str) -> list[tuple[str, str]]:
    """Store an extracted incident once per registered equipment it names.

    Returns (incident_id, equipment_id) pairs. An incident naming no registered
    equipment is skipped: incidents.equipment_id is a required foreign key."""
    ref = inc.get("ref") or inc.get("incident_number") or ""
    title = inc.get("title") or ref or "Incident extracted from document"
    stored: list[tuple[str, str]] = []
    for eq_id in _resolve_eq_ids(inc.get("equipment_ids", []), eq_id_map):
        inc_id = _document_row_id(DOCUMENT_INCIDENT_PREFIX, doc_id, ref or title, eq_id)
        await saveIncident({
            "id": inc_id,
            "equipment_id": eq_id,
            "date": (inc.get("occurred_at") or _TODAY())[:DATE_CHARS],
            "title": title[:MAX_TITLE_CHARS],
            "severity": _coerce(inc.get("severity"), INCIDENT_SEVERITIES, DEFAULT_INCIDENT_SEVERITY),
            "symptom": inc.get("description", ""),
            "source_document": doc_id,
            "source_ref": ref,
        })
        await db.upsert_graph_node({"id": inc_id, "name": f"Incident\n{title[:20]}", "type": "incident", "val": 14})
        stored.append((inc_id, eq_id))
    return stored


async def _store_defect(defect: dict[str, Any], eq_id_map: dict, doc_id: str) -> str | None:
    """Store a defect as a severity-tagged incident; None when its equipment is not registered."""
    eq_id = defect.get("equipment_id", "")
    if eq_id not in eq_id_map:
        return None
    description = defect.get("description", "")
    title = (description or "Defect extracted from document")[:MAX_TITLE_CHARS]
    def_id = _document_row_id(DOCUMENT_DEFECT_PREFIX, doc_id, description, eq_id)
    await saveIncident({
        "id": def_id,
        "equipment_id": eq_id,
        "date": _TODAY(),
        "title": title,
        "severity": DEFECT_SEVERITY_LABELS.get(defect.get("severity", "minor"), DEFAULT_INCIDENT_SEVERITY),
        "symptom": description,
        "source_document": doc_id,
        "kind": "defect",
        "location": defect.get("location"),
    })
    await db.upsert_graph_node({"id": def_id, "name": f"Defect\n{title[:20]}", "type": "defect", "val": 12})
    return def_id


async def _store_sensor_reading(sensor: dict[str, Any], doc_id: str) -> None:
    """Append a sensor reading to SensorHistory, naming the document it came from so deleting the document removes
    it (sensorReadings.removeDocumentReadings). A figure that does not read as a number is not a reading, and every
    consumer of the history compares numbers, so it is not stored.

    Does NOT mutate equipment.current_readings (reserved for live authenticated telemetry)."""
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
        return
    if math.isnan(value_float):
        return

    key = parameter.lower().replace(" ", "_")

    await appendSensorHistory(eq_id, key, {
        "ts": ts, "value": value_float, "unit": unit, "raw": value_str, "source": DOCUMENT_SOURCE,
        DOCUMENT_KEY: doc_id,
    })

    # equipment.current_readings is intentionally NOT updated here.
    # Live equipment telemetry is reserved for authenticated telemetry ingress
    # to prevent document-extracted figures from triggering automated work orders.


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

async def _safe_link(source: str, target: str, label: str) -> None:
    """Add a graph edge, silently ignoring failures."""
    try:
        await db.add_graph_link(source, target, label)
    except Exception as exc:
        logger.debug("doc_entity_mapper: graph link %s→%s (%s) failed: %s", source, target, label, exc)


def _heldEntityLabels(unknownEqIds: list[str], entities: dict[str, Any]) -> list[str]:
    """One readable line per distinct entity the review gate held back, for the document panel."""
    labels = [f"Equipment {eq_id} (not registered)" for eq_id in unknownEqIds]
    for inc in entities.get("incidents", []) or []:
        labels.append(f"Incident: {_entityField(inc, 'title') or _entityField(inc, 'ref') or str(inc)}")
    for defect in entities.get("defects", []) or []:
        labels.append(f"Defect on {_entityField(defect, 'equipment_id') or '?'}: {_entityField(defect, 'description') or str(defect)}")
    for sensor in entities.get("sensors", []) or []:
        reading = " ".join(str(_entityField(sensor, key)) for key in ("equipment_id", "parameter", "value", "unit") if _entityField(sensor, key))
        labels.append(f"Reading: {reading or str(sensor)}")
    # A document that repeats a reading yields identical entities; listing the same line twice tells a reviewer nothing.
    return list(dict.fromkeys(label[:MAX_TITLE_CHARS] for label in labels))


def _entityField(entity: Any, key: str) -> Any:
    # Extraction output is model text: an entity may arrive as a bare string instead of an object.
    return entity.get(key) if isinstance(entity, dict) else None


def _coerce(value: Any, valid: set, default: Any) -> Any:
    """Return value if it's in the valid set, else default."""
    if value and value in valid:
        return value
    return default


def _resolve_eq_ids(raw_ids: list, eq_id_map: dict[str, str]) -> list[str]:
    """Return only equipment IDs that we actually registered in this pipeline run."""
    return [eid for eid in (raw_ids or []) if eid in eq_id_map]
