"""
EPIC — Authentication Provider Port
Defines the abstract interface for authentication and principal resolution.
Allows plugging in local (HMAC/PBKDF2), Keycloak, WorkOS, or other IdPs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Principal:
    """Authenticated identity entity."""
    id: str
    name: str
    role: str
    email: str | None = None


@runtime_checkable
class AuthProvider(Protocol):
    """Protocol defining swappable authentication and session lifecycle operations."""

    async def authenticate(self, employee_id: str, password: str | None = None) -> Principal | None:
        """Authenticate user credentials and return the Principal, or None."""
        ...

    async def issue_session(self, principal: Principal) -> str:
        """Issue an opaque or signed session token string for the Principal."""
        ...

    async def resolve_principal(self, raw_token: str) -> Principal | None:
        """Validate token and resolve the corresponding Principal, or None."""
        ...
