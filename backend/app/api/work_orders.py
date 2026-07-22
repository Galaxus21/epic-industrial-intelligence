"""
AI Operations Brain — Work Orders & Checklists API
Create, track, and complete inspection checklists and work orders from AI query results.
Completion feedback is ingested back into the knowledge base so future AI queries
can learn from real-world outcomes.
"""
import uuid
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services import db_service as db
from app.services.kb_ingestion import (
    on_work_order_created, on_work_order_completed,
    on_checklist_created, on_checklist_completed,
    ingest_async,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class ChecklistCreate(BaseModel):
    equipment_id: str
    query_text: str
    risk_level: str | None = None
    items: list[str]          # plain text items from inspection_checklist


class ChecklistItemUpdate(BaseModel):
    index: int
    checked: bool
    notes: str = ""


class ChecklistComplete(BaseModel):
    outcome_notes: str = ""


class WorkOrderCreate(BaseModel):
    equipment_id: str
    query_text: str
    risk_level: str | None = None
    wo_type: str
    description: str
    estimated_duration_hours: float = 0
    required_technicians: int = 1
    steps: list[dict[str, Any]]
    spare_parts: list[str] = []
    safety_precautions: list[str] = []
    required_permits: list[str] = []


class WorkOrderStepUpdate(BaseModel):
    step_index: int
    checked: bool
    actual_notes: str = ""


class WorkOrderComplete(BaseModel):
    solution_worked: bool | None = None
    extra_steps_taken: str = ""
    outcome_notes: str = ""
    completed_by: str = ""
    actual_duration_hours: float | None = None


class ChecklistUpdate(BaseModel):
    query_text: str | None = None
    risk_level: str | None = None


class WorkOrderUpdate(BaseModel):
    description: str | None = None
    wo_type: str | None = None
    risk_level: str | None = None
    estimated_duration_hours: float | None = None


class OpsAIChat(BaseModel):
    message: str
    history: list[dict[str, str]] = []


class AddChecklistItemsBody(BaseModel):
    items: list[str]


class AddWorkOrderStepsBody(BaseModel):
    steps: list[dict[str, Any]]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict[str, Any]:
    d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


async def _ingest_feedback_as_document(wo: m.SavedWorkOrder) -> None:
    """Store completed work order outcome as a knowledge-base document so the
    AI can learn from it on subsequent queries for this equipment."""
    worked = "YES" if wo.solution_worked else ("NO" if wo.solution_worked is False else "UNKNOWN")
    doc_id = f"FEEDBACK-{wo.id[:8].upper()}"
    name = f"Work Order Outcome: {wo.wo_type} on {wo.equipment_id} ({datetime.utcnow().strftime('%Y-%m-%d')})"

    # Build section text the AI can read
    sections: dict[str, str] = {
        "query": wo.query_text,
        "description": wo.description,
        "solution_worked": f"Solution effective: {worked}",
    }
    if wo.extra_steps_taken:
        sections["extra_steps"] = wo.extra_steps_taken
    if wo.outcome_notes:
        sections["outcome"] = wo.outcome_notes

    completed_steps = [s for s in (wo.steps or []) if s.get("checked")]
    if completed_steps:
        sections["completed_steps"] = "\n".join(
            f"Step {s['step']}: {s['title']} — {s.get('actual_notes', '').strip() or 'completed'}"
            for s in completed_steps
        )

    await db.save_document({
        "id": doc_id,
        "name": name,
        "type": "feedback",
        "equipment_ids": [wo.equipment_id],
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "status": "processed",
        "sections": sections,
        "entities": {
            "equipment_ids": [wo.equipment_id],
            "document_type": "feedback",
            "summary": (
                f"Work order '{wo.wo_type}' for {wo.equipment_id} completed. "
                f"Solution worked: {worked}. "
                f"{len(completed_steps)}/{len(wo.steps or [])} steps executed."
            ),
        },
        "pipeline_steps": {s: "done" for s in ["saved", "extracted", "entities", "graph", "indexed"]},
        "current_step": "done",
    })
    # Link in graph
    await db.upsert_graph_node({
        "id": doc_id,
        "name": f"Feedback\n{wo.equipment_id} {worked}",
        "type": "feedback",
        "val": 12,
    })
    await db.add_graph_link(wo.equipment_id, doc_id, "HAS_FEEDBACK")
    logger.info("Ingested work order feedback as document %s", doc_id)


async def _update_equipment_after_wo(wo: m.SavedWorkOrder) -> None:
    """Write back health/maintenance metrics to the Equipment table after WO completion."""
    eq = await db.get_equipment(wo.equipment_id)
    if not eq:
        return

    updates: dict[str, Any] = {"id": wo.equipment_id}
    wo_type_lower = (wo.wo_type or "").lower()
    worked = wo.solution_worked  # True / False / None

    # Reset maintenance schedule based on work type
    if any(k in wo_type_lower for k in ("preventive", "inspection", "pm")):
        updates["maintenance_due_days"] = 30
    elif "emergency" in wo_type_lower:
        updates["maintenance_due_days"] = 7   # recheck soon after emergency fix
    else:                                       # corrective / other
        updates["maintenance_due_days"] = 14

    # Improve health score if fix worked
    health = eq.get("health_score")
    if health is not None:
        if worked is True:
            updates["health_score"] = min(float(health) + 15.0, 95.0)
        elif worked is None:  # partial / unknown
            updates["health_score"] = min(float(health) + 5.0, 90.0)

    # Reduce failure probability
    fp = eq.get("failure_probability")
    if fp is not None:
        if worked is True:
            updates["failure_probability"] = max(float(fp) - 15.0, 2.0)
        else:
            updates["failure_probability"] = max(float(fp) - 5.0, 2.0)

    # Clear active alert status if solution worked
    status = eq.get("status") or ""
    if worked is True and ("alert" in status.lower() or "alarm" in status.lower()):
        updates["status"] = "Normal Operation"

    await db.upsert_equipment(updates)
    logger.info(
        "Updated equipment %s after WO completion (health=%s fp=%s maint_days=%s)",
        wo.equipment_id,
        updates.get("health_score"), updates.get("failure_probability"), updates.get("maintenance_due_days"),
    )


async def _update_equipment_after_checklist(cl: m.SavedChecklist) -> None:
    """Minor equipment metric update after checklist completion (inspection confirms state)."""
    eq = await db.get_equipment(cl.equipment_id)
    if not eq:
        return
    fp = eq.get("failure_probability")
    if fp is not None and float(fp) > 5:
        await db.upsert_equipment({
            "id": cl.equipment_id,
            "failure_probability": max(float(fp) - 3.0, 2.0),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Checklist endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/checklists")
async def list_checklists(equipment_id: str | None = None):
    async with AsyncSessionLocal() as s:
        q = select(m.SavedChecklist).order_by(m.SavedChecklist.created_at.desc())
        if equipment_id:
            q = q.where(m.SavedChecklist.equipment_id == equipment_id)
        result = await s.execute(q)
        return [_row_to_dict(r) for r in result.scalars().all()]


@router.post("/checklists", status_code=201)
async def create_checklist(body: ChecklistCreate):
    cl_id = f"CL-{uuid.uuid4().hex[:8].upper()}"
    items = [{"text": t, "checked": False, "notes": ""} for t in body.items]
    record = m.SavedChecklist(
        id=cl_id,
        equipment_id=body.equipment_id,
        query_text=body.query_text,
        risk_level=body.risk_level,
        status="open",
        items=items,
    )
    async with AsyncSessionLocal() as s:
        s.add(record)
        await s.commit()
        await s.refresh(record)
    # ── KB: register checklist in knowledge graph ──
    ingest_async(on_checklist_created(cl_id, body.equipment_id, body.risk_level, body.items))
    return _row_to_dict(record)


@router.get("/checklists/{cl_id}")
async def get_checklist(cl_id: str):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedChecklist, cl_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return _row_to_dict(row)


@router.patch("/checklists/{cl_id}/item")
async def update_checklist_item(cl_id: str, body: ChecklistItemUpdate):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedChecklist, cl_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Checklist not found")
        items = list(row.items or [])
        if body.index < 0 or body.index >= len(items):
            raise HTTPException(status_code=400, detail="Invalid item index")
        items[body.index] = {**items[body.index], "checked": body.checked, "notes": body.notes}
        row.items = items
        row.status = "in_progress" if any(i["checked"] for i in items) else "open"
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)


@router.post("/checklists/{cl_id}/complete")
async def complete_checklist(cl_id: str, body: ChecklistComplete):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedChecklist, cl_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Checklist not found")
        row.status = "completed"
        row.outcome_notes = body.outcome_notes
        row.completed_at = datetime.utcnow()
        await s.commit()
        await s.refresh(row)
    await _update_equipment_after_checklist(row)
    # ── KB: ingest completed inspection into knowledge base ──
    ingest_async(on_checklist_completed(
        cl_id=row.id,
        equipment_id=row.equipment_id,
        risk_level=row.risk_level,
        items=list(row.items or []),
        outcome_notes=body.outcome_notes or None,
    ))
    return _row_to_dict(row)


@router.patch("/checklists/{cl_id}")
async def update_checklist_meta(cl_id: str, body: ChecklistUpdate):
    """Edit checklist metadata (query text, risk level)."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedChecklist, cl_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Checklist not found")
        if body.query_text is not None:
            row.query_text = body.query_text
        if body.risk_level is not None:
            row.risk_level = body.risk_level or None
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)


@router.delete("/checklists/{cl_id}", status_code=204)
async def delete_checklist(cl_id: str):
    """Permanently delete a checklist."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedChecklist, cl_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Checklist not found")
        await s.delete(row)
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Work order endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/work-orders")
async def list_work_orders(equipment_id: str | None = None):
    async with AsyncSessionLocal() as s:
        q = select(m.SavedWorkOrder).order_by(m.SavedWorkOrder.created_at.desc())
        if equipment_id:
            q = q.where(m.SavedWorkOrder.equipment_id == equipment_id)
        result = await s.execute(q)
        return [_row_to_dict(r) for r in result.scalars().all()]


@router.post("/work-orders", status_code=201)
async def create_work_order(body: WorkOrderCreate):
    wo_id = f"WO-{uuid.uuid4().hex[:8].upper()}"
    # Enrich steps with tracking fields
    steps = [
        {**step, "checked": False, "actual_notes": ""}
        for step in body.steps
    ]
    record = m.SavedWorkOrder(
        id=wo_id,
        equipment_id=body.equipment_id,
        query_text=body.query_text,
        risk_level=body.risk_level,
        wo_type=body.wo_type,
        description=body.description,
        estimated_duration_hours=body.estimated_duration_hours,
        required_technicians=body.required_technicians,
        status="open",
        steps=steps,
        spare_parts=body.spare_parts,
        safety_precautions=body.safety_precautions,
        required_permits=body.required_permits,
    )
    async with AsyncSessionLocal() as s:
        s.add(record)
        await s.commit()
        await s.refresh(record)
    # ── KB: register new work order in knowledge graph ──
    ingest_async(on_work_order_created(
        wo_id=wo_id,
        equipment_id=body.equipment_id,
        wo_type=body.wo_type,
        description=body.description,
        risk_level=body.risk_level,
        spare_parts=body.spare_parts,
        safety_precautions=body.safety_precautions,
        required_permits=body.required_permits,
    ))
    return _row_to_dict(record)


@router.get("/work-orders/{wo_id}")
async def get_work_order(wo_id: str):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedWorkOrder, wo_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    return _row_to_dict(row)


@router.patch("/work-orders/{wo_id}/step")
async def update_work_order_step(wo_id: str, body: WorkOrderStepUpdate):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedWorkOrder, wo_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        steps = list(row.steps or [])
        if body.step_index < 0 or body.step_index >= len(steps):
            raise HTTPException(status_code=400, detail="Invalid step index")
        steps[body.step_index] = {
            **steps[body.step_index],
            "checked": body.checked,
            "actual_notes": body.actual_notes,
        }
        row.steps = steps
        row.status = "in_progress" if any(step.get("checked") for step in steps) else "open"
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)


@router.post("/work-orders/{wo_id}/complete")
async def complete_work_order(wo_id: str, body: WorkOrderComplete):
    """Mark work order complete and ingest outcome feedback into the knowledge base."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedWorkOrder, wo_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        row.status = "completed"
        row.solution_worked = body.solution_worked
        row.extra_steps_taken = body.extra_steps_taken or None
        row.outcome_notes = body.outcome_notes or None
        row.completed_by = body.completed_by or None
        row.actual_duration_hours = body.actual_duration_hours
        row.completed_at = datetime.utcnow()
        await s.commit()
        await s.refresh(row)
        # Legacy metric update (kept)
        await _ingest_feedback_as_document(row)
        await _update_equipment_after_wo(row)
        # ── KB: full knowledge ingestion (lessons learned + graph) ──
        ingest_async(on_work_order_completed(
            wo_id=row.id,
            equipment_id=row.equipment_id,
            wo_type=row.wo_type or "Corrective",
            description=row.description or "",
            risk_level=row.risk_level,
            solution_worked=row.solution_worked,
            outcome_notes=row.outcome_notes,
            extra_steps_taken=row.extra_steps_taken,
            completed_by=row.completed_by,
            actual_duration_hours=row.actual_duration_hours,
            steps=list(row.steps or []),
            spare_parts=list(row.spare_parts or []),
        ))
    return _row_to_dict(row)


@router.patch("/work-orders/{wo_id}")
async def update_work_order_meta(wo_id: str, body: WorkOrderUpdate):
    """Edit work order metadata (description, type, risk, duration)."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedWorkOrder, wo_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        if body.description is not None:
            row.description = body.description
        if body.wo_type is not None:
            row.wo_type = body.wo_type
        if body.risk_level is not None:
            row.risk_level = body.risk_level or None
        if body.estimated_duration_hours is not None:
            row.estimated_duration_hours = body.estimated_duration_hours
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)


@router.delete("/work-orders/{wo_id}", status_code=204)
async def delete_work_order(wo_id: str):
    """Permanently delete a work order."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedWorkOrder, wo_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        await s.delete(row)
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# AI Chat endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/work-orders/{wo_id}/chat")
async def chat_with_work_order(wo_id: str, body: OpsAIChat):
    """AI assistant for a work order — answers questions and proposes changes."""
    async with AsyncSessionLocal() as s:
        wo = await s.get(m.SavedWorkOrder, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    eq = await db.get_equipment(wo.equipment_id) or {}
    from app.services.llm_service import chat_with_ops_item
    return await chat_with_ops_item(
        item_type="work_order",
        item_data=_row_to_dict(wo),
        equipment_context=eq,
        message=body.message,
        history=body.history,
    )


@router.post("/checklists/{cl_id}/chat")
async def chat_with_checklist_ai(cl_id: str, body: OpsAIChat):
    """AI assistant for a checklist — answers questions and proposes changes."""
    async with AsyncSessionLocal() as s:
        cl = await s.get(m.SavedChecklist, cl_id)
    if cl is None:
        raise HTTPException(status_code=404, detail="Checklist not found")
    eq = await db.get_equipment(cl.equipment_id) or {}
    from app.services.llm_service import chat_with_ops_item
    return await chat_with_ops_item(
        item_type="checklist",
        item_data=_row_to_dict(cl),
        equipment_context=eq,
        message=body.message,
        history=body.history,
    )


@router.post("/checklists/{cl_id}/items/add")
async def add_checklist_items(cl_id: str, body: AddChecklistItemsBody):
    """Append AI-proposed items to a checklist."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedChecklist, cl_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Checklist not found")
        existing = list(row.items or [])
        for text in body.items:
            existing.append({"text": text, "checked": False, "notes": ""})
        row.items = existing
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)


@router.post("/work-orders/{wo_id}/steps/add")
async def add_work_order_steps(wo_id: str, body: AddWorkOrderStepsBody):
    """Append AI-proposed steps to a work order."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedWorkOrder, wo_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        existing = list(row.steps or [])
        next_num = max((sd.get("step", 0) for sd in existing), default=0) + 1
        for sd in body.steps:
            existing.append({**sd, "step": next_num, "checked": False, "actual_notes": ""})
            next_num += 1
        row.steps = existing
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)
