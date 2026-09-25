"""
EPIC — Writers for sensor values: the live value on the equipment and the stored history behind every sensor chart.

A live reading updates both in one transaction, so a chart's last point is always the value the threshold monitor acts
on. A reading extracted from a document is appended to the history only: it must never reach current_readings (the
Telemetry Decoupling Contract in threshold_monitor.py).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.db.database import AsyncSessionLocal

# Past this many points the oldest are dropped, so one sensor's history stays a bounded JSON row.
MAX_HISTORY_POINTS = 500
HISTORY_TIMESTAMP_PRECISION = "seconds"
LIVE_TELEMETRY_SOURCE = "live_telemetry"
DOCUMENT_SOURCE = "document_extraction"
# The key on a history point naming the document it was extracted from.
DOCUMENT_KEY = "document"


def historyPoint(moment: datetime, value: float, unit: str) -> dict[str, Any]:
    return {"ts": moment.isoformat(timespec=HISTORY_TIMESTAMP_PRECISION), "value": value, "unit": unit}


async def recordLiveReadings(equipmentId: str, readings: dict[str, float], readAt: datetime) -> list[str]:
    """Set the value of each sensor configured on the equipment and append it to that sensor's history.

    Returns the keys written. A key the equipment does not configure is skipped, never created, so a caller cannot
    invent a sensor or its thresholds."""
    async with AsyncSessionLocal() as session:
        equipment = await session.get(m.Equipment, equipmentId, with_for_update=True)
        if equipment is None:
            return []
        current = dict(equipment.current_readings or {})
        written = sorted(key for key in readings if isinstance(current.get(key), dict))
        for key in written:
            value = float(readings[key])
            current[key] = {**current[key], "value": value}
            point = {**historyPoint(readAt, value, current[key].get("unit", "")), "source": LIVE_TELEMETRY_SOURCE}
            await _appendPoint(session, equipmentId, key, point)
        equipment.current_readings = current
        await session.commit()
    return written


async def appendSensorHistory(equipmentId: str, sensorKey: str, point: dict[str, Any]) -> None:
    """Append one point to a sensor's stored history without touching the equipment's live value."""
    async with AsyncSessionLocal() as session:
        await _appendPoint(session, equipmentId, sensorKey, point)
        await session.commit()


async def removeDocumentReadings(documentId: str) -> int:
    """Remove every history point extracted from the document, and a sensor history left empty; return how many
    points were removed. A point stored before points named their document cannot be traced and stays."""
    removed = 0
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(m.SensorHistory).with_for_update())).scalars().all()
        for row in rows:
            points = row.readings or []
            kept = [point for point in points if not _fromDocument(point, documentId)]
            removed += len(points) - len(kept)
            if not kept and points:
                await session.delete(row)
            elif len(kept) != len(points):
                row.readings = kept
        await session.commit()
    return removed


async def _appendPoint(session: AsyncSession, equipmentId: str, sensorKey: str, point: dict[str, Any]) -> None:
    result = await session.execute(
        select(m.SensorHistory)
        .where(m.SensorHistory.equipment_id == equipmentId, m.SensorHistory.sensor_key == sensorKey)
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    if row is None:
        session.add(m.SensorHistory(equipment_id=equipmentId, sensor_key=sensorKey, readings=[point]))
        return
    row.readings = [*(row.readings or []), point][-MAX_HISTORY_POINTS:]


def _fromDocument(point: Any, documentId: str) -> bool:
    return isinstance(point, dict) and point.get(DOCUMENT_KEY) == documentId
