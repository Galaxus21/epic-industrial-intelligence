"""
AI Operations Brain — Safety Procedures API
Manage controlled safety documents (SOP, JSA, SWMS, MSDS, ERP).
Approval workflow:
  draft → peer_review → technical_review → final_approval → active → obsolete
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

DOC_TYPES = {"SOP", "JSA", "SWMS", "MSDS", "ERP", "Checklist", "Work_Instruction"}
VALID_STATUSES = [
    "draft", "peer_review", "technical_review", "final_approval", "active", "obsolete"
]
TRANSITIONS: dict[str, list[str]] = {
    "draft":            ["peer_review"],
    "peer_review":      ["technical_review", "draft"],
    "technical_review": ["final_approval", "peer_review"],
    "final_approval":   ["active", "technical_review"],
    "active":           ["obsolete"],
    "obsolete":         [],
}


class ProcedureCreate(BaseModel):
    code: str
    title: str
    version: str = "1.0"
    doc_type: str = "SOP"
    category: str | None = None
    project_id: str | None = None
    plant_id: str | None = None
    equipment_ids: list[str] = []
    steps: list[dict] = []
    hazard_register: list[dict] = []
    ppe_requirements: list[str] = []
    tools_required: list[str] = []
    references: list[str] = []
    tags: list[str] = []
    risk_level: str | None = None
    author_id: str | None = None
    author_name: str | None = None


class ProcedureUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    steps: list[dict] | None = None
    hazard_register: list[dict] | None = None
    ppe_requirements: list[str] | None = None
    tools_required: list[str] | None = None
    references: list[str] | None = None
    tags: list[str] | None = None
    risk_level: str | None = None


class ReviewAction(BaseModel):
    reviewer_id: str
    reviewer_name: str
    decision: str   # approved | rejected
    comments: str = ""


class ApprovalAction(BaseModel):
    approver_id: str
    approver_name: str
    decision: str   # approved | rejected
    comments: str = ""
    effective_date: str | None = None
    review_due_date: str | None = None


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


async def _get(s, proc_id: str) -> m.SafetyProcedure:
    obj = (await s.execute(select(m.SafetyProcedure).where(m.SafetyProcedure.id == proc_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Procedure not found")
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_procedures(
    status: str | None = None,
    doc_type: str | None = None,
    plant_id: str | None = None,
):
    async with AsyncSessionLocal() as s:
        q = select(m.SafetyProcedure)
        if status:
            q = q.where(m.SafetyProcedure.status == status)
        if doc_type:
            q = q.where(m.SafetyProcedure.doc_type == doc_type)
        if plant_id:
            q = q.where(m.SafetyProcedure.plant_id == plant_id)
        rows = (await s.execute(q.order_by(m.SafetyProcedure.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_procedure(body: ProcedureCreate):
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(400, f"Invalid doc_type. Choose from: {sorted(DOC_TYPES)}")
    pid = f"PROC-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        data = body.model_dump()
        data["authored_date"] = _now()
        obj = m.SafetyProcedure(
            id=pid,
            audit_trail=_audit(None, "created", body.author_name or "system"),
            **data,
        )
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{proc_id}")
async def get_procedure(proc_id: str):
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
    return _row(obj)


@router.patch("/{proc_id}")
async def update_procedure(proc_id: str, body: ProcedureUpdate):
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
        if obj.status not in ("draft",):
            raise HTTPException(409, "Can only edit procedures in draft status")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


# ─────────────────────────────────────────────────────────────────────────────
# Approval workflow
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{proc_id}/submit")
async def submit_for_peer_review(proc_id: str, user_id: str, user_name: str):
    """Author submits draft for peer review."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
        if obj.status != "draft":
            raise HTTPException(409, "Only drafts can be submitted for review")
        obj.status = "peer_review"
        obj.audit_trail = _audit(obj.audit_trail, "submitted_for_peer_review", user_name)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{proc_id}/peer-review")
async def peer_review(proc_id: str, body: ReviewAction):
    """Peer reviewer approves or returns to draft."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
        if obj.status != "peer_review":
            raise HTTPException(409, "Procedure is not in peer_review stage")
        obj.peer_reviewer_id = body.reviewer_id
        obj.peer_reviewer_name = body.reviewer_name
        obj.peer_review_decision = body.decision
        obj.peer_review_comments = body.comments
        obj.peer_review_date = _now()
        if body.decision == "approved":
            obj.status = "technical_review"
            obj.audit_trail = _audit(obj.audit_trail, "peer_review_passed", body.reviewer_name, body.comments)
        else:
            obj.status = "draft"
            obj.audit_trail = _audit(obj.audit_trail, "peer_review_rejected", body.reviewer_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{proc_id}/technical-review")
async def technical_review(proc_id: str, body: ReviewAction):
    """Technical reviewer (SME/engineer) approves or sends back."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
        if obj.status != "technical_review":
            raise HTTPException(409, "Procedure is not in technical_review stage")
        obj.tech_reviewer_id = body.reviewer_id
        obj.tech_reviewer_name = body.reviewer_name
        obj.tech_review_decision = body.decision
        obj.tech_review_comments = body.comments
        obj.tech_review_date = _now()
        if body.decision == "approved":
            obj.status = "final_approval"
            obj.audit_trail = _audit(obj.audit_trail, "technical_review_passed", body.reviewer_name, body.comments)
        else:
            obj.status = "peer_review"
            obj.audit_trail = _audit(obj.audit_trail, "technical_review_rejected", body.reviewer_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{proc_id}/approve")
async def final_approval(proc_id: str, body: ApprovalAction):
    """Final approver (safety manager) activates or rejects."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
        if obj.status != "final_approval":
            raise HTTPException(409, "Procedure is not awaiting final approval")
        obj.approver_id = body.approver_id
        obj.approver_name = body.approver_name
        obj.approver_decision = body.decision
        obj.approver_comments = body.comments
        obj.approval_date = _now()
        if body.decision == "approved":
            obj.status = "active"
            obj.effective_date = body.effective_date or _now()
            obj.review_due_date = body.review_due_date
            obj.audit_trail = _audit(obj.audit_trail, "approved_activated", body.approver_name, body.comments)
        else:
            obj.status = "technical_review"
            obj.audit_trail = _audit(obj.audit_trail, "final_approval_rejected", body.approver_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{proc_id}/obsolete")
async def obsolete_procedure(proc_id: str, user_id: str, user_name: str, reason: str = ""):
    """Mark an active procedure as obsolete (superseded by new version)."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
        if obj.status != "active":
            raise HTTPException(409, "Only active procedures can be obsoleted")
        obj.status = "obsolete"
        obj.audit_trail = _audit(obj.audit_trail, "obsoleted", user_name, reason)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.delete("/{proc_id}", status_code=204)
async def delete_procedure(proc_id: str):
    """Delete a procedure (any status)."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
        await s.delete(obj)
        await s.commit()


@router.get("/{proc_id}/audit-trail")
async def get_audit_trail(proc_id: str):
    async with AsyncSessionLocal() as s:
        obj = await _get(s, proc_id)
    return obj.audit_trail or []
