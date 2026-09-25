"""
EPIC — The built-in demo sign-ins for local testing: one account per role.

In development the backend makes sure a technician, a supervisor and a manager demo account exist, so every role can
be tried from the login page's quick sign-in without the curl bootstrap step. Like the seeded demo people they have no
password, and each startup puts them back to the documented role, active and password-less, so a demo that demoted
or deactivated one cannot leave it broken. They must never be usable in production: they are not created there, the
login route refuses a password-less account there, and startup refuses to run while an active copy carried over
from a development database exists.
"""
from __future__ import annotations

import logging
from typing import NamedTuple

from sqlalchemy import select

from app.core.config import settings
from app.core.roles import ROLE_MANAGER, ROLE_SUPERVISOR, ROLE_TECHNICIAN
from app.db import models as m
from app.db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class DemoAccount(NamedTuple):
    userId: str
    employeeId: str
    name: str
    role: str


DEMO_ACCOUNTS = (
    DemoAccount("USR-DEMO-TECHNICIAN", "DEMO-TECHNICIAN", "Demo Technician", ROLE_TECHNICIAN),
    DemoAccount("USR-DEMO-SUPERVISOR", "DEMO-SUPERVISOR", "Demo Supervisor", ROLE_SUPERVISOR),
    DemoAccount("USR-DEMO-MANAGER", "DEMO-MANAGER", "Demo Manager", ROLE_MANAGER),
)
DEMO_EMPLOYEE_IDS = tuple(account.employeeId for account in DEMO_ACCOUNTS)
DEVELOPMENT_ENVIRONMENT = "development"
PRODUCTION_ENVIRONMENT = "production"


async def ensureDemoAccounts() -> list[str]:
    """In development, create each missing demo account and restore any that drifted. The employee ids changed."""
    if settings.environment != DEVELOPMENT_ENVIRONMENT:
        return []
    changed: list[str] = []
    async with AsyncSessionLocal() as session:
        existing = {user.employee_id: user for user in await _findDemoAccounts(session)}
        for account in DEMO_ACCOUNTS:
            if _restore(existing.get(account.employeeId), account, session):
                changed.append(account.employeeId)
        await session.commit()
    if changed:
        logger.warning("Demo sign-ins ready: %s (development only; see README quick start)", ", ".join(changed))
    return changed


async def refuseActiveDemoAccountInProduction() -> None:
    """Fail startup in production while a publicly known demo account can still sign in."""
    if settings.environment != PRODUCTION_ENVIRONMENT:
        return
    async with AsyncSessionLocal() as session:
        active = [user for user in await _findDemoAccounts(session) if user.is_active]
    if active:
        names = ", ".join(sorted(user.employee_id for user in active))
        raise RuntimeError(
            f"Refusing to start in production: the demo accounts {names} (listed in the README) are active. "
            f"Deactivate each with PATCH /api/v1/users/<id> {{\"is_active\": false}} first."
        )


def _restore(user: m.UserProfile | None, account: DemoAccount, session) -> bool:
    if user is None:
        session.add(m.UserProfile(id=account.userId, employee_id=account.employeeId, name=account.name,
                                  role=account.role, password_hash=None, is_active=True))
        return True
    if (user.role, user.is_active, user.password_hash) == (account.role, True, None):
        return False
    user.role, user.is_active, user.password_hash = account.role, True, None
    return True


async def _findDemoAccounts(session) -> list[m.UserProfile]:
    query = select(m.UserProfile).where(m.UserProfile.employee_id.in_(DEMO_EMPLOYEE_IDS))
    return list((await session.execute(query)).scalars().all())
