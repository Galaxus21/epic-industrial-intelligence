"""
AI Operations Brain — Alarm Direction and Breach Evaluation
===========================================================
Single source of truth for sensor alarm and trip threshold evaluation.

Invariant:
1. Direction: Explicit 'alarm_direction' key in reading wins ('low' | 'high').
   Otherwise, if alarm < normal, it is a low alarm; anything else is a high alarm.
2. NaN safety: NaN compares False both ways and must never count as a breach.
3. No number, no verdict: a missing or unreadable value is "no_reading", never "normal".
4. The high/low band is 10% of the normal value's size either side of it, so it also holds for a negative normal
   (a vacuum pressure), where scaling the value itself would put the band on the wrong side.
"""
from __future__ import annotations

import math
from typing import Any

NO_READING_STATUS = "no_reading"
NORMAL_BAND_FRACTION = 0.1


def alarm_direction(reading: dict[str, Any]) -> str:
    """Determine whether an alarm is a low or high threshold.

    Explicit 'alarm_direction' in reading takes precedence.
    Otherwise: alarm < normal indicates a low alarm; anything else is a high alarm.
    """
    explicit = reading.get("alarm_direction")
    if explicit in ("low", "high"):
        return explicit

    alarm = reading.get("alarm")
    normal = reading.get("normal")
    if alarm is not None and normal is not None:
        try:
            if float(alarm) < float(normal):
                return "low"
        except (ValueError, TypeError):
            pass
    return "high"


def is_in_alarm(val: float | None, reading: dict[str, Any]) -> bool:
    """Check if value breaches the alarm threshold respecting direction.

    NaN compares False both ways and must never count as a breach.
    """
    if val is None:
        return False
    alarm = reading.get("alarm")
    if alarm is None:
        return False
    try:
        fval = float(val)
        falarm = float(alarm)
    except (ValueError, TypeError):
        return False

    if math.isnan(fval) or math.isnan(falarm):
        return False

    direction = alarm_direction(reading)
    if direction == "low":
        return fval < falarm
    return fval > falarm


def is_in_trip(val: float | None, reading: dict[str, Any]) -> bool:
    """Check if value breaches the trip threshold respecting direction.

    NaN compares False both ways and must never count as a breach.
    """
    if val is None:
        return False
    trip = reading.get("trip")
    if trip is None:
        return False
    try:
        fval = float(val)
        ftrip = float(trip)
    except (ValueError, TypeError):
        return False

    if math.isnan(fval) or math.isnan(ftrip):
        return False

    direction = alarm_direction(reading)
    if direction == "low":
        return fval <= ftrip
    return fval >= ftrip


def readingStatuses(readings: dict[str, Any] | None) -> dict[str, str]:
    """sensor key -> sensor_status, sent with every equipment so the browser never evaluates a threshold."""
    return {
        key: sensor_status(reading.get("value"), reading)
        for key, reading in (readings or {}).items()
        if isinstance(reading, dict)
    }


def sensor_status(val: float | None, reading: dict[str, Any]) -> str:
    """Classify sensor status into 'trip', 'alarm', 'high', 'low', 'normal', or 'no_reading' without a number."""
    fval = _number(val)
    if fval is None:
        return NO_READING_STATUS
    if is_in_trip(fval, reading):
        return "trip"
    if is_in_alarm(fval, reading):
        return "alarm"

    fnormal = _number(reading.get("normal"))
    if fnormal is None:
        return "normal"
    band = abs(fnormal) * NORMAL_BAND_FRACTION
    if fval > fnormal + band:
        return "high"
    if fval < fnormal - band:
        return "low"
    return "normal"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return None if math.isnan(number) else number
