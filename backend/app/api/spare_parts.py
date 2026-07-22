"""
AI Operations Brain — Spare Parts API
Full CRUD for the spare_parts table so it is writable at runtime
(previously seed-data-only with no management endpoints).

Endpoints
---------
  GET    /api/v1/spare-parts               list all (optional ?equipment_id=)
  GET    /api/v1/spare-parts/{id}          get one
  POST   /api/v1/spare-parts               create
  PATCH  /api/v1/spare-parts/{id}          update fields
  DELETE /api/v1/spare-parts/{id}          hard-delete
  POST   /api/v1/spare-parts/{id}/issue    create a stock-issue transaction
         (decrement quantity_on_hand)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services.audit import audit

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Schemas ──────────────────────────────────────────────────────────────────

class SparePartCreate(BaseModel):
    name: str
    part_number: str | None = None
    equipment_ids: list[str] = []
    quantity_on_hand: int = 0
    reorder_point: int = 0
    lead_time_days: int | None = None
    location: str | None = None
    unit_cost_usd: float | None = None
    status: str = "Available"   # Available | Low Stock | Out of Stock | Discontinued


class SparePartUpdate(BaseModel):
    name: str | None = None
    part_number: str | None = None
    equipment_ids: list[str] | None = None
    quantity_on_hand: int | None = None
    reorder_point: int | None = None
    lead_time_days: int | None = None
    location: str | None = None
    unit_cost_usd: float | None = None
    status: str | None = None


class IssueRequest(BaseModel):
    quantity: int = 1
    issued_to: str = ""
    work_order_id: str | None = None
    notes: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(obj) -> dict[str, Any]:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    return d


def _status_for(qty: int, reorder: int) -> str:
    if qty <= 0:
        return "Out of Stock"
    if qty <= reorder:
        return "Low Stock"
    return "Available"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_spare_parts(equipment_id: str | None = None):
    """List all spare parts, optionally filtered by equipment_id."""
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(m.SparePart).order_by(m.SparePart.name))
        rows = result.scalars().all()
    parts = [_row(r) for r in rows]
    if equipment_id:
        parts = [p for p in parts if equipment_id in (p.get("equipment_ids") or [])]
    return parts


@router.get("/{part_id}")
async def get_spare_part(part_id: str):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SparePart, part_id)
    if row is None:
        raise HTTPException(404, f"Spare part '{part_id}' not found")
    return _row(row)


@router.post("", status_code=201)
async def create_spare_part(body: SparePartCreate):
    part_id = f"SP-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        obj = m.SparePart(
            id=part_id,
            name=body.name,
            part_number=body.part_number,
            equipment_ids=body.equipment_ids,
            quantity_on_hand=body.quantity_on_hand,
            reorder_point=body.reorder_point,
            lead_time_days=body.lead_time_days,
            location=body.location,
            unit_cost_usd=body.unit_cost_usd,
            status=_status_for(body.quantity_on_hand, body.reorder_point),
        )
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    audit("create", "spare_part", part_id, actor="user",
          notes=f"Created: {body.name}")
    return _row(obj)


@router.patch("/{part_id}")
async def update_spare_part(part_id: str, body: SparePartUpdate):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SparePart, part_id)
        if row is None:
            raise HTTPException(404, f"Spare part '{part_id}' not found")
        for field, val in body.model_dump(exclude_none=True).items():
            setattr(row, field, val)
        # Auto-recalculate status from quantity unless explicitly provided
        if body.status is None:
            row.status = _status_for(row.quantity_on_hand, row.reorder_point)
        await s.commit()
        await s.refresh(row)
    audit("update", "spare_part", part_id, actor="user")
    return _row(row)


@router.delete("/{part_id}", status_code=204)
async def delete_spare_part(part_id: str):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SparePart, part_id)
        if row is None:
            raise HTTPException(404, f"Spare part '{part_id}' not found")
        await s.delete(row)
        await s.commit()
    audit("delete", "spare_part", part_id, actor="user")


@router.post("/{part_id}/issue")
async def issue_spare_part(part_id: str, body: IssueRequest):
    """Decrement quantity_on_hand by the requested quantity (stock-issue transaction)."""
    async with AsyncSessionLocal() as s:
        row = await s.get(m.SparePart, part_id)
        if row is None:
            raise HTTPException(404, f"Spare part '{part_id}' not found")
        if row.quantity_on_hand < body.quantity:
            raise HTTPException(
                422,
                f"Only {row.quantity_on_hand} unit(s) in stock; requested {body.quantity}",
            )
        row.quantity_on_hand -= body.quantity
        row.status = _status_for(row.quantity_on_hand, row.reorder_point)
        await s.commit()
        await s.refresh(row)
    audit("update", "spare_part", part_id, actor=body.issued_to or "user",
          notes=f"Issued {body.quantity} unit(s) to {body.issued_to}. WO: {body.work_order_id or '—'}. {body.notes}")
    return {
        "id": part_id,
        "quantity_issued": body.quantity,
        "quantity_remaining": row.quantity_on_hand,
        "status": row.status,
    }
