"""
EPIC — User Profiles API
Manage users with role-based permissions for approval workflows.
Roles: technician | supervisor | safety_officer | area_authority
       authorized_person | manager | quality_inspector
"""
import asyncio
import uuid
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.core.auth import (
    SESSION_COOKIE_NAME,
    TOKEN_TTL_SECONDS,
    get_current_user,
    hash_password,
    async_hash_password,
    issue_token,
    require_roles,
    require_roles_or_bootstrap,
    verify_password,
)
from app.core.config import settings
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
    password: str | None = None


class LoginBody(BaseModel):
    employee_id: str
    password: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    department: str | None = None
    role: str | None = None
    certifications: list[str] | None = None
    is_active: bool | None = None


def _row(obj) -> dict[str, Any]:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    d.pop("password_hash", None)  # never expose credentials
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


# ── Authentication ────────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginBody, response: Response):
    """Exchange credentials for a bearer token bound to a real UserProfile.

    Sets an HttpOnly, SameSite=Lax cookie for browser/SSR sessions while returning
    the token in the JSON payload for backward compatibility and machine clients.
    """
    async with AsyncSessionLocal() as s:
        user = (await s.execute(
            select(m.UserProfile).where(m.UserProfile.employee_id == body.employee_id)
        )).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(401, "Invalid credentials")

    if user.password_hash:
        if not body.password or not await asyncio.to_thread(verify_password, body.password, user.password_hash):
            raise HTTPException(401, "Invalid credentials")
    elif settings.environment == "production":
        raise HTTPException(
            401, "Account has no password set — a password is required in production"
        )

    token = issue_token(user.id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.environment != "development",
        max_age=TOKEN_TTL_SECONDS,
        path="/",
    )
    return {"token": token, "user": _row(user)}


@router.post("/logout")
async def logout(response: Response):
    """Clear session cookie. Idempotent and unauthenticated."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.environment != "development",
    )
    return {"status": "ok"}


@router.get("/me")
async def whoami(user: m.UserProfile = Depends(get_current_user)):
    return _row(user)


class PasswordBody(BaseModel):
    password: str


@router.post("/{user_id}/set-password")
async def set_password(user_id: str, body: PasswordBody,
                       actor: m.UserProfile = Depends(get_current_user)):
    """Set a user's password. Users may set their own; managers may set anyone's."""
    if actor.id != user_id and actor.role != "manager":
        raise HTTPException(403, "Only the user themselves or a manager can set a password")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.UserProfile).where(m.UserProfile.id == user_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "User not found")
        obj.password_hash = await async_hash_password(body.password)
        await s.commit()
    return {"status": "ok"}


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
async def create_user(
    body: UserCreate,
    user: m.UserProfile | None = Depends(require_roles_or_bootstrap("manager")),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Choose from: {sorted(VALID_ROLES)}")
    uid = f"USR-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        existing = (await s.execute(
            select(m.UserProfile).where(m.UserProfile.employee_id == body.employee_id)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(409, f"Employee ID '{body.employee_id}' already exists")
        data = body.model_dump()
        password = data.pop("password", None)
        if settings.environment == "production" and not password:
            raise HTTPException(400, "A password is required when creating users in production")
        obj = m.UserProfile(
            id=uid,
            password_hash=(await async_hash_password(password)) if password else None,
            **data,
        )
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
async def update_user(
    user_id: str,
    body: UserUpdate,
    user: m.UserProfile = Depends(require_roles("manager")),
):
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
