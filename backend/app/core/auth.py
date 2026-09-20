"""
EPIC — Authentication & Authorization
Unified authentication facade supporting swappable AuthProviders and dual-transport
session resolution (HttpOnly cookie for SSR/browser, Bearer header for machine/CLI).
"""
from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select

from app.core.authProvider import AuthProvider, Principal
from app.core.config import settings
from app.core.localAuthProvider import (
    LocalAuthProvider,
    SESSION_COOKIE_NAME,
    TOKEN_TTL_SECONDS,
    _PBKDF2_ITERATIONS,
    hash_password,
    async_hash_password,
    verify_password,
    async_verify_password,
    issue_token,
    verify_token,
    _sign,
)
from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)

# Re-exports for backward compatibility
__all__ = [
    "AuthProvider",
    "Principal",
    "LocalAuthProvider",
    "SESSION_COOKIE_NAME",
    "TOKEN_TTL_SECONDS",
    "_PBKDF2_ITERATIONS",
    "hash_password",
    "async_hash_password",
    "verify_password",
    "async_verify_password",
    "issue_token",
    "verify_token",
    "_sign",
    "get_auth_provider",
    "get_current_user",
    "get_current_principal",
    "require_roles",
    "require_roles_or_bootstrap",
]


@lru_cache
def get_auth_provider() -> AuthProvider:
    """Factory returning the active AuthProvider based on settings."""
    provider_type = settings.auth_provider.strip().lower()
    if provider_type == "local":
        return LocalAuthProvider()
    raise ValueError(f"Unsupported auth provider: '{settings.auth_provider}'")


def _extract_token(request: Request) -> str | None:
    """Extract session token: prefers HttpOnly cookie, falls back to Bearer header."""
    # 1. HttpOnly cookie (browser / Next.js SSR)
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    # 2. Authorization: Bearer <token> (machine clients / API tests)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header.removeprefix("Bearer ").strip()
        if bearer_token:
            return bearer_token

    return None


async def get_current_user(request: Request) -> m.UserProfile:
    """Resolve the authenticated principal from cookie or bearer header.

    The returned UserProfile is loaded fresh from the DB, ensuring role checks
    and identity attributes always reflect the server-side record.
    """
    raw_token = _extract_token(request)
    if not raw_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated — log in via POST /api/v1/users/login",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provider = get_auth_provider()
    resolve_fn = getattr(provider, "resolve_principal", None) or getattr(provider, "resolvePrincipal", None)
    if resolve_fn is not None:
        principal = await resolve_fn(raw_token)
    else:
        user_id = verify_token(raw_token)
        principal = Principal(id=user_id, name="", role="") if user_id else None

    if not principal:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session token",
        )

    async with AsyncSessionLocal() as s:
        user = (await s.execute(
            select(m.UserProfile).where(m.UserProfile.id == principal.id)
        )).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Unknown or deactivated user",
        )
    return user


async def get_current_principal(request: Request) -> Principal:
    """Resolve authenticated Principal without loading full database row."""
    raw_token = _extract_token(request)
    if not raw_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provider = get_auth_provider()
    resolve_fn = getattr(provider, "resolve_principal", None) or getattr(provider, "resolvePrincipal", None)
    if resolve_fn is not None:
        principal = await resolve_fn(raw_token)
    else:
        user_id = verify_token(raw_token)
        principal = Principal(id=user_id, name="", role="") if user_id else None

    if not principal:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")

    return principal


def require_roles(*roles: str | tuple[str, ...] | list[str]):
    """Dependency factory: the authenticated user must hold one of the roles."""
    flat_roles: list[str] = []
    for r in roles:
        if isinstance(r, (tuple, list, set)):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)
    flat_tuple = tuple(flat_roles)

    async def _check(user: m.UserProfile = Depends(get_current_user)) -> m.UserProfile:
        if flat_tuple and user.role not in flat_tuple:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' is not authorized for this action (requires: {', '.join(flat_tuple)})",
            )
        return user

    _check.required_roles = flat_tuple
    return _check


def require_roles_or_bootstrap(*roles: str | tuple[str, ...] | list[str]):
    """Dependency factory: require roles, with bootstrap exemption when UserProfile table has 0 users.

    If 0 users exist in the database, allows unauthenticated bootstrap caller.
    Once at least 1 user exists, enforces standard authentication and role requirements.
    """
    flat_roles: list[str] = []
    for r in roles:
        if isinstance(r, (tuple, list, set)):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)
    flat_tuple = tuple(flat_roles)

    async def _check(request: Request) -> m.UserProfile | None:
        async with AsyncSessionLocal() as s:
            count = (await s.execute(select(func.count()).select_from(m.UserProfile))).scalar() or 0
        if count == 0:
            return None
        user = await get_current_user(request)
        if flat_tuple and user.role not in flat_tuple:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' is not authorized for this action (requires: {', '.join(flat_tuple)})",
            )
        return user

    _check.required_roles = flat_tuple
    _check.allow_bootstrap = True
    return _check

