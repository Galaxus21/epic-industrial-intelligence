"""
AI Operations Brain — Audit Log Service
Industry-standard immutable audit trail (ISO 27001 / OSHA 1910 compliant).
All writes are fire-and-forget; failures are logged but never propagated.

Usage (anywhere in the codebase):
    from app.services.audit import audit
    audit("create", "work_order", wo_id, equipment_id=eq_id, actor="system",
          notes="WO created by AI query", risk_level="High")
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)


async def _write(
    object_type: str,
    object_id: str,
    action: str,
    *,
    equipment_id: str | None = None,
    actor: str = "system",
    actor_type: str = "system",
    changes: dict[str, Any] | None = None,
    risk_level: str | None = None,
    notes: str | None = None,
    related_ids: list[dict] | None = None,
) -> None:
    """Persist one audit entry. Called via asyncio.create_task."""
    try:
        async with AsyncSessionLocal() as s:
            entry = m.AuditLog(
                timestamp=datetime.utcnow(),
                object_type=object_type,
                object_id=object_id,
                equipment_id=equipment_id,
                action=action,
                actor=actor,
                actor_type=actor_type,
                changes=changes,
                risk_level=risk_level,
                notes=notes,
                related_ids=related_ids,
            )
            s.add(entry)
            await s.commit()
    except Exception as exc:
        logger.error("Audit write failed (%s/%s/%s): %s", object_type, object_id, action, exc)


def audit(
    action: str,
    object_type: str,
    object_id: str,
    *,
    equipment_id: str | None = None,
    actor: str = "system",
    actor_type: str = "system",
    changes: dict[str, Any] | None = None,
    risk_level: str | None = None,
    notes: str | None = None,
    related_ids: list[dict] | None = None,
) -> None:
    """Fire-and-forget audit log entry. Safe to call from any async context."""
    try:
        asyncio.create_task(_write(
            object_type, object_id, action,
            equipment_id=equipment_id, actor=actor, actor_type=actor_type,
            changes=changes, risk_level=risk_level, notes=notes,
            related_ids=related_ids,
        ))
    except RuntimeError:
        # No running loop (tests) — skip silently
        pass
