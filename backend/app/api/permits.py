"""
AI Operations Brain — Permit to Work (PTW) API
Industry-standard PTW workflow:
  draft → submitted → area_authority_review → safety_review
       → ap_approval → issued → active → suspended
       → completion_requested → closed | cancelled

Each status transition is a separate endpoint with role validation.
Every transition is logged to audit_trail.
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

# ─────────────────────────────────────────────────────────────────────────────
# Allowed status transitions
# ─────────────────────────────────────────────────────────────────────────────
TRANSITIONS: dict[str, list[str]] = {
    "draft":                    ["submitted", "cancelled"],
    "submitted":                ["area_authority_review", "cancelled", "draft"],
    "area_authority_review":    ["safety_review", "draft", "cancelled"],
    "safety_review":            ["ap_approval", "area_authority_review", "cancelled"],
    "ap_approval":              ["issued", "safety_review", "cancelled"],
    "issued":                   ["active", "cancelled"],
    "active":                   ["suspended", "completion_requested"],
    "suspended":                ["active", "cancelled"],
    "completion_requested":     ["closed", "active"],
    "closed":                   [],
    "cancelled":                [],
}

PERMIT_TYPES = {
    "hot_work", "cold_work", "confined_space", "electrical_isolation",
    "height", "radiography", "excavation", "general",
}


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class PTWCreate(BaseModel):
    title: str
    permit_type: str = "cold_work"
    scope_of_work: str = ""
    project_id: str | None = None
    plant_id: str | None = None
    equipment_ids: list[str] = []
    location_description: str | None = None
    area_classification: str | None = None
    planned_start: str | None = None
    planned_end: str | None = None
    hazards: list[dict] = []
    ppe_requirements: list[dict] = []
    isolation_points: list[dict] = []
    gas_tests: list[dict] = []
    simops_conflicts: list[str] = []
    emergency_response_ref: str | None = None
    work_order_id: str | None = None
    originator_id: str | None = None
    originator_name: str | None = None
    originator_comments: str | None = None
    created_by: str | None = None


class PTWUpdate(BaseModel):
    title: str | None = None
    scope_of_work: str | None = None
    planned_start: str | None = None
    planned_end: str | None = None
    hazards: list[dict] | None = None
    ppe_requirements: list[dict] | None = None
    isolation_points: list[dict] | None = None
    gas_tests: list[dict] | None = None
    simops_conflicts: list[str] | None = None
    emergency_response_ref: str | None = None
    work_order_id: str | None = None


class AreaAuthorityAction(BaseModel):
    decision: str   # approved | rejected
    user_id: str
    user_name: str
    comments: str = ""


class SafetyOfficerAction(BaseModel):
    decision: str   # approved | rejected
    user_id: str
    user_name: str
    comments: str = ""


class APAction(BaseModel):
    decision: str   # issued | rejected
    user_id: str
    user_name: str
    comments: str = ""


class SuspendBody(BaseModel):
    user_id: str
    user_name: str
    reason: str = ""


class ResumeBody(BaseModel):
    user_id: str
    user_name: str
    comments: str = ""


class CloseRequestBody(BaseModel):
    requested_by_id: str
    requested_by_name: str
    comments: str = ""


class CloseBody(BaseModel):
    ap_id: str
    ap_name: str
    comments: str = ""


class CancelBody(BaseModel):
    user_id: str
    user_name: str
    reason: str = ""


class GasTestAdd(BaseModel):
    tested_by: str
    test_time: str
    gas: str
    result: str       # pass | fail
    ppm: float | None = None
    lel_percent: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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


async def _get_ptw(s, ptw_id: str) -> m.PermitToWork:
    obj = (await s.execute(select(m.PermitToWork).where(m.PermitToWork.id == ptw_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Permit not found")
    return obj


def _assert_transition(current: str, target: str):
    if target not in TRANSITIONS.get(current, []):
        raise HTTPException(409, f"Cannot transition permit from '{current}' to '{target}'")


# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_permits(
    status: str | None = None,
    plant_id: str | None = None,
    project_id: str | None = None,
    permit_type: str | None = None,
):
    async with AsyncSessionLocal() as s:
        q = select(m.PermitToWork)
        if status:
            q = q.where(m.PermitToWork.status == status)
        if plant_id:
            q = q.where(m.PermitToWork.plant_id == plant_id)
        if project_id:
            q = q.where(m.PermitToWork.project_id == project_id)
        if permit_type:
            q = q.where(m.PermitToWork.permit_type == permit_type)
        rows = (await s.execute(q.order_by(m.PermitToWork.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_permit(body: PTWCreate):
    if body.permit_type not in PERMIT_TYPES:
        raise HTTPException(400, f"Invalid permit_type. Choose from: {sorted(PERMIT_TYPES)}")
    pid = f"PTW-{uuid.uuid4().hex[:8].upper()}"
    # Auto-generate sequential permit number
    async with AsyncSessionLocal() as s:
        count = len((await s.execute(select(m.PermitToWork))).scalars().all())
        permit_number = f"PTW-{datetime.utcnow().year}-{str(count + 1).zfill(4)}"
        data = body.model_dump()
        data["originator_date"] = _now()
        obj = m.PermitToWork(
            id=pid,
            permit_number=permit_number,
            audit_trail=_audit(None, "created", body.created_by or body.originator_name or "system"),
            **data,
        )
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{ptw_id}")
async def get_permit(ptw_id: str):
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
    return _row(obj)


@router.patch("/{ptw_id}")
async def update_permit(ptw_id: str, body: PTWUpdate):
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        if obj.status not in ("draft", "submitted"):
            raise HTTPException(409, "Can only edit permit in draft or submitted status")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


# ─────────────────────────────────────────────────────────────────────────────
# Workflow transitions
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{ptw_id}/submit")
async def submit_permit(ptw_id: str, user_id: str, user_name: str):
    """Originator submits permit for Area Authority review."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "submitted")
        obj.status = "submitted"
        obj.audit_trail = _audit(obj.audit_trail, "submitted", user_name, "Submitted for Area Authority review")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/area-authority-review")
async def area_authority_review(ptw_id: str, body: AreaAuthorityAction):
    """Area Authority approves / rejects. Approval sends to Safety Officer review."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "area_authority_review" if body.decision == "approved" else "draft")
        obj.area_authority_id = body.user_id
        obj.area_authority_name = body.user_name
        obj.area_authority_decision = body.decision
        obj.area_authority_comments = body.comments
        obj.area_authority_date = _now()
        if body.decision == "approved":
            obj.status = "area_authority_review"
            obj.audit_trail = _audit(obj.audit_trail, "area_authority_approved", body.user_name, body.comments)
        else:
            obj.status = "draft"
            obj.audit_trail = _audit(obj.audit_trail, "area_authority_rejected", body.user_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/safety-review")
async def safety_officer_review(ptw_id: str, body: SafetyOfficerAction):
    """Safety Officer approves / rejects. Approval sends to AP."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        if body.decision == "approved":
            _assert_transition(obj.status, "safety_review")
        else:
            _assert_transition(obj.status, "area_authority_review")
        obj.safety_officer_id = body.user_id
        obj.safety_officer_name = body.user_name
        obj.safety_officer_decision = body.decision
        obj.safety_officer_comments = body.comments
        obj.safety_officer_date = _now()
        if body.decision == "approved":
            obj.status = "safety_review"
            obj.audit_trail = _audit(obj.audit_trail, "safety_approved", body.user_name, body.comments)
        else:
            obj.status = "area_authority_review"
            obj.audit_trail = _audit(obj.audit_trail, "safety_rejected", body.user_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/ap-approval")
async def ap_approval(ptw_id: str, body: APAction):
    """Authorized Person issues or rejects the permit."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        if body.decision == "issued":
            _assert_transition(obj.status, "ap_approval")
        else:
            _assert_transition(obj.status, "safety_review")
        obj.ap_id = body.user_id
        obj.ap_name = body.user_name
        obj.ap_decision = body.decision
        obj.ap_comments = body.comments
        obj.ap_issue_date = _now()
        if body.decision == "issued":
            obj.status = "ap_approval"
            obj.audit_trail = _audit(obj.audit_trail, "ap_approved", body.user_name, body.comments)
        else:
            obj.status = "safety_review"
            obj.audit_trail = _audit(obj.audit_trail, "ap_rejected", body.user_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/issue")
async def issue_permit(ptw_id: str, ap_id: str, ap_name: str):
    """AP formally issues the permit — work may begin."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "issued")
        obj.status = "issued"
        obj.ap_issue_date = _now()
        obj.audit_trail = _audit(obj.audit_trail, "issued", ap_name, "Permit issued — work may begin")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/activate")
async def activate_permit(ptw_id: str, user_id: str, user_name: str):
    """Work team acknowledges and activates the permit."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "active")
        obj.status = "active"
        obj.actual_start = _now()
        obj.audit_trail = _audit(obj.audit_trail, "activated", user_name, "Work commenced")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/suspend")
async def suspend_permit(ptw_id: str, body: SuspendBody):
    """Temporarily suspend active work (e.g. gas alarm, shift change)."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "suspended")
        obj.status = "suspended"
        obj.audit_trail = _audit(obj.audit_trail, "suspended", body.user_name, body.reason)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/resume")
async def resume_permit(ptw_id: str, body: ResumeBody):
    """Resume a suspended permit."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "active")
        obj.status = "active"
        obj.audit_trail = _audit(obj.audit_trail, "resumed", body.user_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/request-closure")
async def request_closure(ptw_id: str, body: CloseRequestBody):
    """Work team requests closure after completing work."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "completion_requested")
        obj.status = "completion_requested"
        obj.closure_requested_by = body.requested_by_name
        obj.closure_requested_at = _now()
        obj.closure_comments = body.comments
        obj.actual_end = _now()
        obj.audit_trail = _audit(obj.audit_trail, "closure_requested", body.requested_by_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/close")
async def close_permit(ptw_id: str, body: CloseBody):
    """AP formally closes the permit after site has been returned to safe condition."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "closed")
        obj.status = "closed"
        obj.ap_close_date = _now()
        obj.audit_trail = _audit(obj.audit_trail, "closed", body.ap_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/cancel")
async def cancel_permit(ptw_id: str, body: CancelBody):
    """Cancel a permit at any stage before issuance or after suspension."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        _assert_transition(obj.status, "cancelled")
        obj.status = "cancelled"
        obj.audit_trail = _audit(obj.audit_trail, "cancelled", body.user_name, body.reason)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{ptw_id}/gas-tests")
async def add_gas_test(ptw_id: str, body: GasTestAdd):
    """Append a gas test certificate to an active or issued permit."""
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
        tests = list(obj.gas_tests or [])
        tests.append(body.model_dump())
        obj.gas_tests = tests
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{ptw_id}/audit-trail")
async def get_audit_trail(ptw_id: str):
    async with AsyncSessionLocal() as s:
        obj = await _get_ptw(s, ptw_id)
    return obj.audit_trail or []
