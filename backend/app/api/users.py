"""
AI Operations Brain — User Profiles API
Manage users with role-based permissions for approval workflows.
Roles: technician | supervisor | safety_officer | area_authority
       authorized_person | manager | quality_inspector
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

VALID_ROLES = {
    "technician", "supervisor", "safety_officer",
    "area_authority", "authorized_person", "manager", "quality_inspector",
}


class UserCreate(BaseModel):
    employee_id: str
    name: str
    email: str | None = None
    department: str | None = None
    role: str = "technician"
    certifications: list[str] = []
    plant_ids: list[str] = []


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    department: str | None = None
    role: str | None = None
    certifications: list[str] | None = None
    plant_ids: list[str] | None = None
    is_active: bool | None = None


def _row(obj) -> dict[str, Any]:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


@router.get("")
async def list_users(role: str | None = None, active_only: bool = True):
    async with AsyncSessionLocal() as s:
        q = select(m.UserProfile)
        if active_only:
            q = q.where(m.UserProfile.is_active == True)  # noqa: E712
        if role:
            q = q.where(m.UserProfile.role == role)
        rows = (await s.execute(q.order_by(m.UserProfile.name))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_user(body: UserCreate):
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Choose from: {sorted(VALID_ROLES)}")
    uid = f"USR-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        existing = (await s.execute(
            select(m.UserProfile).where(m.UserProfile.employee_id == body.employee_id)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(409, f"Employee ID '{body.employee_id}' already exists")
        obj = m.UserProfile(id=uid, **body.model_dump())
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/{user_id}")
async def get_user(user_id: str):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.UserProfile).where(m.UserProfile.id == user_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "User not found")
    return _row(obj)


@router.patch("/{user_id}")
async def update_user(user_id: str, body: UserUpdate):
    if body.role and body.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Choose from: {sorted(VALID_ROLES)}")
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.UserProfile).where(m.UserProfile.id == user_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "User not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)
