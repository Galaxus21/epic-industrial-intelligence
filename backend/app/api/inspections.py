"""
AI Operations Brain — Quality Inspections & Action Items API

Inspections workflow:
  scheduled → in_progress → pending_review → closed_satisfactory | closed_with_findings | rejected

Action Items workflow:
  open → in_progress → pending_verification → verified | overdue
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

INSPECTION_TYPES = {
    "equipment", "process", "safety_audit", "environmental",
    "contractor", "pre_startup", "housekeeping",
}


# ─────────────────────────────────────────────────────────────────────────────
# Schemas — Inspections
# ─────────────────────────────────────────────────────────────────────────────

class InspectionCreate(BaseModel):
    title: str
    inspection_type: str = "equipment"
    project_id: str | None = None
    plant_id: str | None = None
    equipment_ids: list[str] = []
    priority: str = "medium"
    scheduled_date: str | None = None
    inspector_id: str | None = None
    inspector_name: str | None = None
    checklist_items: list[dict] = []
    created_by: str | None = None


class InspectionUpdate(BaseModel):
    title: str | None = None
    scheduled_date: str | None = None
    inspector_id: str | None = None
    inspector_name: str | None = None
    checklist_items: list[dict] | None = None


class InspectionStartBody(BaseModel):
    inspector_id: str
    inspector_name: str


class ChecklistItemResult(BaseModel):
    item_index: int
    result: str          # pass | fail | na | obs
    findings: str = ""
    evidence_ref: str = ""


class NonConformanceAdd(BaseModel):
    description: str
    severity: str = "minor"  # critical | major | minor
    action_required: str = ""
    due_date: str | None = None


class InspectionCloseBody(BaseModel):
    reviewer_id: str
    reviewer_name: str
    decision: str   # closed_satisfactory | closed_with_findings | rejected
    comments: str = ""
    summary_notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Schemas — Action Items
# ─────────────────────────────────────────────────────────────────────────────

class ActionCreate(BaseModel):
    title: str
    description: str = ""
    source_type: str | None = None
    source_id: str | None = None
    source_ref: str | None = None
    action_type: str = "corrective"
    priority: str = "medium"
    project_id: str | None = None
    plant_id: str | None = None
    assigned_to_id: str | None = None
    assigned_to_name: str | None = None
    due_date: str | None = None
    created_by: str | None = None


class ActionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    assigned_to_id: str | None = None
    assigned_to_name: str | None = None
    due_date: str | None = None


class ActionCompleteBody(BaseModel):
    completed_by_id: str
    completed_by_name: str
    completion_evidence: str = ""


class ActionVerifyBody(BaseModel):
    verifier_id: str
    verifier_name: str
    decision: str   # verified | rejected
    comments: str = ""


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


# ─────────────────────────────────────────────────────────────────────────────
# Inspection endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_inspections(
    status: str | None = None,
    plant_id: str | None = None,
    project_id: str | None = None,
    inspection_type: str | None = None,
):
    async with AsyncSessionLocal() as s:
        q = select(m.QualityInspection)
        if status:
            q = q.where(m.QualityInspection.status == status)
        if plant_id:
            q = q.where(m.QualityInspection.plant_id == plant_id)
        if project_id:
            q = q.where(m.QualityInspection.project_id == project_id)
        if inspection_type:
            q = q.where(m.QualityInspection.inspection_type == inspection_type)
        rows = (await s.execute(q.order_by(m.QualityInspection.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_inspection(body: InspectionCreate):
    iid = f"QI-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        count = len((await s.execute(select(m.QualityInspection))).scalars().all())
        inspection_number = f"QI-{datetime.utcnow().year}-{str(count + 1).zfill(4)}"
        obj = m.QualityInspection(
            id=iid,
            inspection_number=inspection_number,
            audit_trail=_audit(None, "created", body.created_by or "system"),
            **body.model_dump(),
        )
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{insp_id}")
async def get_inspection(insp_id: str):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.QualityInspection).where(m.QualityInspection.id == insp_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Inspection not found")
    return _row(obj)


@router.post("/{insp_id}/start")
async def start_inspection(insp_id: str, body: InspectionStartBody):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.QualityInspection).where(m.QualityInspection.id == insp_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Inspection not found")
        if obj.status != "scheduled":
            raise HTTPException(409, "Inspection is not in scheduled status")
        obj.status = "in_progress"
        obj.inspector_id = body.inspector_id
        obj.inspector_name = body.inspector_name
        obj.actual_date = _now()
        obj.audit_trail = _audit(obj.audit_trail, "started", body.inspector_name)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{insp_id}/record-result")
async def record_checklist_result(insp_id: str, body: ChecklistItemResult):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.QualityInspection).where(m.QualityInspection.id == insp_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Inspection not found")
        items = list(obj.checklist_items or [])
        if body.item_index >= len(items):
            raise HTTPException(400, "Invalid item_index")
        items[body.item_index]["result"] = body.result
        items[body.item_index]["findings"] = body.findings
        items[body.item_index]["evidence_ref"] = body.evidence_ref
        obj.checklist_items = items
        # Recalculate overall score
        scored = [i for i in items if i.get("result") in ("pass", "fail")]
        if scored:
            obj.overall_score = round(
                len([i for i in scored if i["result"] == "pass"]) / len(scored) * 100, 1
            )
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{insp_id}/add-nc")
async def add_non_conformance(insp_id: str, body: NonConformanceAdd):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.QualityInspection).where(m.QualityInspection.id == insp_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Inspection not found")
        ncs = list(obj.non_conformances or [])
        ncs.append({
            "id": f"NC-{uuid.uuid4().hex[:6].upper()}",
            "status": "open",
            **body.model_dump(),
        })
        obj.non_conformances = ncs
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{insp_id}/submit")
async def submit_inspection(insp_id: str, inspector_id: str, inspector_name: str, summary_notes: str = ""):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.QualityInspection).where(m.QualityInspection.id == insp_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Inspection not found")
        if obj.status != "in_progress":
            raise HTTPException(409, "Inspection must be in_progress to submit")
        obj.status = "pending_review"
        obj.summary_notes = summary_notes
        obj.audit_trail = _audit(obj.audit_trail, "submitted_for_review", inspector_name)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{insp_id}/review")
async def review_inspection(insp_id: str, body: InspectionCloseBody):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.QualityInspection).where(m.QualityInspection.id == insp_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Inspection not found")
        if obj.status != "pending_review":
            raise HTTPException(409, "Inspection is not pending review")
        valid_decisions = {"closed_satisfactory", "closed_with_findings", "rejected"}
        if body.decision not in valid_decisions:
            raise HTTPException(400, f"Decision must be one of {valid_decisions}")
        obj.status = body.decision
        obj.reviewer_id = body.reviewer_id
        obj.reviewer_name = body.reviewer_name
        obj.reviewer_decision = body.decision
        obj.reviewer_comments = body.comments
        obj.summary_notes = body.summary_notes or obj.summary_notes
        obj.reviewed_at = _now()
        obj.audit_trail = _audit(obj.audit_trail, body.decision, body.reviewer_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


# ─────────────────────────────────────────────────────────────────────────────
# Action Items endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/actions/list")
async def list_actions(
    status: str | None = None,
    priority: str | None = None,
    project_id: str | None = None,
    assigned_to_id: str | None = None,
):
    async with AsyncSessionLocal() as s:
        q = select(m.ActionItem)
        if status:
            q = q.where(m.ActionItem.status == status)
        if priority:
            q = q.where(m.ActionItem.priority == priority)
        if project_id:
            q = q.where(m.ActionItem.project_id == project_id)
        if assigned_to_id:
            q = q.where(m.ActionItem.assigned_to_id == assigned_to_id)
        rows = (await s.execute(q.order_by(m.ActionItem.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("/actions", status_code=201)
async def create_action(body: ActionCreate):
    aid = f"ACT-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        count = len((await s.execute(select(m.ActionItem))).scalars().all())
        action_number = f"ACT-{datetime.utcnow().year}-{str(count + 1).zfill(4)}"
        obj = m.ActionItem(
            id=aid,
            action_number=action_number,
            **body.model_dump(),
        )
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/actions/{action_id}")
async def get_action(action_id: str):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.ActionItem).where(m.ActionItem.id == action_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Action item not found")
    return _row(obj)


@router.patch("/actions/{action_id}")
async def update_action(action_id: str, body: ActionUpdate):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.ActionItem).where(m.ActionItem.id == action_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Action item not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/actions/{action_id}/start")
async def start_action(action_id: str, user_id: str, user_name: str):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.ActionItem).where(m.ActionItem.id == action_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Action item not found")
        obj.status = "in_progress"
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/actions/{action_id}/complete")
async def complete_action(action_id: str, body: ActionCompleteBody):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.ActionItem).where(m.ActionItem.id == action_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Action item not found")
        obj.status = "pending_verification"
        obj.completed_by_id = body.completed_by_id
        obj.completed_by_name = body.completed_by_name
        obj.completed_at = _now()
        obj.completion_evidence = body.completion_evidence
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/actions/{action_id}/verify")
async def verify_action(action_id: str, body: ActionVerifyBody):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.ActionItem).where(m.ActionItem.id == action_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Action item not found")
        if obj.status != "pending_verification":
            raise HTTPException(409, "Action item is not pending verification")
        new_status = "verified" if body.decision == "verified" else "in_progress"
        obj.status = new_status
        obj.verifier_id = body.verifier_id
        obj.verifier_name = body.verifier_name
        obj.verification_comments = body.comments
        obj.verified_at = _now()
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)
