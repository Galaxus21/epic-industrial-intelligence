"""
AI Operations Brain — Alarm Direction and Breach Evaluation
===========================================================
Single source of truth for sensor alarm and trip threshold evaluation.

Invariant:
1. Direction: Explicit 'alarm_direction' key in reading wins ('low' | 'high').
   Otherwise, if alarm < normal, it is a low alarm; anything else is a high alarm.
2. NaN safety: NaN compares False both ways and must never count as a breach.
"""
from __future__ import annotations

import math
from typing import Any


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


def sensor_status(val: float | None, reading: dict[str, Any]) -> str:
    """Classify sensor status into 'trip', 'alarm', 'high', 'low', or 'normal'."""
    if val is None:
        return "normal"
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return "normal"

    if math.isnan(fval):
        return "normal"

    if is_in_trip(fval, reading):
        return "trip"
    if is_in_alarm(fval, reading):
        return "alarm"

    normal = reading.get("normal")
    if normal is not None:
        try:
            fnormal = float(normal)
            if not math.isnan(fnormal):
                direction = alarm_direction(reading)
                if direction == "low":
                    if fval < fnormal * 0.9:
                        return "low"
                    if fval > fnormal * 1.1:
                        return "high"
                else:
                    if fval > fnormal * 1.1:
                        return "high"
                    if fval < fnormal * 0.9:
                        return "low"
        except (ValueError, TypeError):
            pass

    return "normal"
