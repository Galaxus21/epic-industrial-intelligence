"""
AI Operations Brain — Audit Log Service
Central audit trail written to the AuditLog table.

Two entry points:
  await record(...)  — awaited write; raises on failure when critical=True so a
                       workflow action cannot silently succeed without its audit
                       record. Use this for approvals, transitions, deletions.
  audit(...)         — legacy fire-and-forget wrapper for non-critical telemetry
                       (kept for callers where losing an entry is acceptable).

Usage:
    from app.services.audit import record, audit
    await record("approve", "work_order", wo_id, actor="Jane Doe", actor_type="user")
    audit("update", "sensor", sensor_id)   # non-critical
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)


async def record(
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
    critical: bool = True,
) -> None:
    """Persist one audit entry, awaited by the caller.

    critical=True (default): failures propagate so the calling workflow fails
    loudly instead of completing without an audit record.
    """
    try:
        async with AsyncSessionLocal() as s:
            s.add(m.AuditLog(
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
            ))
            await s.commit()
    except Exception as exc:
        logger.error("Audit write failed (%s/%s/%s): %s", object_type, object_id, action, exc)
        if critical:
            raise


_background_tasks: set[asyncio.Task] = set()


def get_background_tasks() -> set[asyncio.Task]:
    """Return the set of currently running background audit tasks."""
    return set(_background_tasks)


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
) -> asyncio.Task | None:
    """Fire-and-forget audit entry for non-critical telemetry only.

    Background tasks are retained in _background_tasks to protect them
    from premature garbage collection by the Python runtime until completion.
    """
    try:
        task = asyncio.create_task(record(
            action, object_type, object_id,
            equipment_id=equipment_id, actor=actor, actor_type=actor_type,
            changes=changes, risk_level=risk_level, notes=notes,
            related_ids=related_ids, critical=False,
        ))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return task
    except RuntimeError:
        # No running loop (tests) — skip silently
        return None

