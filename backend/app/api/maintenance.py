"""
AI Operations Brain — Maintenance Records API

Endpoints:
  GET  /api/v1/maintenance          List all maintenance records (filterable)
  GET  /api/v1/maintenance/{id}     Single record
  POST /api/v1/maintenance          Create a new record
  PATCH /api/v1/maintenance/{id}    Update status / findings
"""
import uuid
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.auth import require_roles
from app.core.roles import FIELD_ROLES
from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services.db_service import list_all_maintenance_records, upsert_maintenance_record

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class MaintenanceCreate(BaseModel):
    equipment_id: str
    type: str = "Preventive"           # Preventive | Corrective | Predictive | Emergency
    description: str
    scheduled_date: str | None = None
    technician: str | None = None
    status: str = "Pending"


class MaintenanceUpdate(BaseModel):
    status: str | None = None
    findings: str | None = None
    technician: str | None = None
    date: str | None = None            # actual completion date


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_maintenance(
    equipment_id: str | None = None,
    status: str | None = None,
    type: str | None = None,
):
    """Return all maintenance records, newest first. Optionally filter."""
    records = await list_all_maintenance_records(
        equipment_id=equipment_id,
        status=status,
        type_filter=type,
    )
    return records


# ── Single record ─────────────────────────────────────────────────────────────

@router.get("/{record_id}")
async def get_maintenance_record(record_id: str):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.MaintenanceRecord, record_id)
    if not row:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    if d.get("extra"):
        d.update(d.pop("extra"))
    return d


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("")
async def create_maintenance_record(
    body: MaintenanceCreate,
    user: m.UserProfile = Depends(require_roles(*FIELD_ROLES)),
):
    rec_id = f"MR-{datetime.utcnow().strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
    record: dict[str, Any] = {
        "id": rec_id,
        "equipment_id": body.equipment_id,
        "type": body.type,
        "description": body.description,
        "scheduled_date": body.scheduled_date,
        "technician": user.name,
        "status": body.status,
        "date": None,
        "findings": None,
    }
    await upsert_maintenance_record(record)
    return {"id": rec_id, **record}


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{record_id}")
async def update_maintenance_record(
    record_id: str,
    body: MaintenanceUpdate,
    user: m.UserProfile = Depends(require_roles(*FIELD_ROLES)),
):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.MaintenanceRecord, record_id)
        if not row:
            raise HTTPException(status_code=404, detail="Maintenance record not found")
        if body.status is not None:
            row.status = body.status
        if body.findings is not None:
            row.findings = body.findings
        # Technician identity is resolved from authenticated user
        row.technician = user.name
        if body.date is not None:
            row.date = body.date
        await s.commit()
    return {"id": record_id, "status": "updated"}
