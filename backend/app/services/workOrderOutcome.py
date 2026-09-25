"""
EPIC — What a completed work order changes on its equipment.

A rule of thumb, not a measurement. A fix that worked raises the health score and lowers the failure probability; an
unknown or partial outcome moves them less; a fix that did not work changes neither, because nothing got better. The
maintenance due date restarts by work type, matched on whole words. An alarm status is cleared only when the fix
worked and no live reading is still in alarm or trip, since the screen would otherwise say "normal" beside a reading
the threshold monitor is about to raise a new work order for. Metrics that were never measured (None) stay None.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.alarmEvaluation import readingStatuses

WORKED_HEALTH_GAIN = 15.0
WORKED_HEALTH_CEILING = 95.0
UNSURE_HEALTH_GAIN = 5.0
UNSURE_HEALTH_CEILING = 90.0
WORKED_RISK_DROP = 15.0
UNSURE_RISK_DROP = 5.0
RISK_FLOOR = 2.0
DUE_DAYS_BY_TYPE_WORD = {"preventive": 30, "inspection": 30, "pm": 30, "emergency": 7}
DEFAULT_DUE_DAYS = 14
RECOVERED_STATUS = "Normal Operation"
ALARM_STATUS_WORDS = ("alert", "alarm")
LIVE_ALARM_STATUSES = frozenset({"alarm", "trip"})


def equipmentUpdatesAfterWorkOrder(equipment: dict[str, Any], woType: str, worked: bool | None) -> dict[str, Any]:
    """The equipment fields to write after a work order of `woType` completed with outcome `worked`."""
    updates: dict[str, Any] = {"id": equipment["id"], "maintenance_due_days": _dueDays(woType)}
    if worked is False:
        return updates
    gain, ceiling, drop = ((WORKED_HEALTH_GAIN, WORKED_HEALTH_CEILING, WORKED_RISK_DROP) if worked
                           else (UNSURE_HEALTH_GAIN, UNSURE_HEALTH_CEILING, UNSURE_RISK_DROP))
    health, risk = equipment.get("health_score"), equipment.get("failure_probability")
    if health is not None:
        updates["health_score"] = min(float(health) + gain, ceiling)
    if risk is not None:
        updates["failure_probability"] = max(float(risk) - drop, RISK_FLOOR)
    if worked and _showsAnAlarm(equipment) and not _readingInAlarm(equipment):
        updates["status"] = RECOVERED_STATUS
    return updates


def _dueDays(woType: str) -> int:
    words = re.findall(r"[a-z]+", woType.lower())
    return next((DUE_DAYS_BY_TYPE_WORD[word] for word in words if word in DUE_DAYS_BY_TYPE_WORD), DEFAULT_DUE_DAYS)


def _showsAnAlarm(equipment: dict[str, Any]) -> bool:
    status = (equipment.get("status") or "").lower()
    return any(word in status for word in ALARM_STATUS_WORDS)


def _readingInAlarm(equipment: dict[str, Any]) -> bool:
    return any(status in LIVE_ALARM_STATUSES for status in readingStatuses(equipment.get("current_readings")).values())
