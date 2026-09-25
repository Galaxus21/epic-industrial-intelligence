"""
AI Operations Brain — Work Orders API
Create, track, and complete work orders from AI query results.
Completion feedback is ingested back into the knowledge base so future AI queries
can learn from real-world outcomes.
"""
import uuid
import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.chatTurn import MAX_MESSAGE_CHARS, ChatHistory, historyDicts
from app.core.auth import get_current_user, require_roles
from app.core.roles import APPROVER_ROLES, FIELD_ROLES
from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services import db_service as db
from app.services.workOrderOutcome import equipmentUpdatesAfterWorkOrder
from app.services.workOrderProposals import (
    MAX_LABEL_CHARS, MAX_NOTE_CHARS, MAX_STEPS, MAX_TEXT_CHARS, MAX_TITLE_CHARS, ProposedStep, RiskLevel,
    permittedProposal,
)
from app.services.kb_ingestion import (
    on_work_order_created, on_work_order_completed, on_work_order_deleted,
    ingest_async,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_ID_CHARS = 64
COMPLETED = "completed"
CONFLICT = 409
MAX_WORK_ORDER_HOURS = 1000
MAX_TECHNICIANS = 50
ShortLine = Annotated[str, Field(max_length=MAX_TITLE_CHARS)]
NoteLine = Annotated[str, Field(max_length=MAX_NOTE_CHARS)]


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class WorkOrderCreate(BaseModel):
    """A work order as the browser saves it from an AI answer: every field is bounded and steps are validated."""

    equipment_id: str = Field(min_length=1, max_length=MAX_ID_CHARS)
    query_text: str = Field("", max_length=MAX_TEXT_CHARS)
    risk_level: RiskLevel | None = None
    wo_type: str = Field(min_length=1, max_length=MAX_LABEL_CHARS)
    description: str = Field("", max_length=MAX_TEXT_CHARS)
    estimated_duration_hours: float = Field(0, ge=0, le=MAX_WORK_ORDER_HOURS)
    required_technicians: int = Field(1, ge=1, le=MAX_TECHNICIANS)
    steps: list[ProposedStep] = Field(default_factory=list, max_length=MAX_STEPS)
    spare_parts: list[ShortLine] = Field(default_factory=list, max_length=MAX_STEPS)
    safety_precautions: list[NoteLine] = Field(default_factory=list, max_length=MAX_STEPS)
    required_permits: list[ShortLine] = Field(default_factory=list, max_length=MAX_STEPS)


class WorkOrderStepUpdate(BaseModel):
    step_index: int
    checked: bool
    actual_notes: str = Field("", max_length=MAX_TEXT_CHARS)


class WorkOrderComplete(BaseModel):
    solution_worked: bool | None = None
    is_partial: bool | None = False
    extra_steps_taken: str = ""
    outcome_notes: str = ""
    completed_by: str | None = None
    actual_duration_hours: float | None = Field(None, ge=0)


class WorkOrderUpdate(BaseModel):
    description: str | None = Field(None, max_length=MAX_TEXT_CHARS)
    wo_type: str | None = Field(None, max_length=MAX_LABEL_CHARS)
    risk_level: RiskLevel | None = None
    estimated_duration_hours: float | None = Field(None, ge=0)


class OpsAIChat(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: ChatHistory = []


class AddWorkOrderStepsBody(BaseModel):
    steps: list[ProposedStep] = Field(min_length=1, max_length=MAX_STEPS)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict[str, Any]:
    d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


async def _openWorkOrder(session, wo_id: str) -> m.SavedWorkOrder:
    """The work order, locked for this change. A completed one is closed: re-completing it would apply its outcome
    to the equipment twice, and ticking a step would move it back to in_progress."""
    row = await session.get(m.SavedWorkOrder, wo_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    if row.status == COMPLETED:
        raise HTTPException(status_code=CONFLICT, detail="Work order is already completed")
    return row


async def _update_equipment_after_wo(wo: m.SavedWorkOrder) -> None:
    """Write back health/maintenance metrics to the Equipment table after WO completion (workOrderOutcome.py)."""
    eq = await db.get_equipment(wo.equipment_id)
    if not eq:
        return
    updates = equipmentUpdatesAfterWorkOrder(eq, wo.wo_type or "", wo.solution_worked)
    await db.upsert_equipment(updates)
    logger.info(
        "Updated equipment %s after WO completion (health=%s fp=%s maint_days=%s)",
        wo.equipment_id,
        updates.get("health_score"), updates.get("failure_probability"), updates.get("maintenance_due_days"),
    )


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
async def create_work_order(
    body: WorkOrderCreate,
    user: m.UserProfile = Depends(get_current_user),
):
    if await db.get_equipment(body.equipment_id) is None:
        raise HTTPException(status_code=422, detail=f"equipment_id '{body.equipment_id}' is not registered equipment")
    wo_id = f"WO-{uuid.uuid4().hex[:8].upper()}"
    steps = [
        {"step": position, **step.model_dump(exclude_none=True), "checked": False, "actual_notes": ""}
        for position, step in enumerate(body.steps, start=1)
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
        actor=user.name,
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
async def update_work_order_step(
    wo_id: str,
    body: WorkOrderStepUpdate,
    user: m.UserProfile = Depends(require_roles(*FIELD_ROLES)),
):
    async with AsyncSessionLocal() as s:
        row = await _openWorkOrder(s, wo_id)
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
async def complete_work_order(
    wo_id: str,
    body: WorkOrderComplete,
    user: m.UserProfile = Depends(require_roles(*FIELD_ROLES)),
):
    """Mark work order complete and ingest outcome feedback into the knowledge base."""
    async with AsyncSessionLocal() as s:
        row = await _openWorkOrder(s, wo_id)
        row.status = COMPLETED
        row.solution_worked = body.solution_worked
        row.is_partial = bool(body.is_partial)
        row.extra_steps_taken = body.extra_steps_taken or None
        row.outcome_notes = body.outcome_notes or None
        # Actor identity is derived strictly from the authenticated principal
        row.completed_by = user.name
        row.actual_duration_hours = body.actual_duration_hours
        row.completed_at = datetime.utcnow()
        await s.commit()
        await s.refresh(row)
        await _update_equipment_after_wo(row)
        # ── KB: full knowledge ingestion (lessons learned + graph) ──
        ingest_async(on_work_order_completed(
            wo_id=row.id,
            equipment_id=row.equipment_id,
            wo_type=row.wo_type or "Corrective",
            description=row.description or "",
            risk_level=row.risk_level,
            solution_worked=row.solution_worked,
            is_partial=row.is_partial,
            outcome_notes=row.outcome_notes,
            extra_steps_taken=row.extra_steps_taken,
            completed_by=user.name,
            actual_duration_hours=row.actual_duration_hours,
            steps=list(row.steps or []),
            spare_parts=list(row.spare_parts or []),
        ))
    return _row_to_dict(row)


@router.patch("/work-orders/{wo_id}")
async def update_work_order_meta(
    wo_id: str,
    body: WorkOrderUpdate,
    user: m.UserProfile = Depends(require_roles(*APPROVER_ROLES)),
):
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
async def delete_work_order(
    wo_id: str,
    user: m.UserProfile = Depends(require_roles(*APPROVER_ROLES)),
):
    """Permanently delete a work order, and cancel the maintenance record that listed it as scheduled work."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SavedWorkOrder, wo_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        await on_work_order_deleted(wo_id, row.equipment_id, completed=row.status == COMPLETED)
        await s.delete(row)
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# AI Chat endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/work-orders/{wo_id}/chat")
async def chat_with_work_order(
    wo_id: str,
    body: OpsAIChat,
    user: m.UserProfile = Depends(get_current_user),
):
    """AI assistant for a work order — answers questions and proposes changes.

    The proposal is validated and cut to what the caller's role may apply (workOrderProposals); the fields a role
    may not apply are named in withheld_changes, so the UI can say who has to make them."""
    async with AsyncSessionLocal() as s:
        wo = await s.get(m.SavedWorkOrder, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    brain = await db.get_equipment_brain(wo.equipment_id)
    from app.services.llm_service import chat_with_ops_item
    reply = await chat_with_ops_item(
        item_type="work_order",
        item_data=_row_to_dict(wo),
        equipment_context=brain,
        message=body.message,
        history=historyDicts(body.history),
        userRole=user.role,
    )
    proposal, withheld = permittedProposal(reply.get("proposed_changes"), user.role, len(wo.steps or []))
    return {**reply, "proposed_changes": proposal, "withheld_changes": withheld}




@router.post("/work-orders/{wo_id}/steps/add")
async def add_work_order_steps(
    wo_id: str,
    body: AddWorkOrderStepsBody,
    user: m.UserProfile = Depends(require_roles(*FIELD_ROLES)),
):
    """Append AI-proposed steps to a work order."""
    async with AsyncSessionLocal() as s:
        row = await _openWorkOrder(s, wo_id)
        existing = list(row.steps or [])
        next_num = max((sd.get("step", 0) for sd in existing), default=0) + 1
        for sd in body.steps:
            existing.append({**sd.model_dump(exclude_none=True), "step": next_num, "checked": False, "actual_notes": ""})
            next_num += 1
        row.steps = existing
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)
