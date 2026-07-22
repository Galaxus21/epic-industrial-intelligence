"""
AI Operations Brain — Incident Reports API
Full investigation workflow:
  reported → investigation → root_cause_analysis → capa → closed

Includes CAPA tracking, investigation team assignment, and management sign-off.
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

INCIDENT_TYPES = {
    "near_miss", "first_aid", "medical_treatment", "lost_time",
    "fatality", "environmental", "property_damage", "fire", "spill", "other",
}
SEVERITY_LEVELS = {"P1", "P2", "P3", "P4", "P5"}


class IncidentCreate(BaseModel):
    title: str
    description: str = ""
    incident_type: str = "near_miss"
    severity: str = "P5"
    project_id: str | None = None
    plant_id: str | None = None
    equipment_ids: list[str] = []
    location_description: str | None = None
    occurred_at: str | None = None
    persons_involved: list[dict] = []
    witnesses: list[dict] = []
    immediate_actions: list[str] = []
    reported_by_id: str | None = None
    reported_by_name: str | None = None
    # Operational impact (optional at report time; updateable later)
    downtime_hours: float | None = None
    cost_usd: float | None = None
    root_cause_category: str | None = None


class InvestigationAssign(BaseModel):
    lead_id: str
    lead_name: str
    team: list[dict] = []   # [{id, name, role}]


class RootCauseUpdate(BaseModel):
    root_causes: list[dict]            # [{level, cause, category}]
    contributing_factors: list[str]
    timeline: list[dict] = []         # [{time, event, description}]


class CapaAdd(BaseModel):
    action_type: str = "corrective"   # corrective | preventive
    description: str
    assigned_to_id: str | None = None
    assigned_to_name: str | None = None
    due_date: str | None = None


class CapaComplete(BaseModel):
    capa_id: str
    completed_by_id: str
    completed_by_name: str
    evidence: str = ""


class ManagementReview(BaseModel):
    reviewer_id: str
    reviewer_name: str
    comments: str = ""


class CloseBody(BaseModel):
    closed_by_id: str
    closed_by_name: str
    closure_comments: str = ""


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


async def _get(s, inc_id: str) -> m.IncidentReport:
    obj = (await s.execute(select(m.IncidentReport).where(m.IncidentReport.id == inc_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Incident report not found")
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_incidents(
    status: str | None = None,
    severity: str | None = None,
    incident_type: str | None = None,
    project_id: str | None = None,
):
    async with AsyncSessionLocal() as s:
        q = select(m.IncidentReport)
        if status:
            q = q.where(m.IncidentReport.status == status)
        if severity:
            q = q.where(m.IncidentReport.severity == severity)
        if incident_type:
            q = q.where(m.IncidentReport.incident_type == incident_type)
        if project_id:
            q = q.where(m.IncidentReport.project_id == project_id)
        rows = (await s.execute(q.order_by(m.IncidentReport.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_incident(body: IncidentCreate):
    if body.incident_type not in INCIDENT_TYPES:
        raise HTTPException(400, f"Invalid incident_type. Choose from: {sorted(INCIDENT_TYPES)}")
    if body.severity not in SEVERITY_LEVELS:
        raise HTTPException(400, f"Invalid severity. Use P1 (Fatality) … P5 (Near Miss)")
    iid = f"INC-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        count = len((await s.execute(select(m.IncidentReport))).scalars().all())
        incident_number = f"INC-{datetime.utcnow().year}-{str(count + 1).zfill(4)}"
        data = body.model_dump()
        data["reported_at"] = _now()
        obj = m.IncidentReport(
            id=iid,
            incident_number=incident_number,
            audit_trail=_audit(None, "reported", body.reported_by_name or "system"),
            **data,
        )
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{inc_id}")
async def get_incident(inc_id: str):
    async with AsyncSessionLocal() as s:
        obj = await _get(s, inc_id)
    return _row(obj)


# ─────────────────────────────────────────────────────────────────────────────
# Workflow
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{inc_id}/assign-investigation")
async def assign_investigation(inc_id: str, body: InvestigationAssign):
    """Assign investigation lead and team."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, inc_id)
        obj.status = "investigation"
        obj.investigation_lead_id = body.lead_id
        obj.investigation_lead_name = body.lead_name
        obj.investigation_team = body.team
        obj.audit_trail = _audit(obj.audit_trail, "investigation_assigned", body.lead_name,
                                  f"Team: {[m['name'] for m in body.team]}")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{inc_id}/root-cause")
async def update_root_cause(inc_id: str, body: RootCauseUpdate):
    """Record root causes (5-Why / Bow-Tie) from investigation."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, inc_id)
        obj.status = "root_cause_analysis"
        obj.root_causes = body.root_causes
        obj.contributing_factors = body.contributing_factors
        obj.timeline = body.timeline
        obj.audit_trail = _audit(obj.audit_trail, "root_cause_recorded",
                                  obj.investigation_lead_name or "system",
                                  f"{len(body.root_causes)} root causes identified")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{inc_id}/capa/add")
async def add_capa(inc_id: str, body: CapaAdd):
    """Add a corrective or preventive action."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, inc_id)
        items = list(obj.capa_items or [])
        capa_id = f"CAPA-{uuid.uuid4().hex[:6].upper()}"
        items.append({
            "id": capa_id,
            "status": "open",
            "created_at": _now(),
            **body.model_dump(),
        })
        obj.capa_items = items
        obj.status = "capa"
        obj.audit_trail = _audit(obj.audit_trail, "capa_added", "system",
                                  f"{body.action_type}: {body.description[:60]}")
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{inc_id}/capa/complete")
async def complete_capa(inc_id: str, body: CapaComplete):
    """Mark a CAPA item as completed."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, inc_id)
        items = list(obj.capa_items or [])
        item = next((i for i in items if i.get("id") == body.capa_id), None)
        if not item:
            raise HTTPException(404, f"CAPA item {body.capa_id} not found")
        item["status"] = "completed"
        item["completed_by_id"] = body.completed_by_id
        item["completed_by_name"] = body.completed_by_name
        item["completed_at"] = _now()
        item["evidence"] = body.evidence
        obj.capa_items = items
        obj.audit_trail = _audit(obj.audit_trail, "capa_completed", body.completed_by_name, body.capa_id)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{inc_id}/management-review")
async def management_review(inc_id: str, body: ManagementReview):
    """Management reviews and acknowledges the investigation findings."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, inc_id)
        obj.reviewed_by_id = body.reviewer_id
        obj.reviewed_by_name = body.reviewer_name
        obj.review_comments = body.comments
        obj.reviewed_at = _now()
        obj.audit_trail = _audit(obj.audit_trail, "management_reviewed", body.reviewer_name, body.comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.post("/{inc_id}/close")
async def close_incident(inc_id: str, body: CloseBody):
    """Close the incident after all CAPAs are complete."""
    async with AsyncSessionLocal() as s:
        obj = await _get(s, inc_id)
        # Check all CAPAs are completed
        open_capas = [c for c in (obj.capa_items or []) if c.get("status") == "open"]
        if open_capas:
            raise HTTPException(409, f"{len(open_capas)} CAPA items still open — cannot close incident")
        obj.status = "closed"
        obj.closed_by_id = body.closed_by_id
        obj.closed_by_name = body.closed_by_name
        obj.closed_at = _now()
        obj.closure_comments = body.closure_comments
        obj.audit_trail = _audit(obj.audit_trail, "closed", body.closed_by_name, body.closure_comments)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{inc_id}/audit-trail")
async def get_audit_trail(inc_id: str):
    async with AsyncSessionLocal() as s:
        obj = await _get(s, inc_id)
    return obj.audit_trail or []
