"""
EPIC — Local Authentication Provider
Implements AuthProvider using local database user profiles, PBKDF2 password hashing,
and HMAC-SHA256 signed session tokens.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

from sqlalchemy import select

from app.core.authProvider import Principal
from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS: int = 12 * 3600
SESSION_COOKIE_NAME: str = "epicSession"
_PBKDF2_ITERATIONS: int = 200_000


# ── Password hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 200,000 iterations and random salt."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify password against a stored PBKDF2 string using constant-time comparison."""
    try:
        _, iters, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError):
        return False
    except Exception as exc:
        logger.warning("verify_password encountered unexpected error: %s", exc, exc_info=True)
        return False


async def async_hash_password(password: str) -> str:
    """Offload CPU-bound PBKDF2 hashing (200k iterations) to worker thread."""
    return await asyncio.to_thread(hash_password, password)


async def async_verify_password(password: str, stored: str) -> bool:
    """Offload CPU-bound PBKDF2 verification to worker thread."""
    return await asyncio.to_thread(verify_password, password, stored)


# ── Token issue / verify ─────────────────────────────────────────────────────

def _sign(payload_b64: str, secret_key: str | None = None) -> str:
    """Compute HMAC-SHA256 hex digest for a base64 payload using the secret key."""
    key = secret_key or settings.secret_key
    return hmac.new(key.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()


def issue_token(user_id: str) -> str:
    """Legacy helper: Issue an HMAC-signed token containing user_id."""
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str, secret_key: str | None = None) -> str | None:
    """Legacy helper: Return the user_id if the token is valid and unexpired, else None."""
    try:
        payload_b64, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(payload_b64, secret_key)):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("uid")
    except Exception:
        return None


# ── Provider Implementation ──────────────────────────────────────────────────

class LocalAuthProvider:
    """Authentication provider using the local database, PBKDF2, and HMAC session tokens."""

    def __init__(self, secret_key: str | None = None, token_ttl: int = TOKEN_TTL_SECONDS) -> None:
        self.secret_key = secret_key or settings.secret_key
        self.token_ttl = token_ttl

    async def authenticate(self, employee_id: str, password: str | None = None) -> Principal | None:
        """Authenticate employee_id against user_profiles table."""
        async with AsyncSessionLocal() as s:
            user = (await s.execute(
                select(m.UserProfile).where(m.UserProfile.employee_id == employee_id)
            )).scalar_one_or_none()

        if not user or not user.is_active:
            return None

        if user.password_hash:
            if not password:
                return None
            # Offload CPU-bound PBKDF2 verification to worker thread
            valid = await asyncio.to_thread(verify_password, password, user.password_hash)
            if not valid:
                return None
        elif settings.environment == "production":
            # Passwords mandatory in production
            return None

        return Principal(id=user.id, name=user.name, role=user.role, email=user.email)

    async def issue_session(self, principal: Principal) -> str:
        """Issue an HMAC-signed token embedding full principal identity claims."""
        payload_dict: dict[str, Any] = {
            "uid": principal.id,
            "name": principal.name,
            "role": principal.role,
            "email": principal.email,
            "exp": int(time.time()) + self.token_ttl,
        }
        payload_json = json.dumps(payload_dict)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
        sig = _sign(payload_b64, self.secret_key)
        return f"{payload_b64}.{sig}"

    async def resolve_principal(self, raw_token: str) -> Principal | None:
        """Verify token signature and decode principal claims."""
        try:
            payload_b64, sig = raw_token.rsplit(".", 1)
            if not hmac.compare_digest(sig, _sign(payload_b64, self.secret_key)):
                return None
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            if payload.get("exp", 0) < time.time():
                return None

            user_id = payload.get("uid")
            if not user_id:
                return None

            name = payload.get("name")
            role = payload.get("role")
            email = payload.get("email")

            # Fallback for tokens issued by legacy issue_token(uid) (missing name/role claims)
            if not name or not role:
                async with AsyncSessionLocal() as s:
                    user = (await s.execute(
                        select(m.UserProfile).where(m.UserProfile.id == user_id)
                    )).scalar_one_or_none()
                if not user or not user.is_active:
                    return None
                name = user.name
                role = user.role
                email = user.email

            return Principal(id=user_id, name=name, role=role, email=email)
        except Exception:
            return None

    # CamelCase aliases for interface contract compatibility
    issueSession = issue_session
    resolvePrincipal = resolve_principal
