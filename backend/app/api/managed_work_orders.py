"""
AI Operations Brain — Managed Work Orders API
Full approval workflow:
  draft → submitted → pending_approval → approved → scheduled
        → in_progress → pending_verification → verified → closed

One person creates; a different person (supervisor) approves.
A different person from the completer verifies completion.
Every transition is recorded in audit_trail.
"""
import uuid
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)
router = APIRouter()

TRANSITIONS: dict[str, list[str]] = {
    "draft":               ["submitted", "cancelled"],
    "submitted":           ["pending_approval", "draft"],
    "pending_approval":    ["approved", "rejected", "draft"],
    "approved":            ["scheduled", "cancelled"],
    "scheduled":           ["in_progress", "cancelled"],
    "in_progress":         ["pending_verification"],
    "pending_verification": ["verified", "in_progress"],
    "verified":            ["closed"],
    "closed":              [],
    "rejected":            ["draft"],
    "cancelled":           [],
}


class MWOCreate(BaseModel):
    title: str
    description: str = ""
    category: str = "corrective"
    priority: str = "medium"
    project_id: str | None = None
    plant_id: str | None = None
    equipment_ids: list[str] = []
    permit_id: str | None = None
    scheduled_start: str | None = None
    scheduled_end: str | None = None
    estimated_hours: float | None = None
    tasks: list[dict] = []
    materials: list[dict] = []
    safety_requirements: list[str] = []
    created_by_id: str | None = None
    created_by_name: str | None = None


class MWOUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    category: str | None = None
    scheduled_start: str | None = None
    scheduled_end: str | None = None
    estimated_hours: float | None = None
    tasks: list[dict] | None = None
    materials: list[dict] | None = None
    safety_requirements: list[str] | None = None
    permit_id: str | None = None


class ApprovalBody(BaseModel):
    approver_id: str
    approver_name: str
    decision: str    # approved | rejected
    comments: str = ""


class AssignBody(BaseModel):
    assigned_to: list[dict]   # [{id, name, role}]
    scheduled_start: str | None = None
    scheduled_end: str | None = None


class StartBody(BaseModel):
    started_by_id: str
    started_by_name: str


class TaskUpdateBody(BaseModel):
    task_index: int
    status: str   # pending | in_progress | completed | skipped
    notes: str = ""


class CompleteBody(BaseModel):
    completed_by_id: str
    completed_by_name: str
    completion_notes: str = ""
    actual_hours: float | None = None


class VerifyBody(BaseModel):
    verified_by_id: str
    verified_by_name: str
    decision: str    # passed | failed
    comments: str = ""


def _row(obj) -> dict[str, Any]:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _audit(trail: list | None, action: str, user: str, comments: str = "") -> list:
    trail = list(trail or [])
    trail.append({
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user": user,
        "comments": comments,
    })
    return trail


def _now() -> str:
    return datetime.utcnow().isoformat()


def _assert_transition(current: str, target: str):
    if target not in TRANSITIONS.get(current, []):
        raise HTTPException(409, f"Cannot move work order from '{current}' to '{target}'")


async def _get(s, wo_id: str) -> m.ManagedWorkOrder:
    obj = (await s.execute(select(m.ManagedWorkOrder).where(m.ManagedWorkOrder.id == wo_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Work order not found")
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_work_orders(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    project_id: str | None = None,
    plant_id: str | None = None,
):
    async with AsyncSessionLocal() as s:
        q = select(m.ManagedWorkOrder)
        if status:
            q = q.where(m.ManagedWorkOrder.status == status)
        if priority:
            q = q.where(m.ManagedWorkOrder.priority == priority)
        if category:
            q = q.where(m.ManagedWorkOrder.category == category)
        if project_id:
            q = q.where(m.ManagedWorkOrder.project_id == project_id)
        if plant_id:
            q = q.where(m.ManagedWorkOrder.plant_id == plant_id)
        rows = (await s.execute(q.order_by(m.ManagedWorkOrder.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_work_order(body: MWOCreate):
    wid = f"MWO-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        count = len((await s.execute(select(m.ManagedWorkOrder))).scalars().all())
        wo_number = f"WO-{datetime.utcnow().year}-{str(count + 1).zfill(4)}"
        obj = m.ManagedWorkOrder(
            id=wid,
            wo_number=wo_number,
            audit_trail=_audit(None, "created", body.created_by_name or "system"),
            **body.model_dump(),
        )
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{wo_id}")
async def get_work_order(wo_id: str):
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
    return _row(obj)


@router.patch("/{wo_id}")
async def update_work_order(wo_id: str, body: MWOUpdate):
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        if obj.status not in ("draft", "rejected"):
            raise HTTPException(409, "Can only edit work orders in draft or rejected status")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


# ─────────────────────────────────────────────────────────────────────────────
# Workflow transitions
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{wo_id}/submit")
async def submit_work_order(wo_id: str, user_id: str, user_name: str):
    """Creator submits the work order for supervisor approval."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        _assert_transition(obj.status, "submitted")
        obj.status = "submitted"
        obj.audit_trail = _audit(obj.audit_trail, "submitted", user_name, "Submitted for approval")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{wo_id}/approve")
async def approve_work_order(wo_id: str, body: ApprovalBody):
    """Supervisor approves or rejects. Must be a different user from creator."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        if obj.status not in ("submitted", "pending_approval"):
            raise HTTPException(409, f"Work order is not awaiting approval (current: {obj.status})")
        # Prevent same person approving their own WO
        if body.approver_id and body.approver_id == obj.created_by_id:
            raise HTTPException(403, "Approver cannot be the same as creator")
        obj.approver_id = body.approver_id
        obj.approver_name = body.approver_name
        obj.approval_decision = body.decision
        obj.approval_comments = body.comments
        obj.approval_date = _now()
        if body.decision == "approved":
            obj.status = "approved"
            obj.audit_trail = _audit(obj.audit_trail, "approved", body.approver_name, body.comments)
        else:
            obj.status = "rejected"
            obj.audit_trail = _audit(obj.audit_trail, "rejected", body.approver_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{wo_id}/assign")
async def assign_work_order(wo_id: str, body: AssignBody):
    """Schedule and assign technicians to an approved work order."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        if obj.status not in ("approved", "scheduled"):
            raise HTTPException(409, "Work order must be approved before assigning")
        obj.assigned_to = body.assigned_to
        if body.scheduled_start:
            obj.scheduled_start = body.scheduled_start
        if body.scheduled_end:
            obj.scheduled_end = body.scheduled_end
        obj.status = "scheduled"
        obj.audit_trail = _audit(
            obj.audit_trail, "scheduled",
            ",".join(a.get("name", "") for a in body.assigned_to),
            f"Assigned to: {[a.get('name') for a in body.assigned_to]}"
        )
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{wo_id}/start")
async def start_work_order(wo_id: str, body: StartBody):
    """Technician starts work execution."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        _assert_transition(obj.status, "in_progress")
        obj.status = "in_progress"
        obj.started_by_id = body.started_by_id
        obj.started_by_name = body.started_by_name
        obj.actual_start = _now()
        obj.audit_trail = _audit(obj.audit_trail, "started", body.started_by_name, "Work execution started")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{wo_id}/update-task")
async def update_task(wo_id: str, body: TaskUpdateBody):
    """Update individual task status during execution."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        tasks = list(obj.tasks or [])
        if body.task_index >= len(tasks):
            raise HTTPException(400, "Invalid task_index")
        tasks[body.task_index]["status"] = body.status
        tasks[body.task_index]["notes"] = body.notes
        obj.tasks = tasks
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{wo_id}/complete")
async def complete_work_order(wo_id: str, body: CompleteBody):
    """Technician marks work as complete; awaits supervisor verification."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        _assert_transition(obj.status, "pending_verification")
        obj.status = "pending_verification"
        obj.completed_by_id = body.completed_by_id
        obj.completed_by_name = body.completed_by_name
        obj.completed_at = _now()
        obj.completion_notes = body.completion_notes
        if body.actual_hours:
            obj.actual_hours = body.actual_hours
        obj.audit_trail = _audit(
            obj.audit_trail, "completed", body.completed_by_name,
            f"Work completed. Notes: {body.completion_notes}"
        )
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{wo_id}/verify")
async def verify_work_order(wo_id: str, body: VerifyBody):
    """Supervisor verifies completion. Must be different from the completer."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        _assert_transition(obj.status, "verified" if body.decision == "passed" else "in_progress")
        # Prevent the same person verifying their own completion
        if body.verified_by_id and body.verified_by_id == obj.completed_by_id:
            raise HTTPException(403, "Verifier cannot be the same as the person who completed the work")
        obj.verified_by_id = body.verified_by_id
        obj.verified_by_name = body.verified_by_name
        obj.verification_decision = body.decision
        obj.verification_comments = body.comments
        obj.verified_at = _now()
        if body.decision == "passed":
            obj.status = "verified"
            obj.audit_trail = _audit(obj.audit_trail, "verified", body.verified_by_name, body.comments)
        else:
            obj.status = "in_progress"
            obj.audit_trail = _audit(obj.audit_trail, "verification_failed", body.verified_by_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{wo_id}/close")
async def close_work_order(wo_id: str, user_id: str, user_name: str):
    """Close a verified work order."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
        _assert_transition(obj.status, "closed")
        obj.status = "closed"
        obj.audit_trail = _audit(obj.audit_trail, "closed", user_name, "Work order closed")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{wo_id}/audit-trail")
async def get_audit_trail(wo_id: str):
    async with AsyncSessionLocal() as s:
        obj = await _get(s, wo_id)
    return obj.audit_trail or []
