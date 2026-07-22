"""
AI Operations Brain — Audit Log API
Exposes the immutable audit trail with filtering, full-text search,
relation mapping, and CSV export.

Endpoints:
  GET /api/v1/audit                       — paginated audit log
  GET /api/v1/audit/{object_type}/{id}    — all events for one object
  GET /api/v1/audit/relations/{equip_id} — full relation map for an equipment
  GET /api/v1/audit/export                — CSV export (last N days)
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_, or_, desc

from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services import db_service as db

logger = logging.getLogger(__name__)
router = APIRouter()

_OBJ_ICON = {
    "work_order":  "🔧", "checklist":   "✅", "incident":    "🚨",
    "defect":      "🔍", "equipment":   "⚙️",  "sensor":      "📡",
    "safety":      "🛡️",  "document":    "📄", "form":        "📝",
    "lesson":      "📚", "feedback":    "💡", "system":      "🤖",
}


def _row_to_dict(row: m.AuditLog) -> dict[str, Any]:
    return {
        "id":           row.id,
        "timestamp":    row.timestamp.isoformat() if row.timestamp else None,
        "object_type":  row.object_type,
        "object_id":    row.object_id,
        "equipment_id": row.equipment_id,
        "action":       row.action,
        "actor":        row.actor,
        "actor_type":   row.actor_type,
        "changes":      row.changes,
        "risk_level":   row.risk_level,
        "notes":        row.notes,
        "related_ids":  row.related_ids,
        "icon":         _OBJ_ICON.get(row.object_type, "📋"),
    }


# ── Paginated audit log ───────────────────────────────────────────────────────

@router.get("")
async def get_audit_log(
    object_type: str | None = Query(None),
    equipment_id: str | None = Query(None),
    actor: str | None = Query(None),
    action: str | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Return filtered, paginated audit log entries (newest first)."""
    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as s:
        q = select(m.AuditLog).where(m.AuditLog.timestamp >= since)
        if object_type:    q = q.where(m.AuditLog.object_type == object_type)
        if equipment_id:   q = q.where(m.AuditLog.equipment_id == equipment_id)
        if actor:          q = q.where(m.AuditLog.actor.ilike(f"%{actor}%"))
        if action:         q = q.where(m.AuditLog.action == action)
        total_q = q
        q = q.order_by(desc(m.AuditLog.timestamp)).offset(offset).limit(limit)
        result = await s.execute(q)
        rows = result.scalars().all()
        # Count
        from sqlalchemy import func
        count_result = await s.execute(
            select(func.count()).select_from(total_q.subquery())
        )
        total = count_result.scalar_one()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [_row_to_dict(r) for r in rows],
    }


# ── Relation map for one equipment ────────────────────────────────────────────
# NOTE: Must be defined BEFORE /{object_type}/{object_id} to avoid shadowing.

@router.get("/relations/{equipment_id}")
async def get_relation_map(equipment_id: str):
    """
    Return the full relation web for one equipment — all connected objects
    grouped by type, with audit trails, forming the industry 'asset history' view.
    """
    eq = await db.get_equipment(equipment_id)
    if not eq:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")

    # Gather all related objects
    incidents   = await db.get_equipment_incidents(equipment_id)
    maintenance = await db.get_maintenance_records(equipment_id)
    documents   = await db.get_equipment_documents(equipment_id)

    async with AsyncSessionLocal() as s:
        # Work orders
        wo_result = await s.execute(
            select(m.SavedWorkOrder).where(m.SavedWorkOrder.equipment_id == equipment_id)
            .order_by(desc(m.SavedWorkOrder.created_at))
        )
        work_orders = [
            {"id": r.id, "type": r.wo_type, "status": r.status,
             "description": r.description, "risk_level": r.risk_level,
             "created_at": r.created_at.isoformat() if r.created_at else None,
             "completed_at": r.completed_at.isoformat() if r.completed_at else None,
             "solution_worked": r.solution_worked}
            for r in wo_result.scalars().all()
        ]

        # Checklists
        cl_result = await s.execute(
            select(m.SavedChecklist).where(m.SavedChecklist.equipment_id == equipment_id)
            .order_by(desc(m.SavedChecklist.created_at))
        )
        checklists = [
            {"id": r.id, "risk_level": r.risk_level, "status": r.status,
             "item_count": len(r.items or []),
             "checked_count": sum(1 for i in (r.items or []) if i.get("checked")),
             "created_at": r.created_at.isoformat() if r.created_at else None,
             "completed_at": r.completed_at.isoformat() if r.completed_at else None,
             "outcome_notes": r.outcome_notes}
            for r in cl_result.scalars().all()
        ]

        # Audit log for this equipment
        audit_result = await s.execute(
            select(m.AuditLog).where(m.AuditLog.equipment_id == equipment_id)
            .order_by(desc(m.AuditLog.timestamp))
            .limit(50)
        )
        audit_entries = [_row_to_dict(r) for r in audit_result.scalars().all()]

    # Safety incidents (PTW checks) from incident table
    safety_records = [i for i in incidents if i.get("id", "").startswith("PTW-")]
    incidents_clean = [i for i in incidents if not i.get("id", "").startswith("PTW-")]
    lesson_records  = [i for i in incidents if i.get("id", "").startswith("LESSON-")]

    # Build comprehensive timeline merging all sources
    timeline: list[dict] = []
    for inc in incidents_clean:
        timeline.append({"date": inc.get("date"), "type": "incident",
                         "id": inc["id"], "title": inc.get("title"), "severity": inc.get("severity"),
                         "description": inc.get("symptom")})
    for mr in maintenance:
        timeline.append({"date": mr.get("date") or mr.get("scheduled_date"), "type": "maintenance",
                         "id": mr["id"], "title": mr.get("description"), "severity": mr.get("status"),
                         "description": mr.get("findings")})
    for wo in work_orders:
        timeline.append({"date": wo["created_at"], "type": "work_order",
                         "id": wo["id"], "title": f"WO: {wo['type']} ({wo['status']})",
                         "severity": wo.get("risk_level"), "description": wo.get("description")})
    for cl in checklists:
        timeline.append({"date": cl["created_at"], "type": "checklist",
                         "id": cl["id"], "title": f"Inspection ({cl['status']})",
                         "severity": cl.get("risk_level"), "description": cl.get("outcome_notes")})
    for sf in safety_records:
        timeline.append({"date": sf.get("date"), "type": "safety",
                         "id": sf["id"], "title": sf.get("title"), "severity": sf.get("severity"),
                         "description": sf.get("action_taken")})

    timeline.sort(key=lambda x: (x.get("date") or ""), reverse=True)

    return {
        "equipment_id":      equipment_id,
        "equipment_name":    eq.get("name"),
        "equipment_type":    eq.get("type"),
        "location":          eq.get("location"),
        "health_score":      eq.get("health_score"),
        "status":            eq.get("status"),
        "relations": {
            "incidents":        incidents_clean,
            "maintenance":      maintenance,
            "work_orders":      work_orders,
            "checklists":       checklists,
            "documents":        [{"id": d["id"], "name": d["name"], "type": d["type"], "date": d.get("date")} for d in documents],
            "safety_checks":    safety_records,
            "lessons_learned":  lesson_records,
        },
        "timeline":    timeline,
        "audit_trail": audit_entries,
        "summary": {
            "total_incidents":  len(incidents_clean),
            "total_work_orders": len(work_orders),
            "open_work_orders": sum(1 for w in work_orders if w["status"] not in ("completed",)),
            "total_checklists": len(checklists),
            "safety_checks":    len(safety_records),
            "documents":        len(documents),
            "audit_events":     len(audit_entries),
        },
    }


# ── Single object history (defined AFTER /relations/ to avoid shadowing) ──────

@router.get("/{object_type}/{object_id}")
async def get_object_history(object_type: str, object_id: str):
    """Return the full audit history for one specific object."""
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.object_type == object_type,
                m.AuditLog.object_id == object_id,
            )
            .order_by(desc(m.AuditLog.timestamp))
        )
        rows = result.scalars().all()
    return {
        "object_type": object_type,
        "object_id": object_id,
        "event_count": len(rows),
        "history": [_row_to_dict(r) for r in rows],
    }


# ── CSV export ─────────────────────────────────────────────────────────────────

@router.get("/export/csv")
async def export_audit_csv(days: int = Query(30, ge=1, le=365)):
    """Export audit log as CSV for compliance reporting."""
    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(m.AuditLog)
            .where(m.AuditLog.timestamp >= since)
            .order_by(desc(m.AuditLog.timestamp))
            .limit(5000)
        )
        rows = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "Object Type", "Object ID", "Equipment",
                     "Action", "Actor", "Actor Type", "Risk Level", "Notes"])
    for r in rows:
        writer.writerow([
            r.id, r.timestamp.isoformat() if r.timestamp else "",
            r.object_type, r.object_id, r.equipment_id or "",
            r.action, r.actor, r.actor_type, r.risk_level or "", r.notes or "",
        ])

    output.seek(0)
    filename = f"audit_log_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
