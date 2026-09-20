"""
AI Operations Brain — DB Service
Async data access layer backed by PostgreSQL (SQLAlchemy ORM).
All runtime reads go through this module; there is no fallback to
in-memory data.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, delete, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.db import models as m

# ── Equipment tag classification (ISA-5.1 prefix patterns) ──────────────────

_INSTRUMENT_PREFIXES = frozenset({
    "FT", "PT", "TT", "LT", "VT", "AT", "XT", "ZT", "ST",
    "FIC", "PIC", "TIC", "LIC", "FCV", "PCV", "TCV",
    "DPDP", "AHU", "PSV", "PRV",
})

_TYPE_MAP = [
    (("P",),               "Centrifugal Pump"),
    (("K", "C"),           "Compressor"),
    (("HX", "E"),          "Heat Exchanger"),
    (("V", "DR"),          "Pressure Vessel"),
    (("T",),               "Storage Tank"),
    (("MOV", "FV", "HV"),  "Valve"),
    (("B",),               "Blower"),
    (("F",),               "Filter / Furnace"),
    (("R",),               "Reactor"),
    (("G",),               "Generator"),
    (("M",),               "Motor"),
]


def _infer_type(equipment_id: str) -> str:
    prefix = equipment_id.split("-")[0].upper()
    for prefixes, eq_type in _TYPE_MAP:
        if prefix in prefixes:
            return eq_type
    return "Unknown Equipment"


def _is_instrument(equipment_id: str) -> bool:
    prefix = equipment_id.split("-")[0].upper()
    return prefix in _INSTRUMENT_PREFIXES

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Session helper
# ─────────────────────────────────────────────────────────────────────────────

def _session() -> AsyncSession:
    return AsyncSessionLocal()


def _split_extra(data: dict[str, Any], model) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split data into (known-column fields, extra fields).
    Handles the "steps" → "pipeline_steps" rename for DocumentRecord."""
    if "steps" in data:
        data = dict(data)
        data["pipeline_steps"] = data.pop("steps")
    known_cols = {c.name for c in model.__table__.columns}
    mapped: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for k, v in data.items():
        if k in known_cols:
            mapped[k] = v
        else:
            extra[k] = v
    return mapped, extra


def _apply_upsert(existing, mapped: dict[str, Any], extra: dict[str, Any]) -> None:
    """Apply mapped fields to an existing ORM row, merging extra instead of replacing."""
    if extra:
        # Merge new extra keys into whatever is already stored
        current_extra: dict[str, Any] = dict(existing.extra or {})
        current_extra.update(extra)
        mapped["extra"] = current_extra
    for k, v in mapped.items():
        setattr(existing, k, v)


def _row_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy ORM row to a plain dict (datetime → ISO string)."""
    d = {}
    for c in obj.__table__.columns:
        v = getattr(obj, c.name)
        if isinstance(v, datetime):
            v = v.isoformat()
        d[c.name] = v
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Equipment
# ─────────────────────────────────────────────────────────────────────────────

async def get_equipment(equipment_id: str) -> dict[str, Any] | None:
    async with _session() as s:
        row = await s.get(m.Equipment, equipment_id)
        if row is None:
            return None
        d = _row_to_dict(row)
        # Flatten extra metadata stored in `extra` JSON column
        if d.get("extra"):
            d.update(d.pop("extra"))
        return d


async def get_all_equipment_list() -> list[dict[str, Any]]:
    async with _session() as s:
        result = await s.execute(select(m.Equipment))
        rows = result.scalars().all()
    out = []
    for row in rows:
        d = _row_to_dict(row)
        if d.get("extra"):
            d.update(d.pop("extra"))
        out.append(d)
    return out


async def update_equipment_sensor_values(
    equipment_id: str,
    sensor_values: dict[str, float],
) -> None:
    """
    Update the `.value` of specific sensors in equipment.current_readings.
    Preserves all existing metadata (unit, normal, alarm, trip).
    Only updates sensors whose keys already exist OR are explicitly provided.

    Called by the authenticated telemetry ingress (POST /api/v1/sensors/{id}/readings) so that
    live readings visible in the AI chat and equipment detail reflect the
    newly entered data.
    """
    if not sensor_values:
        return
    async with _session() as s:
        row = await s.get(m.Equipment, equipment_id)
        if row is None:
            return
        readings: dict[str, Any] = dict(row.current_readings or {})
        updated = False
        for key, val in sensor_values.items():
            if val is None:
                continue
            if key in readings and isinstance(readings[key], dict):
                # Preserve all metadata, only update value
                readings[key] = {**readings[key], "value": float(val)}
                updated = True
            else:
                # Sensor not previously tracked — store bare value dict
                readings[key] = {"value": float(val)}
                updated = True
        if updated:
            row.current_readings = readings
            await s.commit()


async def get_discovered_equipment() -> list[dict[str, Any]]:
    async with _session() as s:
        result = await s.execute(select(m.Equipment).where(m.Equipment.discovered == True))
        rows = result.scalars().all()
    out = []
    for row in rows:
        d = _row_to_dict(row)
        if d.get("extra"):
            d.update(d.pop("extra"))
        out.append(d)
    return out


async def register_equipment(
    equipment_id: str,
    source_document: str,
    eq_type: str = "Unknown Equipment",
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Auto-register a new equipment ID discovered from a document upload."""
    from datetime import datetime

    if _is_instrument(equipment_id):
        return None

    async with _session() as s:
        existing = await s.get(m.Equipment, equipment_id)
        if existing:
            # Merge source document
            src = (existing.source_documents or [])
            if source_document not in src:
                src.append(source_document)
                existing.source_documents = src
                await s.commit()
            return _row_to_dict(existing)

        inferred = _infer_type(equipment_id)
        record = m.Equipment(
            id=equipment_id,
            name=f"{equipment_id} ({inferred})",
            type=inferred,
            location="Pending — see source document",
            health_score=100.0,
            failure_probability=5.0,
            compliance_score=100.0,
            maintenance_due_days=30,
            criticality="Unknown",
            status="Discovered",
            discovered=True,
            source_documents=[source_document],
            extra={"_discovered_at": datetime.now().isoformat()},
        )
        if extra_context:
            record.extra = {**(record.extra or {}), **extra_context}
        s.add(record)
        try:
            await s.commit()
            await s.refresh(record)
            return _row_to_dict(record)
        except Exception as exc:
            # Race condition: another concurrent pipeline created the same equipment
            # between our GET and INSERT.  Roll back and return the existing row.
            await s.rollback()
            logger.warning(
                "Equipment %s already exists (concurrent insert) — merging source document instead",
                equipment_id,
            )
            existing = await s.get(m.Equipment, equipment_id)
            if existing:
                src = list(existing.source_documents or [])
                if source_document not in src:
                    src.append(source_document)
                    existing.source_documents = src
                    await s.commit()
                return _row_to_dict(existing)
            raise exc


async def upsert_equipment(data: dict[str, Any]) -> None:
    """Insert or update an equipment row (used during seeding)."""
    async with _session() as s:
        existing = await s.get(m.Equipment, data["id"])
        mapped, extra = _split_extra(data, m.Equipment)
        if existing:
            _apply_upsert(existing, mapped, extra)
        else:
            if extra:
                mapped["extra"] = extra
            s.add(m.Equipment(**mapped))
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Incidents
# ─────────────────────────────────────────────────────────────────────────────

async def get_equipment_incidents(equipment_id: str) -> list[dict[str, Any]]:
    async with _session() as s:
        result = await s.execute(
            select(m.Incident).where(m.Incident.equipment_id == equipment_id)
        )
        rows = result.scalars().all()
    out = []
    for row in rows:
        d = _row_to_dict(row)
        if d.get("extra"):
            d.update(d.pop("extra"))
        out.append(d)
    return out


async def find_similar_incidents(
    query_keywords: list[str],
    exclude_equipment_id: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return up to `limit` incidents whose keyword JSON or text overlaps with query_keywords.
    Pushes filtering down to SQL using ilike and caps candidate scans with .limit().
    """
    if not query_keywords:
        return []

    clean_kws = [kw.strip() for kw in query_keywords if kw and kw.strip()][:32]
    if not clean_kws:
        return []

    # Build SQL-level ilike conditions across keywords JSON, title, and symptom
    kw_conditions = []
    for kw in clean_kws:
        kw_conditions.append(cast(m.Incident.keywords, String).ilike(f"%{kw}%"))
        kw_conditions.append(m.Incident.title.ilike(f"%{kw}%"))
        kw_conditions.append(m.Incident.symptom.ilike(f"%{kw}%"))

    async with _session() as s:
        q = select(m.Incident).where(or_(*kw_conditions))
        if exclude_equipment_id:
            q = q.where(m.Incident.equipment_id != exclude_equipment_id)
        # Cap scanned rows at SQL level
        q = q.limit(max(limit * 10, 50))
        result = await s.execute(q)
        all_incidents = result.scalars().all()

    scored: list[tuple[int, dict[str, Any]]] = []
    for inc in all_incidents:
        kw_str = f"{str(inc.keywords or [])} {inc.title or ''} {inc.symptom or ''}".lower()
        score = sum(1 for kw in clean_kws if kw.lower() in kw_str)
        if score > 0:
            d = _row_to_dict(inc)
            if d.get("extra"):
                d.update(d.pop("extra"))
            scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


async def upsert_incident(data: dict[str, Any]) -> None:
    async with _session() as s:
        existing = await s.get(m.Incident, data["id"])
        mapped, extra = _split_extra(data, m.Incident)
        if existing:
            _apply_upsert(existing, mapped, extra)
        else:
            if extra:
                mapped["extra"] = extra
            s.add(m.Incident(**mapped))
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Maintenance Records
# ─────────────────────────────────────────────────────────────────────────────

async def get_maintenance_records(equipment_id: str) -> list[dict[str, Any]]:
    async with _session() as s:
        result = await s.execute(
            select(m.MaintenanceRecord).where(m.MaintenanceRecord.equipment_id == equipment_id)
        )
        rows = result.scalars().all()
    out = []
    for row in rows:
        d = _row_to_dict(row)
        if d.get("extra"):
            d.update(d.pop("extra"))
        out.append(d)
    return out


async def list_all_maintenance_records(
    equipment_id: str | None = None,
    status: str | None = None,
    type_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return all maintenance records, optionally filtered by equipment, status, or type."""
    async with _session() as s:
        q = select(m.MaintenanceRecord)
        if equipment_id:
            q = q.where(m.MaintenanceRecord.equipment_id == equipment_id)
        if status:
            q = q.where(m.MaintenanceRecord.status == status)
        if type_filter:
            q = q.where(m.MaintenanceRecord.type == type_filter)
        rows = (await s.execute(q)).scalars().all()
    out = []
    for row in rows:
        d = _row_to_dict(row)
        if d.get("extra"):
            d.update(d.pop("extra"))
        out.append(d)
    return sorted(out, key=lambda x: (x.get("date") or ""), reverse=True)


async def upsert_maintenance_record(data: dict[str, Any]) -> None:
    async with _session() as s:
        existing = await s.get(m.MaintenanceRecord, data["id"])
        mapped, extra = _split_extra(data, m.MaintenanceRecord)
        if existing:
            _apply_upsert(existing, mapped, extra)
        else:
            if extra:
                mapped["extra"] = extra
            s.add(m.MaintenanceRecord(**mapped))
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Documents
# ─────────────────────────────────────────────────────────────────────────────

async def get_equipment_documents(
    equipment_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return documents whose equipment_ids JSON list contains equipment_id.
    Pushes filtering down to SQL with ilike and caps candidate scans with .limit().
    """
    if not equipment_id:
        return []

    async with _session() as s:
        q = (
            select(m.DocumentRecord)
            .where(cast(m.DocumentRecord.equipment_ids, String).ilike(f"%{equipment_id}%"))
            .limit(limit)
        )
        result = await s.execute(q)
        rows = result.scalars().all()
    out = []
    for row in rows:
        if equipment_id in (row.equipment_ids or []):
            d = _row_to_dict(row)
            if d.get("extra"):
                d.update(d.pop("extra"))
            if "pipeline_steps" in d and "steps" not in d:
                d["steps"] = d.pop("pipeline_steps")
            out.append(d)
    return out


async def list_all_documents() -> list[dict[str, Any]]:
    async with _session() as s:
        result = await s.execute(select(m.DocumentRecord))
        rows = result.scalars().all()
    out = []
    for row in rows:
        d = _row_to_dict(row)
        if d.get("extra"):
            d.update(d.pop("extra"))
        if "pipeline_steps" in d and "steps" not in d:
            d["steps"] = d.pop("pipeline_steps")
        out.append(d)
    return out


async def get_document(doc_id: str) -> dict[str, Any] | None:
    async with _session() as s:
        row = await s.get(m.DocumentRecord, doc_id)
        if row is None:
            return None
        d = _row_to_dict(row)
        if d.get("extra"):
            d.update(d.pop("extra"))
        if "pipeline_steps" in d and "steps" not in d:
            d["steps"] = d.pop("pipeline_steps")
        return d


async def delete_document(doc_id: str) -> None:
    """Hard-delete a document record from the database."""
    async with _session() as s:
        row = await s.get(m.DocumentRecord, doc_id)
        if row:
            await s.delete(row)
            await s.commit()


async def save_document(data: dict[str, Any]) -> None:
    """Insert or update a document record (used by upload pipeline)."""
    async with _session() as s:
        existing = await s.get(m.DocumentRecord, data["id"])
        mapped, extra = _split_extra(data, m.DocumentRecord)
        if existing:
            _apply_upsert(existing, mapped, extra)
        else:
            if extra:
                mapped["extra"] = extra
            s.add(m.DocumentRecord(**mapped))
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Compliance
# ─────────────────────────────────────────────────────────────────────────────

async def get_compliance(equipment_id: str) -> dict[str, Any] | None:
    async with _session() as s:
        row = await s.get(m.Compliance, equipment_id)
        if row is None:
            return None
        return _row_to_dict(row)


async def get_all_compliance() -> list[dict[str, Any]]:
    async with _session() as s:
        result = await s.execute(select(m.Compliance))
        rows = result.scalars().all()
    return [_row_to_dict(row) for row in rows]


async def upsert_compliance(data: dict[str, Any]) -> None:
    async with _session() as s:
        existing = await s.get(m.Compliance, data["equipment_id"])
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            s.add(m.Compliance(**data))
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Spare Parts
# ─────────────────────────────────────────────────────────────────────────────

async def get_equipment_spare_parts(equipment_id: str) -> list[dict[str, Any]]:
    async with _session() as s:
        result = await s.execute(select(m.SparePart))
        rows = result.scalars().all()
    return [
        _row_to_dict(row) for row in rows
        if equipment_id in (row.equipment_ids or [])
    ]


async def upsert_spare_part(data: dict[str, Any]) -> None:
    async with _session() as s:
        existing = await s.get(m.SparePart, data["id"])
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            s.add(m.SparePart(**data))
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Technicians
# ─────────────────────────────────────────────────────────────────────────────

async def get_equipment_technicians(equipment_id: str) -> list[dict[str, Any]]:
    """
    Return technicians for an equipment.
    Merges the legacy Technician seed table (equipment_ids-keyed) with live
    UserProfile rows that have a technical role, so new users created via
    /api/v1/users are automatically surfaced here.
    """
    results: dict[str, dict[str, Any]] = {}

    async with _session() as s:
        # 1. Legacy Technician seed data
        tech_rows = (await s.execute(select(m.Technician))).scalars().all()
        for row in tech_rows:
            if equipment_id in (row.equipment_ids or []):
                d = _row_to_dict(row)
                if d.get("extra"):
                    d.update(d.pop("extra"))
                results[row.id] = d

        # 2. Live UserProfile rows with technical roles
        technical_roles = {"technician", "supervisor", "safety_officer",
                           "area_authority", "authorized_person"}
        up_rows = (await s.execute(
            select(m.UserProfile).where(
                m.UserProfile.role.in_(list(technical_roles)),
                m.UserProfile.is_active == True,  # noqa: E712
            )
        )).scalars().all()
        for row in up_rows:
            # Include this user if they are not already in results (avoid dups).
            uid = f"USR-{row.id}"
            if uid not in results:
                results[uid] = {
                    "id":         uid,
                    "name":       row.name,
                    "role":       row.role,
                    "contact":    row.email or "",
                    "certifications": row.certifications or [],
                    "available":  True,
                    "_source":    "user_profile",
                }

    return list(results.values())


async def upsert_technician(data: dict[str, Any]) -> None:
    async with _session() as s:
        existing = await s.get(m.Technician, data["id"])
        mapped, extra = _split_extra(data, m.Technician)
        if existing:
            _apply_upsert(existing, mapped, extra)
        else:
            if extra:
                mapped["extra"] = extra
            s.add(m.Technician(**mapped))
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Graph Nodes / Links
# ─────────────────────────────────────────────────────────────────────────────

async def get_full_graph() -> dict[str, Any]:
    async with _session() as s:
        nodes_result = await s.execute(select(m.GraphNode))
        links_result = await s.execute(select(m.GraphLink))
        nodes = [_row_to_dict(n) for n in nodes_result.scalars().all()]
        links = [_row_to_dict(l) for l in links_result.scalars().all()]
    # Strip internal 'id' from links (auto-increment PK, not needed by frontend)
    for lnk in links:
        lnk.pop("id", None)
    return {"nodes": nodes, "links": links}


async def get_equipment_subgraph(equipment_id: str) -> dict[str, Any]:
    """The equipment node, its direct neighbours, and the links among them."""
    return await get_equipment_neighbourhood(equipment_id, max_depth=1)


async def get_equipment_neighbourhood(
    equipment_id: str,
    max_depth: int,
    limit: int | None = None,
) -> dict[str, Any]:
    """Breadth-first traversal over graph_links.

    Returns every node within max_depth hops of the equipment (at most `limit`
    nodes when a limit is given) and the links among the nodes reached.
    """
    reached: set[str] = {equipment_id}
    frontier: set[str] = {equipment_id}
    for _ in range(max_depth):
        if not frontier:
            break
        async with _session() as s:
            result = await s.execute(
                select(m.GraphLink).where(
                    or_(m.GraphLink.source.in_(frontier), m.GraphLink.target.in_(frontier))
                )
            )
            touching = result.scalars().all()
        frontier = set()
        for lnk in touching:
            for node_id in (lnk.source, lnk.target):
                if node_id in reached or (limit is not None and len(reached) >= limit):
                    continue
                reached.add(node_id)
                frontier.add(node_id)

    async with _session() as s:
        nodes_result = await s.execute(select(m.GraphNode).where(m.GraphNode.id.in_(reached)))
        links_result = await s.execute(
            select(m.GraphLink).where(
                m.GraphLink.source.in_(reached),
                m.GraphLink.target.in_(reached),
            )
        )
        nodes = [_row_to_dict(n) for n in nodes_result.scalars().all()]
        link_dicts = [_row_to_dict(link) for link in links_result.scalars().all()]

    for lnk in link_dicts:
        lnk.pop("id", None)
    return {"nodes": nodes, "links": link_dicts}


async def upsert_graph_node(data: dict[str, Any]) -> None:
    """Write a graph node to PostgreSQL (the graph's system of record)."""
    async with _session() as s:
        existing = await s.get(m.GraphNode, data["id"])
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            s.add(m.GraphNode(**data))
        await s.commit()


async def add_graph_link(source: str, target: str, label: str) -> None:
    """Add a graph link if it doesn't already exist."""
    async with _session() as s:
        result = await s.execute(
            select(m.GraphLink).where(
                m.GraphLink.source == source,
                m.GraphLink.target == target,
                m.GraphLink.label == label,
            )
        )
        if result.scalar_one_or_none() is None:
            s.add(m.GraphLink(source=source, target=target, label=label))
            await s.commit()


async def remove_graph_node_and_links(node_id: str) -> None:
    """Delete a graph node and every edge that references it."""
    async with _session() as s:
        await s.execute(
            delete(m.GraphLink).where(
                or_(m.GraphLink.source == node_id, m.GraphLink.target == node_id)
            )
        )
        node = await s.get(m.GraphNode, node_id)
        if node:
            await s.delete(node)
        await s.commit()


async def remove_document_from_equipment(doc_name: str, equipment_ids: list[str]) -> None:
    """Remove a document filename from Equipment.source_documents for affected equipment."""
    async with _session() as s:
        for eq_id in equipment_ids:
            row = await s.get(m.Equipment, eq_id)
            if row and row.source_documents:
                updated = [sd for sd in row.source_documents if sd != doc_name]
                if len(updated) != len(row.source_documents):
                    row.source_documents = updated
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Sensor History
# ─────────────────────────────────────────────────────────────────────────────

async def get_sensor_history(equipment_id: str) -> dict[str, Any]:
    """Return {sensor_key: [{ts, value}, ...]} for the given equipment."""
    async with _session() as s:
        result = await s.execute(
            select(m.SensorHistory).where(m.SensorHistory.equipment_id == equipment_id)
        )
        rows = result.scalars().all()
    return {row.sensor_key: (row.readings or []) for row in rows}


async def upsert_sensor_history(equipment_id: str, sensor_key: str, readings: list) -> None:
    async with _session() as s:
        result = await s.execute(
            select(m.SensorHistory).where(
                m.SensorHistory.equipment_id == equipment_id,
                m.SensorHistory.sensor_key == sensor_key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.readings = readings
        else:
            s.add(m.SensorHistory(equipment_id=equipment_id, sensor_key=sensor_key, readings=readings))
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Work Orders (lightweight helpers used by threshold monitor)
# ─────────────────────────────────────────────────────────────────────────────

async def get_work_orders(equipment_id: str | None = None) -> list[dict[str, Any]]:
    async with _session() as s:
        q = select(m.SavedWorkOrder).order_by(m.SavedWorkOrder.created_at.desc())
        if equipment_id:
            q = q.where(m.SavedWorkOrder.equipment_id == equipment_id)
        result = await s.execute(q)
        return [_row_to_dict(r) for r in result.scalars().all()]


async def create_work_order(data: dict[str, Any]) -> str:
    """Insert a work order row and return its ID. Used by threshold monitor."""
    import uuid as _uuid
    wo_id = data.get("id") or f"WO-{_uuid.uuid4().hex[:8].upper()}"
    steps = [
        {**s, "checked": False, "actual_notes": ""}
        for s in data.get("steps", [])
    ]
    record = m.SavedWorkOrder(
        id=wo_id,
        equipment_id=data["equipment_id"],
        query_text=data.get("query_text", ""),
        risk_level=data.get("risk_level"),
        wo_type=data.get("wo_type", "Corrective"),
        description=data.get("description", ""),
        estimated_duration_hours=data.get("estimated_duration_hours", 0),
        required_technicians=data.get("required_technicians", 1),
        status=data.get("status", "open"),
        steps=steps,
        spare_parts=data.get("spare_parts", []),
        safety_precautions=data.get("safety_precautions", []),
        required_permits=data.get("required_permits", []),
    )
    async with _session() as s:
        s.add(record)
        await s.commit()
    return wo_id


# ─────────────────────────────────────────────────────────────────────────────
# Composite: Equipment Brain (used by orchestrator + knowledge-graph API)
# ─────────────────────────────────────────────────────────────────────────────

async def get_equipment_brain(equipment_id: str) -> dict[str, Any]:
    eq = await get_equipment(equipment_id)
    if eq is None:
        return {}

    incidents = await get_equipment_incidents(equipment_id)
    maintenance = await get_maintenance_records(equipment_id)
    documents = await get_equipment_documents(equipment_id)
    parts = await get_equipment_spare_parts(equipment_id)
    techs = await get_equipment_technicians(equipment_id)
    compliance = await get_compliance(equipment_id) or {}
    sensor_history = await get_sensor_history(equipment_id)

    downstream = []
    for eid in (eq.get("downstream_equipment") or []):
        child = await get_equipment(eid)
        if child:
            downstream.append(child)

    return {
        "equipment": eq,
        "incidents": incidents,
        "maintenance_records": maintenance,
        "documents": [{"id": d["id"], "name": d["name"], "type": d["type"]} for d in documents],
        "technicians": techs,
        "spare_parts": parts,
        "compliance": compliance,
        "sensor_history": sensor_history,
        "downstream_equipment": downstream,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Graph update when a new document is ingested
# ─────────────────────────────────────────────────────────────────────────────

async def update_graph_with_document(doc_id: str, filename: str, entities: dict[str, Any]) -> None:
    """
    Add the uploaded document as a graph node and link it to equipment IDs
    found during entity extraction.

    Unknown equipment tags are only auto-registered when
    AUTO_REGISTER_ENTITIES=true — by default extracted tags never create new
    master-data records (review gate; see doc_entity_mapper).
    """
    from app.core.config import settings

    await upsert_graph_node({"id": doc_id, "name": filename[:30], "type": "document", "val": 10})

    for eq_id in entities.get("equipment_ids", []):
        try:
            eq = await get_equipment(eq_id)
            if eq is None:
                if not settings.auto_register_entities:
                    continue  # held for review — do not create or link
                new_eq = await register_equipment(eq_id, filename)
                if new_eq:
                    await upsert_graph_node(
                        {"id": eq_id, "name": f"{eq_id}\n(Discovered)", "type": "equipment", "val": 16}
                    )

            await add_graph_link(eq_id, doc_id, "DOCUMENTED_IN")
        except Exception as exc:
            logger.warning(
                "Could not register/link equipment %s from %s — skipping: %s",
                eq_id, filename, exc,
            )
